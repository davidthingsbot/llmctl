#!/usr/bin/env python3
import importlib.util
import shutil
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



COBS_REFERENCE = """```python
def cobs_encode(data):
    out = bytearray(); run = bytearray()
    for b in data:
        if b == 0:
            out.append(len(run)+1); out.extend(run); run = bytearray()
        else:
            run.append(b)
            if len(run) == 254:
                out.append(255); out.extend(run); run = bytearray()
    out.append(len(run)+1); out.extend(run)
    return bytes(out)

def cobs_decode(data):
    out = bytearray(); i = 0; n = len(data)
    if n == 0: raise ValueError("empty")
    while i < n:
        code = data[i]
        if code == 0: raise ValueError("zero")
        i += 1; end = i + code - 1
        if end > n: raise ValueError("overrun")
        chunk = data[i:end]
        if 0 in chunk: raise ValueError("zero")
        out.extend(chunk); i = end
        if code != 255 and i < n: out.append(0)
    return bytes(out)
```"""

REASSEMBLER_REFERENCE = r"""```python
class Reassembler:
    def __init__(self):
        self.buf = bytearray()

    def feed(self, chunk):
        self.buf.extend(chunk)
        out = []
        while True:
            i = self.buf.find(b"\xaa\x55")
            if i < 0:
                break
            if i:
                del self.buf[:i]
            if len(self.buf) < 4:
                break
            length = int.from_bytes(self.buf[2:4], "little")
            if length > 4096:
                del self.buf[:2]
                continue
            if len(self.buf) < 5 + length:
                break
            payload = bytes(self.buf[4:4+length])
            check = self.buf[4+length]
            x = 0
            for b in payload:
                x ^= b
            if x == check:
                out.append(payload)
                del self.buf[:5+length]
            else:
                del self.buf[:2]
        return out
```"""


class ExtendedTaskTest(unittest.TestCase):
    """A grader that rejects a correct answer is worse than no task at all."""

    def test_cobs_reference_scores_full(self):
        _, _, _, grade = suite.task_cobs_codec()
        score, maximum, _ = grade(COBS_REFERENCE)
        self.assertEqual(score, maximum)

    def test_cobs_boundary_bug_loses_points_without_collapsing(self):
        _, _, _, grade = suite.task_cobs_codec()
        broken = COBS_REFERENCE.replace("if len(run) == 254:", "if len(run) == 255:")
        score, maximum, details = grade(broken)
        self.assertLess(score, maximum)
        self.assertGreater(score, 0)
        self.assertFalse(details["boundary_roundtrip"])

    def test_reassembler_reference_scores_full(self):
        _, _, _, grade = suite.task_stream_reassembler()
        score, maximum, _ = grade(REASSEMBLER_REFERENCE)
        self.assertEqual(score, maximum)

    def test_reassembler_must_resync_after_bad_checksum(self):
        _, _, _, grade = suite.task_stream_reassembler()
        broken = REASSEMBLER_REFERENCE.replace(
            "            else:\n                del self.buf[:2]",
            "            else:\n                self.buf = bytearray()")
        score, maximum, details = grade(broken)
        self.assertLess(score, maximum)
        self.assertFalse(details["resync_after_bad_check"])

    def test_extended_tasks_are_opt_in(self):
        self.assertNotIn("cobs_codec", {t[0] for t in [
            suite.task_structured_protocol(), suite.task_bom(), suite.task_code_repair(),
            suite.task_code_review(), suite.task_protocol_design(), suite.task_long_context(),
            suite.task_scope_control(), suite.task_timing()]})



FIFO_REFERENCE = """```verilog
module sync_fifo #(parameter WIDTH = 8, parameter DEPTH = 4)
  (input clk, input rst_n,
   input wr_en, input [WIDTH-1:0] din,
   input rd_en, output reg [WIDTH-1:0] dout,
   output full, output empty);

  localparam AW = $clog2(DEPTH);
  reg [WIDTH-1:0] mem [0:DEPTH-1];
  reg [AW:0] wptr, rptr;

  assign empty = (wptr == rptr);
  assign full  = (wptr[AW] != rptr[AW]) && (wptr[AW-1:0] == rptr[AW-1:0]);

  always @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      wptr <= 0;
      rptr <= 0;
      dout <= 0;
    end else begin
      if (wr_en && !full) begin
        mem[wptr[AW-1:0]] <= din;
        wptr <= wptr + 1'b1;
      end
      if (rd_en && !empty) begin
        dout <= mem[rptr[AW-1:0]];
        rptr <= rptr + 1'b1;
      end
    end
  end
endmodule
```"""

KERNEL_REFERENCE = """```cuda
__global__ void block_sum(const float* in, float* out, int n) {
    extern __shared__ float sdata[];
    unsigned int tid = threadIdx.x;
    unsigned int i = blockIdx.x * blockDim.x + threadIdx.x;
    sdata[tid] = (i < n) ? in[i] : 0.0f;
    __syncthreads();
    for (unsigned int s = blockDim.x / 2; s > 0; s >>= 1) {
        if (tid < s) sdata[tid] += sdata[tid + s];
        __syncthreads();
    }
    if (tid == 0) out[blockIdx.x] = sdata[0];
}
```"""


class DomainTaskTest(unittest.TestCase):
    """Verilog and CUDA tasks, graded by real toolchains where present.

    These skip rather than fail when a toolchain is absent: a machine without
    iverilog must not report a model as broken.
    """

    def test_extract_code_handles_any_language_fence(self):
        # A ```verilog fence used to fall through the regex entirely, handing the
        # backticks to the parser and scoring a correct answer zero.
        self.assertTrue(suite.extract_code("```verilog\nmodule m; endmodule\n```")
                        .startswith("module"))
        self.assertTrue(suite.extract_code("```cuda\n__global__ void k(){}\n```")
                        .startswith("__global__"))
        self.assertTrue(suite.extract_code("```python\nx = 1\n```").startswith("x ="))

    @unittest.skipUnless(shutil.which("iverilog") and shutil.which("vvp"),
                         "iverilog not installed")
    def test_verilog_reference_scores_full(self):
        _, _, _, grade = suite.task_verilog_fifo()
        score, maximum, details = grade(FIFO_REFERENCE)
        self.assertEqual(score, maximum, details)

    @unittest.skipUnless(shutil.which("iverilog") and shutil.which("vvp"),
                         "iverilog not installed")
    def test_verilog_missing_full_flag_loses_behaviour_points(self):
        _, _, _, grade = suite.task_verilog_fifo()
        broken = FIFO_REFERENCE.replace(
            "assign full  = (wptr[AW] != rptr[AW]) && (wptr[AW-1:0] == rptr[AW-1:0]);",
            "assign full  = 1'b0;")
        score, maximum, details = grade(broken)
        self.assertLess(score, maximum)
        self.assertFalse(details["full_at_depth"])

    @unittest.skipUnless(shutil.which("verilator"), "verilator not installed")
    def test_verilog_blocking_assignment_is_caught_by_lint_only(self):
        # It simulates correctly and would still be broken silicon.
        _, _, _, grade = suite.task_verilog_fifo()
        broken = FIFO_REFERENCE.replace("wptr <= wptr + 1'b1;", "wptr = wptr + 1'b1;")
        _, _, details = grade(broken)
        self.assertFalse(details["lint_clean"])

    @unittest.skipUnless(shutil.which("nvcc"), "nvcc not installed")
    def test_cuda_reference_compiles_and_scores_full(self):
        _, _, _, grade = suite.task_cuda_reduction()
        score, maximum, details = grade(KERNEL_REFERENCE)
        if details.get("gpu") == "unavailable":
            self.skipTest("GPU busy serving a model")
        self.assertEqual(score, maximum, details)

    @unittest.skipUnless(shutil.which("nvcc"), "nvcc not installed")
    def test_cuda_missing_bounds_guard_is_caught(self):
        _, _, _, grade = suite.task_cuda_reduction()
        broken = KERNEL_REFERENCE.replace("sdata[tid] = (i < n) ? in[i] : 0.0f;",
                                          "sdata[tid] = in[i];")
        score, maximum, details = grade(broken)
        if details.get("gpu") == "unavailable":
            self.skipTest("GPU busy serving a model")
        self.assertLess(score, maximum)

    def test_barrier_in_thread_conditional_detected_textually(self):
        divergent = "if (tid < s) { sdata[tid] += sdata[tid + s]; __syncthreads(); }"
        fine = "if (tid < s) sdata[tid] += sdata[tid + s];\n__syncthreads();"
        self.assertTrue(suite._barrier_inside_thread_conditional(divergent))
        self.assertFalse(suite._barrier_inside_thread_conditional(fine))


if __name__ == "__main__":
    unittest.main()
