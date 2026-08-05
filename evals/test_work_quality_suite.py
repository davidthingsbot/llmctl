#!/usr/bin/env python3
import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).with_name("work_quality_suite.py")
spec = importlib.util.spec_from_file_location("work_quality_suite", MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot load {MODULE_PATH}")
suite = importlib.util.module_from_spec(spec)
spec.loader.exec_module(suite)


class WorkQualitySuiteTests(unittest.TestCase):
    def test_weights_total_one_hundred(self):
        tasks = [
            suite.task_structured_protocol(),
            suite.task_bom(),
            suite.task_code_repair(),
            suite.task_code_review(),
            suite.task_protocol_design(),
            suite.task_long_context(),
            suite.task_scope_control(),
            suite.task_timing(),
        ]
        self.assertEqual(sum(grader("")[1] for _, _, _, grader in tasks), 100)

    def test_reference_decoder_passes_all_executable_checks(self):
        candidate = '''
def decode_frame(frame: bytes):
    if len(frame) < 5:
        raise ValueError("short")
    payload_len = int.from_bytes(frame[1:3], "little")
    if len(frame) != 5 + payload_len:
        raise ValueError("length")
    payload = frame[3:3 + payload_len]
    expected = int.from_bytes(frame[-2:], "little")
    if crc16(frame[:-2]) != expected:
        raise ValueError("crc")
    return frame[0], payload
'''
        score, maximum, details = suite.task_code_repair()[3](candidate)
        self.assertEqual((score, maximum), (20, 20), details)

    def test_decoder_with_wrong_endianness_fails(self):
        candidate = '''
def decode_frame(frame: bytes):
    payload_len = int.from_bytes(frame[1:3], "big")
    if len(frame) != 5 + payload_len:
        raise ValueError("length")
    if crc16(frame[:-2]) != int.from_bytes(frame[-2:], "big"):
        raise ValueError("crc")
    return frame[0], frame[3:-2]
'''
        score, maximum, _details = suite.task_code_repair()[3](candidate)
        self.assertLess(score, maximum)


if __name__ == "__main__":
    unittest.main()
