#!/usr/bin/env python3
"""Tests for concurrency_sweep: the arithmetic and the failure handling.

No model is served here — a stub HTTP server returns a fixed SSE stream, so the
harness's own behaviour is what gets checked.
"""
import importlib.util, json, threading, unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "sweep", str(Path(__file__).with_name("concurrency_sweep.py")))
sweep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sweep)

TOKENS = 5


class Handler(BaseHTTPRequestHandler):
    fail = False

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", 0)))
        if Handler.fail:
            self.send_response(500)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for i in range(TOKENS):
            chunk = {"choices": [{"delta": {"content": f"t{i} "}}]}
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
        # A reasoning-only delta must count: thinking tokens cost the same
        # bandwidth, and not counting them is how a throughput script silently
        # reports zero for a model served with a reasoning parser.
        chunk = {"choices": [{"delta": {"reasoning_content": "think "}}]}
        self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")

    def log_message(self, *_args):
        pass


class SweepTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/v1/chat/completions"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        Handler.fail = False

    def test_counts_every_stream_and_reasoning_tokens(self):
        results = sweep.sweep(self.url, "k", "m", [1, 2], 50)
        self.assertEqual(results[0]["tokens"], TOKENS + 1)
        self.assertEqual(results[1]["tokens"], (TOKENS + 1) * 2)
        self.assertEqual([r["streams"] for r in results], [1, 2])

    def test_aggregate_exceeds_per_stream_when_parallel(self):
        results = sweep.sweep(self.url, "k", "m", [4], 50)
        row = results[0]
        self.assertGreater(row["aggregate_tok_s"], row["per_stream_tok_s"])
        self.assertEqual(row["failed"], 0)

    def test_failed_streams_are_reported_not_averaged_as_zero(self):
        Handler.fail = True
        results = sweep.sweep(self.url, "k", "m", [2], 50)
        self.assertEqual(results[0]["failed"], 2)
        self.assertNotIn("aggregate_tok_s", results[0])


if __name__ == "__main__":
    unittest.main()
