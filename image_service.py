"""CPU-only image inference companion (loopback by default); weights are provisioned explicitly.

OpenCV Zoo YOLOX (Apache-2.0), YuNet (MIT), SFace (Apache-2.0).
COCO classes include car/cow. Similarity is uncalibrated; names never leave this service.
"""
import argparse
import base64
import binascii
import hashlib
import json
import math
import os
import io
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

INFERENCE_LOCK = threading.Lock()  # OpenCV DNN / YuNet / SFace instances are mutable.
INFERENCE_WAIT = 5

def serialized_inference(call, *args):
    if not INFERENCE_LOCK.acquire(timeout=INFERENCE_WAIT):
        raise ValueError('inference busy')
    try:
        return call(*args)
    finally:
        INFERENCE_LOCK.release()

MAX_BODY = 12 * 1024 * 1024
READ_TIMEOUT = 5
MAX_CONNECTIONS = 4

MAX_IMAGE = 4 * 1024 * 1024
MAX_PIXELS = 12_000_000
COCO = ('person bicycle car motorcycle airplane bus train truck boat traffic-light fire-hydrant stop-sign parking-meter bench bird cat dog horse sheep cow elephant bear zebra giraffe backpack umbrella handbag tie suitcase frisbee skis snowboard sports-ball kite baseball-bat baseball-glove skateboard surfboard tennis-racket bottle wine-glass cup fork knife spoon bowl banana apple sandwich orange broccoli carrot hot-dog pizza donut cake chair couch potted-plant bed dining-table toilet tv laptop mouse remote keyboard cell-phone microwave oven toaster sink refrigerator book clock vase scissors teddy-bear hair-drier toothbrush').split()
WEIGHT_SHA256 = {
    'object_detection_yolox_2022nov.onnx': 'c5c2d13e59ae883e6af3b45daea64af4833a4951c92d116ec270d9ddbe998063',
    'face_detection_yunet_2023mar.onnx': '8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4',
    'face_recognition_sface_2021dec_int8.onnx': '2b0e941e6f16cc048c20aee0c8e31f569118f65d702914540f7bfdc14048d78a',
}


def verify_weight_hashes(hashes):
    if hashes != WEIGHT_SHA256:
        raise ValueError('image weight digest mismatch')



def match_candidates(query, gallery, *, scores=(), threshold=0.363, margin=0.05):
    if len(gallery) != len(scores) or not all(math.isfinite(float(s)) for s in scores):
        return []
    people = {}
    for entry, score in zip(gallery, scores):
        person = entry['personRef']
        best, count = people.get(person, (float('-inf'), 0))
        people[person] = (max(best, float(score)), count + 1)
    ranked = sorted(people.items(), key=lambda item: item[1][0], reverse=True)
    if not ranked or ranked[0][1][0] < threshold:
        return []
    difference = ranked[0][1][0] - ranked[1][1][0] if len(ranked) > 1 else None
    if difference is not None and difference < margin:
        return []
    return [{'personRef': ranked[0][0], 'similarity': round(ranked[0][1][0], 5), 'threshold': threshold, 'margin': margin,
             'marginToNext': round(difference, 5) if difference is not None else None, 'referenceCount': ranked[0][1][1]}]


def _region(box, width, height):
    x, y, w, h = [float(v) for v in box]
    x1, y1 = max(0, x), max(0, y)
    x2, y2 = min(width, x + w), min(height, y + h)
    if not all(map(math.isfinite, (x1, y1, x2, y2))) or x2 <= x1 or y2 <= y1:
        return None
    return [round(x1 / width * 100, 3), round(y1 / height * 100, 3), round((x2 - x1) / width * 100, 3), round((y2 - y1) / height * 100, 3)]


def analyze_request(request, model):
    if not isinstance(request, dict) or request.get('version') != 1 or request.get('kind') not in ('objects', 'knownPeople'):
        raise ValueError('invalid request version or kind')
    image = request.get('image')
    if not isinstance(image, str) or len(image) > MAX_IMAGE * 2:
        raise ValueError('image missing or too large')
    try:
        raw = base64.b64decode(image, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError('invalid image encoding') from None
    if not raw or len(raw) > MAX_IMAGE:
        raise ValueError('image missing or too large')
    if request['kind'] == 'objects':
        findings = serialized_inference(model.detect_objects, raw)[:50]
    else:
        gallery = request.get('gallery', [])
        if not isinstance(gallery, list) or len(gallery) > 16:
            raise ValueError('gallery too large')
        refs = set()
        verified = []
        total_bytes = len(raw)
        for entry in gallery:
            if not isinstance(entry, dict) or not isinstance(entry.get('personRef'), str) or not entry['personRef'] or not isinstance(entry.get('image'), str):
                raise ValueError('invalid gallery entry')
            if len(entry['image']) > MAX_IMAGE * 2:
                raise ValueError('invalid gallery image')
            try:
                data = base64.b64decode(entry['image'], validate=True)
            except (ValueError, binascii.Error):
                raise ValueError('invalid gallery image') from None
            total_bytes += len(data)
            if total_bytes > 8 * 1024 * 1024:
                raise ValueError('total gallery bytes exceeded')
            if not data or len(data) > MAX_IMAGE:
                raise ValueError('invalid gallery image')
            verified.append({'personRef': entry['personRef'], 'image': data})
        findings = serialized_inference(model.match_people, raw, verified)[:16]
    return {'version': 1, 'kind': request['kind'], 'model': model.provenance, 'findings': findings}


class ImageInference:
    def __init__(self, weights_dir):
        import cv2
        import numpy as np
        self.cv = cv2
        self.np = np
        names = ('object_detection_yolox_2022nov.onnx', 'face_detection_yunet_2023mar.onnx', 'face_recognition_sface_2021dec_int8.onnx')
        paths = [os.path.join(weights_dir, name) for name in names]
        self.provenance = {}
        for name, path in zip(names, paths):
            with open(path, 'rb') as weights:
                self.provenance[name] = hashlib.sha256(weights.read()).hexdigest()
        verify_weight_hashes(self.provenance)
        self.net = cv2.dnn.readNet(paths[0])
        self.face = cv2.FaceDetectorYN.create(paths[1], '', (320, 320), score_threshold=0.8)
        self.recognizer = cv2.FaceRecognizerSF.create(paths[2], '')
        self.grids = np.concatenate([np.stack(np.meshgrid(np.arange(640 // stride), np.arange(640 // stride)), 2).reshape(1, -1, 2) for stride in (8, 16, 32)], 1)
        self.strides = np.concatenate([np.full((1, (640 // stride) ** 2, 1), stride) for stride in (8, 16, 32)], 1)

    def decode(self, raw):
        # Inspect compressed image dimensions before OpenCV allocates decoded pixels.
        from PIL import Image, UnidentifiedImageError
        try:
            with Image.open(io.BytesIO(raw)) as header:
                width, height = header.size
                if width < 1 or height < 1 or width * height > MAX_PIXELS:
                    raise ValueError('pixel limit exceeded')
                if header.format not in ('JPEG', 'PNG', 'WEBP'):
                    raise ValueError('unsupported image')
        except Image.DecompressionBombError:
            raise ValueError('pixel limit exceeded') from None
        except (UnidentifiedImageError, OSError):
            raise ValueError('unsupported image') from None
        image = self.cv.imdecode(self.np.frombuffer(raw, dtype=self.np.uint8), self.cv.IMREAD_COLOR)
        if image is None or image.shape[0] * image.shape[1] > MAX_PIXELS:
            raise ValueError('unsupported image or pixel limit exceeded')
        return image

    def detect_objects(self, raw):
        cv, np = self.cv, self.np
        img = self.decode(raw)
        h, w = img.shape[:2]
        ratio = min(640 / h, 640 / w)
        resized = cv.resize(img, (int(w * ratio), int(h * ratio))).astype(np.float32)
        canvas = np.full((640, 640, 3), 114, dtype=np.float32)
        canvas[:resized.shape[0], :resized.shape[1]] = resized
        self.net.setInput(np.transpose(canvas, (2, 0, 1))[None])
        dets = self.net.forward()[0].copy()
        dets[:, :2] = (dets[:, :2] + self.grids[0]) * self.strides[0]
        dets[:, 2:4] = np.exp(dets[:, 2:4]) * self.strides[0]
        scores = dets[:, 4:5] * dets[:, 5:]
        cls = np.argmax(scores, axis=1)
        confidences = np.max(scores, axis=1)
        boxes = [[float((d[0] - d[2] / 2) / ratio), float((d[1] - d[3] / 2) / ratio), float(d[2] / ratio), float(d[3] / ratio)] for d in dets]
        indices = cv.dnn.NMSBoxesBatched(boxes, confidences.tolist(), cls.tolist(), 0.35, 0.5)
        result = []
        for i in indices[:50]:
            region = _region(boxes[int(i)], w, h)
            if region:
                result.append({'label': COCO[int(cls[i])], 'score': round(float(confidences[i]), 5), 'box': region})
        return result

    def _faces(self, img):
        h, w = img.shape[:2]
        self.face.setInputSize((w, h))
        _, faces = self.face.detect(img)
        return [] if faces is None else faces[:16]

    def match_people(self, raw, gallery):
        image = self.decode(raw)
        enrolled = []
        for entry in gallery:
            reference = self.decode(entry['image'])
            faces = self._faces(reference)
            if len(faces) != 1:
                continue  # enrollment requires exactly one detectable face
            enrolled.append((entry['personRef'], self.recognizer.feature(self.recognizer.alignCrop(reference, faces[0]))))
        h, w = image.shape[:2]
        results = []
        for face in self._faces(image):
            embedding = self.recognizer.feature(self.recognizer.alignCrop(image, face))
            scores = [self.recognizer.match(embedding, feature, self.cv.FaceRecognizerSF_FR_COSINE) for _, feature in enrolled]
            candidates = match_candidates(embedding, [{'personRef': person} for person, _ in enrolled], scores=scores)
            region = _region(face[:4], w, h)
            if region:
                results.append({'label': 'face', 'box': region, 'candidates': candidates, 'decision': 'candidate' if candidates else 'unknown'})
        return results


def create_server(model, host='127.0.0.1', port=19470):
    # No authentication: a non-loopback host is a deliberate choice, and the
    # firewall is then the only access control (same as whisper and kokoro).

    class BoundedServer(ThreadingHTTPServer):
        daemon_threads = True
        max_connections = MAX_CONNECTIONS
        read_timeout = READ_TIMEOUT

        def __init__(self, address, handler):
            super().__init__(address, handler)
            self.slots = threading.BoundedSemaphore(MAX_CONNECTIONS)

        def process_request(self, request, client_address):
            if not self.slots.acquire(blocking=False):
                request.close()  # fixed cap on active sockets/threads, including slow readers
                return
            try:
                super().process_request(request, client_address)
            except BaseException:
                self.slots.release()
                raise

        def process_request_thread(self, request, client_address):
            try:
                super().process_request_thread(request, client_address)
            finally:
                self.slots.release()

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            self.request.settimeout(self.server.read_timeout)
            # A fixed wall-clock deadline closes even a byte-at-a-time connection.
            def expire():
                try:
                    self.request.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
            self.deadline = threading.Timer(self.server.read_timeout, expire)
            self.deadline.daemon = True
            self.deadline.start()
            super().setup()

        def finish(self):
            try:
                super().finish()
            finally:
                self.deadline.cancel()

        def do_GET(self):
            if self.path != '/health':
                self.send_error(404)
                return
            self.reply(200, {'version': 1, 'capabilities': ['objects', 'knownPeople']})

        def do_POST(self):
            if self.path != '/v1/analyze':
                self.send_error(404)
                return
            size = self.headers.get('Content-Length', '')
            if not size.isdecimal() or int(size) > MAX_BODY or int(size) < 1:
                self.reply(413, {'error': 'request too large'})
                return
            try:
                payload = self.rfile.read(int(size))
                if len(payload) != int(size):
                    raise ValueError('truncated request')
                result = analyze_request(json.loads(payload), model)
            except (ValueError, json.JSONDecodeError, socket.timeout, TimeoutError):
                self.reply(400, {'error': 'invalid image request'})
                return
            except Exception:
                self.reply(503, {'error': 'inference unavailable'})
                return
            self.reply(200, result)

        def reply(self, status, value):
            body = json.dumps(value).encode()
            try:
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError, socket.timeout):
                pass

        def log_message(self, format, *args):
            pass  # do not log image-bearing request paths/bodies

    return BoundedServer((host, port), Handler)


def serve(model, host='127.0.0.1', port=19470):
    with create_server(model, host, port) as server:
        server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=19470)
    parser.add_argument('--weights-dir', default=os.path.join(os.path.dirname(__file__), '.models'))
    args = parser.parse_args()
    serve(ImageInference(args.weights_dir), args.host, args.port)
