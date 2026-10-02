import importlib.util
import pathlib
import unittest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

spec = importlib.util.spec_from_file_location('tf_frontend', pathlib.Path(__file__).parents[1] / 'scripts/tensorfold_frontend.py')
frontend = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frontend)


class FrontendTests(unittest.IsolatedAsyncioTestCase):
    async def test_authenticated_chat_reaches_backend_without_credentials(self):
        self.assertTrue(callable(getattr(frontend, 'create_app', None)), 'authenticated frontend not implemented')
        async def handler(request):
            self.assertNotIn('Authorization', request.headers)
            self.assertEqual((await request.json())['model'], 'test-model')
            return web.json_response({'choices': [{'message': {'content': 'OK'}}]})
        backend = web.Application()
        backend.router.add_post('/v1/chat/completions', handler)
        async with TestServer(backend) as target:
            async with TestClient(TestServer(frontend.create_app(str(target.make_url('')).rstrip('/'), ['secret']))) as client:
                denied = await client.post('/v1/chat/completions', json={})
                self.assertEqual(denied.status, 401)
                wrong = await client.post('/v1/chat/completions', headers={'Authorization': 'Bearer wrong'}, json={})
                self.assertEqual(wrong.status, 401)
                response = await client.post('/v1/chat/completions', headers={'Authorization': 'Bearer secret'}, json={'model': 'test-model'})
                self.assertEqual(response.status, 200)
                self.assertEqual((await response.json())['choices'][0]['message']['content'], 'OK')

    async def test_health_and_sse_are_forwarded_without_buffering(self):
        self.assertTrue(callable(getattr(frontend, 'create_app', None)))
        async def health(request):
            return web.json_response({'ok': True, 'backend': 'tensorfold'})
        async def stream(request):
            response = web.StreamResponse(headers={'Content-Type': 'text/event-stream'})
            await response.prepare(request)
            await response.write(b'data: {"text":"hello"}\n\n')
            await response.write(b'data: [DONE]\n\n')
            await response.write_eof()
            return response
        backend = web.Application()
        backend.router.add_get('/health', health)
        backend.router.add_post('/v1/chat/completions', stream)
        async with TestServer(backend) as target:
            async with TestClient(TestServer(frontend.create_app(str(target.make_url('')).rstrip('/'), ['secret']))) as client:
                response = await client.get('/health')
                self.assertEqual((await response.json())['backend'], 'tensorfold')
                response = await client.post('/v1/chat/completions', headers={'Authorization': 'Bearer secret'}, json={'stream': True})
                self.assertEqual(response.headers['Content-Type'], 'text/event-stream')
                self.assertEqual(await response.read(), b'data: {"text":"hello"}\n\ndata: [DONE]\n\n')

    def test_v13_media_body_limit_is_not_reduced_by_frontend(self):
        self.assertEqual(frontend.create_app('http://127.0.0.1:1', ['secret'])._client_max_size, 96 * 1024 * 1024)

    def test_production_enables_disconnected_client_cancellation(self):
        from unittest import mock
        with mock.patch('sys.argv', ['frontend']), mock.patch.object(frontend, 'configured_app', new=mock.Mock(return_value=object())), mock.patch.object(frontend.web, 'run_app') as run:
            frontend.main()
        self.assertIs(run.call_args.kwargs.get('handler_cancellation'), True)

    def test_orchestration_failure_preserves_unknown_remote_state(self):
        import os
        import subprocess
        import tempfile
        source = (pathlib.Path(__file__).parents[1] / 'scripts/teardown-glm53-tensorfold.sh').read_text()
        with tempfile.TemporaryDirectory() as d:
            root = pathlib.Path(d)
            for name, script in [('docker', '#!/bin/sh\nprintf "true\\n"\n'), ('ssh', '#!/bin/sh\nexit 255\n')]:
                file = root / name
                file.write_text(script)
                file.chmod(0o700)
            teardown = root / 'teardown.sh'
            teardown.write_text(source.replace('exec /home/david/work/glm53-tensorfold/stop.sh', 'exit 77'))
            environment = dict(os.environ, PATH=str(root) + ':' + os.environ['PATH'], SERVICE_RESULT='exit-code')
            result = subprocess.run(['bash', str(teardown)], env=environment, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, 'must preserve ranks when SSH state is unknown')

    async def test_backend_outage_returns_502_not_a_fake_completion(self):
        self.assertTrue(callable(getattr(frontend, 'create_app', None)))
        target = TestServer(web.Application())
        await target.start_server()
        url = str(target.make_url('')).rstrip('/')
        await target.close()
        async with TestClient(TestServer(frontend.create_app(url, ['secret']))) as client:
            response = await client.get('/health')
            self.assertEqual(response.status, 502)
            self.assertNotIn('choices', await response.json())


if __name__ == '__main__':
    unittest.main()
