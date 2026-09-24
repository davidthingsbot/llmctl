import base64
import io
import json
import os
import pathlib
import unittest
import threading
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from image_service import ImageInference, analyze_request, match_candidates, verify_weight_hashes, create_server, MAX_BODY, MAX_CONNECTIONS, READ_TIMEOUT


class ContractTests(unittest.TestCase):
    def test_weight_hash_verification_fails_closed(self):
        with self.assertRaisesRegex(ValueError, 'weight'):
            verify_weight_hashes({'object_detection_yolox_2022nov.onnx': 'wrong'})

    @unittest.skipUnless(os.environ.get('IMAGE_TRIAL_MODELS'), 'explicit public weights and fixture required')
    def test_actual_cow_detector(self):
        model = ImageInference(os.environ['IMAGE_TRIAL_MODELS'])
        image = pathlib.Path(os.environ['IMAGE_TRIAL_MODELS'], 'cow.jpg').read_bytes()
        results = model.detect_objects(image)
        self.assertTrue(any(f['label'] == 'cow' for f in results), results)

    @unittest.skipUnless(os.environ.get('IMAGE_TRIAL_MODELS'), 'explicit public weights and fixture required')
    def test_actual_enrolled_candidate_on_distinct_public_domain_photos(self):
        folder = pathlib.Path(os.environ['IMAGE_TRIAL_MODELS'])
        model = ImageInference(folder)
        results = model.match_people((folder / 'face-query.jpg').read_bytes(),
                                     [{'personRef': 'demo:obama', 'image': (folder / 'face-reference.jpg').read_bytes()}])
        self.assertEqual(results[0]['candidates'][0]['personRef'], 'demo:obama')
        self.assertEqual(model.match_people((folder / 'cow.jpg').read_bytes(),
                                            [{'personRef': 'demo:obama', 'image': (folder / 'face-reference.jpg').read_bytes()}]), [])

    @unittest.skipUnless(os.environ.get('IMAGE_TRIAL_MODELS'), 'explicit public weights and fixture required')
    def test_real_two_views_same_person_and_negative_abstention(self):
        folder = pathlib.Path(os.environ['IMAGE_TRIAL_MODELS'])
        model = ImageInference(folder)
        gallery = [{'personRef': 'demo:obama', 'image': (folder / name).read_bytes()}
                   for name in ('face-reference.jpg', 'face-query.jpg')]
        query = model.match_people((folder / 'face-query.jpg').read_bytes(), gallery)
        self.assertEqual(query[0]['candidates'][0]['personRef'], 'demo:obama')
        self.assertEqual(query[0]['candidates'][0]['referenceCount'], 2)
        self.assertEqual(model.match_people((folder / 'cow.jpg').read_bytes(), gallery), [])

    def test_same_person_views_do_not_compete_against_each_other(self):
        gallery = [{'personRef': 'p:a', 'imageRef': 'i:1'}, {'personRef': 'p:a', 'imageRef': 'i:2'}, {'personRef': 'p:b', 'imageRef': 'i:3'}]
        candidate = match_candidates(None, gallery, scores=[.90, .89, .60], threshold=.363, margin=.05)
        self.assertEqual(candidate[0]['personRef'], 'p:a')
        self.assertEqual(candidate[0]['marginToNext'], .30)
        self.assertEqual(candidate[0]['referenceCount'], 2)
        self.assertEqual(match_candidates(None, gallery, scores=[.90, .2, .88], margin=.05), [])
        request = {'version': 1, 'kind': 'knownPeople', 'image': base64.b64encode(b'img').decode(),
                   'gallery': [{'personRef': 'p:a', 'image': base64.b64encode(b'view').decode()} for _ in range(2)]}
        model = Mock(provenance={})
        model.match_people.return_value = []
        self.assertEqual(len(analyze_request(request, model)['findings']), 0)

    def test_inference_wait_is_bounded_when_model_busy(self):
        request = {'version': 1, 'kind': 'objects', 'image': base64.b64encode(b'a').decode()}
        from image_service import INFERENCE_LOCK
        INFERENCE_LOCK.acquire()
        try:
            with patch('image_service.INFERENCE_WAIT', .05):
                with self.assertRaisesRegex(ValueError, 'busy'):
                    analyze_request(request, Mock(provenance={}))
        finally:
            INFERENCE_LOCK.release()

    def test_serializes_model_calls_for_parallel_requests(self):
        active = 0
        peak = 0
        gate = threading.Barrier(4)
        class Model:
            provenance = {}
            def detect_objects(self, raw):
                nonlocal active, peak
                active += 1
                peak = max(peak, active)
                time.sleep(.03)
                active -= 1
                return []
        model = Model()
        def invoke(_):
            gate.wait()
            return analyze_request({'version': 1, 'kind': 'objects', 'image': base64.b64encode(b'a').decode()}, model)
        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(invoke, range(4)))
        self.assertEqual(peak, 1)

    def test_rejects_large_pixel_headers_before_decode(self):
        # PNG header advertises an enormous allocation but has no pixel data.
        import zlib
        from PIL import Image
        buffer = io.BytesIO()
        Image.new('RGB', (1, 1)).save(buffer, format='PNG')
        raw = bytearray(buffer.getvalue())
        raw[16:24] = (20000).to_bytes(4, 'big') * 2
        raw[29:33] = zlib.crc32(raw[12:29]).to_bytes(4, 'big')
        raw = bytes(raw)
        model = ImageInference.__new__(ImageInference)
        model.cv = Mock()
        model.np = Mock()
        with self.assertRaisesRegex(ValueError, 'pixel'):
            model.decode(raw)
        model.cv.imdecode.assert_not_called()

    def test_server_limits_connections_body_and_slow_reads(self):
        model = Mock(provenance={})
        model.detect_objects.return_value = []
        server = create_server(model, port=0)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        url = f'http://127.0.0.1:{server.server_port}'
        try:
            self.assertEqual(json.loads(urlopen(url + '/health').read())['capabilities'], ['objects', 'knownPeople'])
            with self.assertRaises(HTTPError) as error:
                urlopen(Request(url + '/v1/analyze', data=b'a', headers={'Content-Length': str(MAX_BODY + 1)}))
            self.assertEqual(error.exception.code, 413)
            self.assertLessEqual(server.max_connections, MAX_CONNECTIONS)
            self.assertEqual(server.read_timeout, READ_TIMEOUT)
        finally:
            server.shutdown(); server.server_close(); worker.join(timeout=2)

    def test_slow_drip_connection_has_absolute_deadline(self):
        with patch('image_service.READ_TIMEOUT', .25):
            server = create_server(Mock(provenance={}), port=0)
        worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
        try:
            with socket.create_connection(('127.0.0.1', server.server_port), timeout=2) as client:
                client.sendall(b'POST /v1/analyze HTTP/1.1\r\nHost: localhost\r\nContent-Length: 100\r\n\r\nx')
                time.sleep(.5)
                client.settimeout(1)
                self.assertEqual(client.recv(4096), b'')
        finally:
            server.shutdown(); server.server_close(); worker.join(timeout=2)

    def test_fifth_slow_connection_cannot_allocate_worker(self):
        with patch('image_service.READ_TIMEOUT', 1):
            server = create_server(Mock(provenance={}), port=0)
        worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
        clients = []
        try:
            for _ in range(MAX_CONNECTIONS):
                client = socket.create_connection(('127.0.0.1', server.server_port), timeout=2)
                client.sendall(b'POST /v1/analyze HTTP/1.1\r\nHost: localhost\r\nContent-Length: 100\r\n\r\nx')
                clients.append(client)
            deadline = time.monotonic() + .5
            while server.slots._value and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertEqual(server.slots._value, 0)
            with socket.create_connection(('127.0.0.1', server.server_port), timeout=1) as extra:
                extra.settimeout(.5)
                self.assertEqual(extra.recv(1), b'')
            self.assertEqual(server.slots._value, 0)
        finally:
            for client in clients: client.close()
            server.shutdown(); server.server_close(); worker.join(timeout=2)

    def test_abstains_without_enrollment(self):
        self.assertEqual(match_candidates([1.0, 0.0], []), [])

    def test_ranks_enrolled_candidate_but_rejects_ambiguous_match(self):
        gallery = [{'personRef': 'p:1', 'image': 'example'}, {'personRef': 'p:2', 'image': 'example'}]
        scores = [0.9, 0.88]
        self.assertEqual(match_candidates([1, 0], gallery, scores=scores, threshold=0.36, margin=0.05), [])
        candidate = match_candidates([1, 0], gallery, scores=[0.9, 0.1], threshold=0.36, margin=0.05)[0]
        self.assertEqual(candidate['personRef'], 'p:1')
        self.assertEqual(candidate['threshold'], 0.36)
        self.assertEqual(candidate['margin'], 0.05)

    def test_rejects_bad_input_before_inference(self):
        model = Mock()
        with self.assertRaises(ValueError):
            analyze_request({'version': 1, 'kind': 'objects', 'image': '!!'}, model)
        model.assert_not_called()

    def test_rejects_excessive_total_gallery_payload(self):
        model = Mock()
        request = {'version': 1, 'kind': 'knownPeople', 'image': base64.b64encode(b'jpeg').decode(),
                   'gallery': [{'personRef': f'p:{i}', 'image': base64.b64encode(b'x' * 600_000).decode()} for i in range(16)]}
        with self.assertRaisesRegex(ValueError, 'total'):
            analyze_request(request, model)
        model.match_people.assert_not_called()

    def test_bounded_versioned_object_response(self):
        model = Mock()
        model.detect_objects.return_value = [{'label': 'cow', 'score': .87, 'box': [1, 2, 3, 4]}]
        response = analyze_request({'version': 1, 'kind': 'objects', 'image': base64.b64encode(b'abc').decode()}, model)
        self.assertEqual(response['version'], 1)
        self.assertEqual(response['findings'][0]['label'], 'cow')
        self.assertNotIn('embedding', str(response))


if __name__ == '__main__':
    unittest.main()
