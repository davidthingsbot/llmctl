"""Authenticated, streaming frontend for loopback-only TensorFold.
Keeps existing clients on port 8005; key values never enter logs or the backend.
"""
import argparse
import asyncio
import hmac
from pathlib import Path

import aiohttp
from aiohttp import web

CLIENT = web.AppKey('client', aiohttp.ClientSession)
HOP = {'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
       'te', 'trailer', 'transfer-encoding', 'upgrade'}


def filtered(headers):
    excluded = HOP | {x.strip().lower() for x in headers.get('Connection', '').split(',')}
    return {k: v for k, v in headers.items()
            if k.lower() not in excluded | {'authorization', 'host'}}


def create_app(upstream, keys):
    app = web.Application(client_max_size=96 * 1024 * 1024)

    async def client_context(app):
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=7200, connect=10),
                                         auto_decompress=False) as client:
            app[CLIENT] = client
            yield

    async def proxy(request):
        if request.path != '/health':
            auth = request.headers.get('Authorization', '')
            if not auth.startswith('Bearer ') or not any(
                    hmac.compare_digest(auth[7:].encode(), key.encode()) for key in keys):
                return web.json_response({'error': 'Unauthorized'}, status=401)
            if not request.path.startswith('/v1/'):
                return web.json_response({'error': 'Unknown endpoint'}, status=404)
        result = None
        try:
            async with app[CLIENT].request(request.method, upstream + request.rel_url.path_qs,
                                           data=await request.read(), headers=filtered(request.headers),
                                           allow_redirects=False) as response:
                result = web.StreamResponse(status=response.status, headers=filtered(response.headers))
                await result.prepare(request)
                async for chunk in response.content.iter_any():
                    await result.write(chunk)
                await result.write_eof()
                return result
        except (aiohttp.ClientError, asyncio.TimeoutError):
            if result is not None and result.prepared:
                raise ConnectionResetError('Backend stream interrupted')
            return web.json_response({'error': 'Inference backend unavailable'}, status=502)

    app.cleanup_ctx.append(client_context)
    app.router.add_route('*', '/{path:.*}', proxy)
    return app


async def configured_app(args):
    keys = [key.strip() for key in Path(args.keyfile).read_text().splitlines() if key.strip()]
    if not keys:
        raise RuntimeError('Empty API key file')
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as client:
        async with client.get(args.upstream + '/health') as response:
            response.raise_for_status()
            health = await response.json()
            if health.get('ok') is not True or health.get('context_length') != 1048576:
                raise RuntimeError('Backend health/context mismatch')
        async with client.get(args.upstream + '/v1/models') as response:
            response.raise_for_status()
            listing = await response.json()
            if [m['id'] for m in listing['data']] != ['GLM-5.3-Flash-EXL3']:
                raise RuntimeError('Backend model identity mismatch')
    return create_app(args.upstream, keys)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8005)
    parser.add_argument('--upstream', default='http://127.0.0.1:18888')
    parser.add_argument('--keyfile', default='/home/david/.config/vllm/api-keys')
    args = parser.parse_args()
    web.run_app(configured_app(args), host=args.host, port=args.port, access_log=None,
                handler_cancellation=True)


if __name__ == '__main__':
    main()
