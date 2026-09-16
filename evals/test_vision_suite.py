import unittest
import vision_suite as v

class GradingTests(unittest.TestCase):
    def test_exact_json_fields(self):
        r=v.grade('{"code":"R7K2","count":6}', {'code':'R7K2','count':6})
        self.assertEqual(r['score'],2)
    def test_partial_credit(self):
        r=v.grade('{"code":"wrong","count":6}', {'code':'R7K2','count':6})
        self.assertEqual(r['score'],1)
    def test_boolean_is_not_number(self):
        self.assertEqual(v.grade('{"count":true}',{'count':1})['score'],0)
    def test_fenced_json(self):
        self.assertEqual(v.grade('```json\n{"code":"R7K2"}\n```',{'code':'R7K2'})['score'],1)
    def test_malformed_and_missing(self):
        self.assertEqual(v.grade('I cannot tell',{'code':'R7K2'})['score'],0)
        self.assertEqual(v.grade('{}',{'code':'R7K2'})['score'],0)
    def test_lists_ordered(self):
        self.assertEqual(v.grade('{"ids":["A","B"]}',{'ids':['B','A']})['score'],0)

class FixtureTests(unittest.TestCase):
    def test_suite_artifacts(self):
        import tempfile
        import pathlib
        from vision_fixtures import build_suite
        with tempfile.TemporaryDirectory() as tmp:
            tasks = build_suite(pathlib.Path(tmp))
            self.assertEqual(len(tasks), 9)
            self.assertEqual([t['difficulty'] for t in tasks].count('easy'),3)
            self.assertEqual([t['difficulty'] for t in tasks].count('medium'),3)
            self.assertEqual([t['difficulty'] for t in tasks].count('hard'),3)
            self.assertEqual(len({t['id'] for t in tasks}),9)
            for task in tasks:
                self.assertTrue(pathlib.Path(task['image']).is_file())
                self.assertTrue(task['expected'])
            self.assertEqual(tasks[0]['expected'], {'code':'R7K2'})
            self.assertEqual(tasks[5]['expected'], {'destination':'FAN HIGH'})
            self.assertTrue((pathlib.Path(tmp)/'contact-sheet.png').is_file())

class RunnerTests(unittest.TestCase):
    def test_real_http_checkpoint_and_no_answer_leak(self):
        import tempfile, pathlib, json, threading
        from http.server import BaseHTTPRequestHandler, HTTPServer
        received=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
                data=json.dumps({'choices':[{'message':{'content':'{"code":"R7K2"}'},'finish_reason':'stop'}],'usage':{'completion_tokens':8}}).encode()
                self.send_response(200); self.end_headers(); self.wfile.write(data)
            def log_message(self,*args): pass
        server=HTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                p=pathlib.Path(tmp); (p/'x.png').write_bytes(b'fixture'); (p/'key').write_text('test-key')
                tasks=[{'id':'ocr','difficulty':'easy','image':str(p/'x.png'),'question':'Read the code.','expected':{'code':'R7K2'}}]
                r=v.run_suite(tasks, f'http://127.0.0.1:{server.server_port}', 'test-model', p/'key', p/'result.json')
                self.assertEqual(r['score'],1); self.assertEqual(r['status'],'complete')
                self.assertEqual(json.loads((p/'result.json').read_text())['score'],1)
                self.assertNotIn('R7K2',json.dumps(received))
                self.assertEqual(received[0]['messages'][0]['content'][1]['type'],'image_url')
        finally:
            server.shutdown(); server.server_close(); thread.join()

if __name__=='__main__': unittest.main()
