#!/usr/bin/env python3
"""Measure how a served model scales with concurrent streams.

`llmctl bench` is single-stream and the eval suites are sequential, so nothing
in this repo reproduced the 1/2/4/8 concurrency numbers recorded in the machine
NOTES. This does.

The number that matters is AGGREGATE tokens/sec across all streams. A model
whose aggregate is flat is bandwidth-bound with nothing left to give -- adding
clients just divides the same throughput, which is what a MoE with distinct
per-token experts does on a low-bandwidth box. A model whose aggregate climbs is
being served by an engine with spare capacity (vLLM's continuous batching, or
llama.cpp with enough free slots).

Read alongside per-stream decay and TTFT: a server can hold aggregate up while
making every individual client wait much longer, which is the failure mode that
matters for interactive use.
"""
import argparse, json, statistics, sys, threading, time, urllib.request
from pathlib import Path

PROMPT = ("Explain, in about 150 words and without bullet points, why token "
          "generation on a memory-bandwidth-bound accelerator depends on the "
          "number of active parameters rather than the total parameter count.")


def one_stream(url, key, model, max_tokens, out, idx):
    body = {"model": model, "messages": [{"role": "user", "content": PROMPT}],
            "temperature": 0.7, "max_tokens": max_tokens, "stream": True,
            "chat_template_kwargs": {"enable_thinking": False}}
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key})
    started = time.monotonic()
    first = None
    tokens = 0
    try:
        with urllib.request.urlopen(req, timeout=900) as response:
            for raw in response:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload == "[DONE]":
                    break
                try:
                    delta = json.loads(payload)["choices"][0].get("delta", {})
                except (ValueError, KeyError, IndexError):
                    continue
                # Count reasoning tokens too: they cost exactly the same bandwidth.
                if delta.get("content") or delta.get("reasoning_content"):
                    if first is None:
                        first = time.monotonic() - started
                    tokens += 1
    except Exception as exc:                      # a failed stream must not be
        out[idx] = {"error": str(exc)}            # silently averaged as a zero
        return
    elapsed = time.monotonic() - started
    out[idx] = {"tokens": tokens, "elapsed_s": elapsed, "ttft_s": first,
                "tok_s": tokens / elapsed if elapsed else 0.0}


def sweep(url, key, model, levels, max_tokens):
    results = []
    for n in levels:
        out = [None] * n
        threads = [threading.Thread(target=one_stream,
                                    args=(url, key, model, max_tokens, out, i))
                   for i in range(n)]
        wall = time.monotonic()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        wall = time.monotonic() - wall
        errors = [r for r in out if r and "error" in r]
        good = [r for r in out if r and "error" not in r]
        if not good:
            print(f"  {n:2d} streams: ALL FAILED — {errors[0]['error'][:80]}", flush=True)
            results.append({"streams": n, "failed": len(errors)})
            continue
        total = sum(r["tokens"] for r in good)
        agg = total / wall
        per = statistics.mean(r["tok_s"] for r in good)
        ttft = statistics.mean(r["ttft_s"] for r in good if r["ttft_s"] is not None)
        results.append({"streams": n, "aggregate_tok_s": round(agg, 1),
                        "per_stream_tok_s": round(per, 1), "ttft_s": round(ttft, 2),
                        "tokens": total, "wall_s": round(wall, 1),
                        "failed": len(errors)})
        note = f"  ({len(errors)} failed)" if errors else ""
        print(f"  {n:2d} streams: aggregate {agg:7.1f} tok/s | per-stream {per:6.1f} "
              f"| TTFT {ttft:5.2f}s | {total} tok in {wall:.1f}s{note}", flush=True)
    return results


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--key-file", required=True)
    p.add_argument("--output")
    p.add_argument("--levels", default="1,2,4,8",
                   help="comma-separated stream counts (default 1,2,4,8)")
    p.add_argument("--max-tokens", type=int, default=200)
    args = p.parse_args()
    key = next(l.strip() for l in Path(args.key_file).read_text().splitlines() if l.strip())
    levels = [int(x) for x in args.levels.split(",")]
    print(f"sweeping {args.model} at {levels} streams, {args.max_tokens} tokens each",
          flush=True)
    results = sweep(args.url, key, args.model, levels, args.max_tokens)
    base = next((r for r in results if r.get("streams") == 1
                 and "aggregate_tok_s" in r), None)
    if base:
        peak = max(r["aggregate_tok_s"] for r in results if "aggregate_tok_s" in r)
        print(f"scaling: {peak / base['aggregate_tok_s']:.2f}x from 1 stream to peak")
    if args.output:
        Path(args.output).write_text(json.dumps(
            {"model": args.model, "levels": levels, "max_tokens": args.max_tokens,
             "results": results}, indent=2) + "\n")
        print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
