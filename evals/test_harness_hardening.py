"""No model calls: bounded real tools and interrupted stub evaluation runs."""
import contextlib
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

EVALS = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location(name, EVALS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BoundedProcessTests(unittest.TestCase):
    def setUp(self):
        self.runtime = load('eval_runtime')

    def run_python(self, code, **kwargs):
        return self.runtime.bounded_run([sys.executable, '-c', code], **kwargs)

    def test_success_and_nonzero_preserve_both_streams(self):
        for rc in (0, 7):
            result = self.run_python(f'import sys; print("out"); print("err", file=sys.stderr); sys.exit({rc})', timeout=5)
            self.assertEqual((result.returncode, result.stdout, result.stderr), (rc, 'out\n', 'err\n'))

    def test_wall_timeout_even_when_pipes_are_closed(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            self.run_python('import os,time; os.close(1); os.close(2); time.sleep(10)', timeout=0.2)

    def test_output_limit_on_either_stream(self):
        for fd in (1, 2):
            with self.subTest(fd=fd), self.assertRaisesRegex(RuntimeError, 'output limit'):
                self.run_python(f'import os\nwhile True: os.write({fd}, b"x"*8192)', timeout=5, output_limit=4096)

    def test_combined_output_limit(self):
        with self.assertRaisesRegex(RuntimeError, 'output limit'):
            self.run_python('import os; os.write(1, b"x"*3000); os.write(2, b"x"*3000)', timeout=5, output_limit=4096)

    def test_threaded_calls_leave_controller_limits_unchanged(self):
        import resource
        before = resource.getrlimit(resource.RLIMIT_AS)
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: self.run_python('print("ok")', timeout=5), range(2)))
        self.assertTrue(all(result.stdout == 'ok\n' for result in results))
        self.assertEqual(resource.getrlimit(resource.RLIMIT_AS), before)

    def test_memory_and_cpu_limits_are_inherited(self):
        result = self.run_python('import resource; print(resource.getrlimit(resource.RLIMIT_AS)); print(resource.getrlimit(resource.RLIMIT_CPU))', timeout=5, memory_bytes=128*1024*1024)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('(134217728, 134217728)', result.stdout)
        self.assertIn('(5, 5)', result.stdout)
        result = self.run_python('x = bytearray(256*1024*1024)', timeout=5, memory_bytes=128*1024*1024)
        self.assertNotEqual(result.returncode, 0)

    def test_bound_setup_failure_does_not_exec(self):
        with mock.patch.dict(sys.modules, {'resource': None}), mock.patch.object(os, 'execvp') as execute:
            with self.assertRaises(SystemExit) as error, contextlib.redirect_stderr(io.StringIO()):
                self.runtime._bounded_exec(['134217728', '5', 'never-run'])
            self.assertNotEqual(error.exception.code, 0)
            execute.assert_not_called()

    def test_setrlimit_failure_does_not_exec(self):
        import resource
        with mock.patch.object(resource, 'setrlimit', side_effect=OSError('unavailable')), mock.patch.object(os, 'execvp') as execute:
            with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
                self.runtime._bounded_exec(['134217728', '5', 'never-run'])
            execute.assert_not_called()

    @unittest.skipUnless(shutil.which('iverilog') and shutil.which('vvp'), 'iverilog/vvp not installed')
    def test_exact_preserved_runaway_is_contained(self):
        fixture = EVALS / 'diagnostics/verilog-hard-runaway'
        if not (fixture / 'async_fifo.v').exists() or not (fixture / 'tb.v').exists():
            self.skipTest('preserved runaway diagnostic files not available')
        with tempfile.TemporaryDirectory() as tmp:
            binary = str(Path(tmp) / 'sim')
            build = self.runtime.bounded_run(['iverilog', '-g2001', '-o', binary, str(fixture / 'async_fifo.v'), str(fixture / 'tb.v')], timeout=10)
            self.assertEqual(build.returncode, 0, build.stderr)
            try:
                result = self.runtime.bounded_run(['vvp', binary], timeout=8, memory_bytes=128*1024*1024)
            except subprocess.TimeoutExpired:
                return  # Other Icarus versions may spin rather than allocate.
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertNotIn('SUMMARY', result.stdout)


class VerilogHardeningTests(unittest.TestCase):
    def setUp(self):
        self.suite = load('work_quality_suite')

    def exercise(self, lint='', rc=0, output=None):
        for level, name, count in [('easy', 'edge_detect', 6), ('medium', 'sync_fifo', 14), ('hard', 'async_fifo', 4)]:
            calls = []
            def run(args, **kwargs):
                calls.append(args[0])
                if args[0] == 'verilator':
                    return subprocess.CompletedProcess(args, int(bool(lint)), '', lint)
                stdout = output if output is not None else ''.join(f'CHECK {i} PASS\n' for i in range(count)) + 'SUMMARY pass=14 fail=0 got=16 errors=0\n'
                return subprocess.CompletedProcess(args, rc if args[0] == 'vvp' else 0, stdout, 'simulator diagnostic')
            with self.subTest(level=level), mock.patch.object(self.suite.shutil, 'which', return_value='/tool'), mock.patch.object(self.suite.subprocess, 'run', side_effect=run), mock.patch.object(self.suite, 'bounded_run', side_effect=run, create=True):
                score, maximum, details = getattr(self.suite, 'task_verilog_' + level)()[3]('module ' + name + '; endmodule')
                yield calls, score, maximum, details

    def test_explicit_loop_skips_simulation_all_levels(self):
        for calls, score, _, details in self.exercise(lint='%Warning-UNOPTFLAT: Circular combinational logic: wfull'):
            self.assertEqual(calls[0], 'verilator')
            self.assertNotIn('vvp', calls)
            self.assertEqual(score, 0)
            self.assertFalse(details['ran_to_completion'])
            self.assertIn('UNOPTFLAT', '\n'.join(details['lint_first']))

    def test_other_lint_warnings_keep_existing_behaviour_credit(self):
        for calls, score, maximum, details in self.exercise(lint='%Warning-BLKSEQ: blocking assignment'):
            self.assertEqual(calls, ['verilator', 'iverilog', 'vvp'])
            self.assertGreater(score, 0)
            self.assertLess(score, maximum)
            self.assertFalse(details['lint_clean'])

    def test_aborted_simulator_cannot_earn_check_credit(self):
        for _, score, _, details in self.exercise(rc=-6):
            self.assertEqual(score, 0)
            self.assertFalse(details['ran_to_completion'])
            self.assertEqual(details['simulator_returncode'], -6)

    def test_missing_summary_or_testbench_timeout_is_failure(self):
        for output in ('CHECK 0 PASS\n', 'CHECK 0 PASS\nSUMMARY pass=1 fail=0 TIMEOUT\n'):
            for _, score, _, details in self.exercise(output=output):
                self.assertEqual(score, 0)
                self.assertFalse(details['ran_to_completion'])

    def test_tool_timeouts_and_output_overflow_fail_all_levels(self):
        for level, name in [('easy', 'edge_detect'), ('medium', 'sync_fifo'), ('hard', 'async_fifo')]:
            for stage in ('verilator', 'iverilog', 'vvp'):
                for error in (subprocess.TimeoutExpired(stage, 1), RuntimeError('tool output limit exceeded')):
                    calls = []
                    def run(args, **kwargs):
                        calls.append(args[0])
                        if args[0] == stage:
                            raise error
                        return subprocess.CompletedProcess(args, 0, '', '')
                    with self.subTest(level=level, stage=stage, error=error), mock.patch.object(self.suite.shutil, 'which', return_value='/tool'), mock.patch.object(self.suite, 'bounded_run', side_effect=run):
                        score, _, details = getattr(self.suite, 'task_verilog_' + level)()[3]('module ' + name + '; endmodule')
                        self.assertEqual(score, 0)
                        self.assertFalse(details['ran_to_completion'])
                        self.assertEqual(calls[-1], stage)

    @unittest.skipUnless(shutil.which('verilator'), 'verilator not installed')
    def test_actual_loop_lint_blocks_runaway(self):
        fixture = EVALS / 'diagnostics/verilog-hard-runaway/async_fifo.v'
        if not fixture.exists():
            self.skipTest('preserved runaway diagnostic file not available')
        # Require the bounded helper before invoking the formerly unsafe grader.
        self.assertTrue(hasattr(self.suite, 'bounded_run'))
        score, _, details = self.suite.task_verilog_hard()[3](fixture.read_text())
        self.assertEqual(score, 0, details)
        self.assertIn('UNOPTFLAT', '\n'.join(details['lint_first']))
        self.assertFalse(details['ran_to_completion'])


class CheckpointTests(unittest.TestCase):
    def test_atomic_write_failure_preserves_previous_checkpoint(self):
        runtime = load('eval_runtime')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'result.json'
            runtime.atomic_write_json(path, {'status': 'partial', 'tasks': ['saved']})
            with mock.patch.object(runtime.os, 'replace', side_effect=OSError('disk error')):
                with self.assertRaises(OSError):
                    runtime.atomic_write_json(path, {'status': 'complete'})
            self.assertEqual(json.loads(path.read_text()), {'status': 'partial', 'tasks': ['saved']})
            self.assertEqual(list(Path(tmp).iterdir()), [path])

    def exercise(self, module_name, stop=None, first_score=2, retry_score=10, grader_error=False):
        suite = load(module_name)
        with tempfile.TemporaryDirectory() as tmp, contextlib.ExitStack() as stack:
            output = Path(tmp) / 'result.json'
            key = Path(tmp) / 'key'
            key.write_text('stub-key')
            output.write_text('{"status":"complete","stale":true}')
            argv = ['suite', '--url', 'http://unused', '--model', 'stub', '--key-file', str(key), '--output', str(output), '--strip-reasoning']
            stack.enter_context(mock.patch.object(sys, 'argv', argv))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            grade_calls = 0
            def grade(text):
                nonlocal grade_calls
                if not text:
                    return 0, 10, {}
                grade_calls += 1
                saved = json.loads(output.read_text())
                self.assertEqual(saved['status'], 'partial')
                self.assertFalse(saved['complete'])
                row = saved['tasks'][-1]
                field = 'retry_response' if grade_calls == 2 else 'response'
                self.assertEqual(row[field], text)
                self.assertEqual(row['raw_' + field], '<think>raw thought</think>\n' + text)
                if grade_calls == 2:
                    self.assertEqual(row['score_first'], first_score)
                    self.assertEqual(row['score'], first_score)
                if stop == grade_calls:
                    self.assertEqual(saved['cost']['completion_tokens'], 3 * grade_calls)
                    raise KeyboardInterrupt('grading interrupted')
                if grader_error:
                    raise ValueError('grader failed')
                return (first_score if grade_calls == 1 else retry_score), 10, {'check': False}
            task = ('stub_task', 'prompt', 100, grade)
            if module_name == 'deep_reasoning_suite':
                stack.enter_context(mock.patch.object(suite, 'tasks', return_value=[task, ('next', 'prompt', 100, grade)]))
            else:
                names = ['structured_protocol', 'bom', 'code_repair', 'code_review', 'protocol_design', 'long_context', 'scope_control', 'timing']
                for i, name in enumerate(names):
                    stack.enter_context(mock.patch.object(suite, 'task_' + name, return_value=task if i == 0 else (f'next{i}', 'prompt', 100, grade)))
            requests = 0
            def request(*args, **kwargs):
                nonlocal requests
                requests += 1
                if requests > 2 or (grader_error and requests > 1):
                    saved = json.loads(output.read_text())
                    self.assertEqual(saved['tasks'][0]['status'], 'complete')
                    if stop == 'next':
                        raise KeyboardInterrupt('next request interrupted')
                return '<think>raw thought</think>\n' + ('first' if requests == 1 else 'retry'), {'completion_tokens': 3}, 1.0
            stack.enter_context(mock.patch.object(suite, 'request', side_effect=request))
            if stop is not None:
                with self.assertRaises(KeyboardInterrupt):
                    suite.main()
            else:
                suite.main()
            saved = json.loads(output.read_text())
            self.assertEqual(saved['status'], 'partial' if stop else 'complete')
            self.assertEqual(saved['complete'], stop is None)
            self.assertEqual(saved['max_score'], 20 if module_name == 'deep_reasoning_suite' else 80)
            self.assertEqual(saved['score'], sum(row['score'] for row in saved['tasks']))
            return saved

    def test_first_and_retry_answers_survive_interruption_both_suites(self):
        for module in ('work_quality_suite', 'deep_reasoning_suite'):
            for stop in (1, 2, 'next'):
                with self.subTest(module=module, stop=stop):
                    self.exercise(module, stop=stop)

    def test_final_schema_totals_and_retry_credit_are_preserved(self):
        for module in ('work_quality_suite', 'deep_reasoning_suite'):
            for first, retry, expected in [(2, 10, 7), (8, 10, 8), (2, 0, 2)]:
                with self.subTest(module=module, first=first, retry=retry):
                    result = self.exercise(module, first_score=first, retry_score=retry)
                    row = result['tasks'][0]
                    self.assertEqual((row['score_first'], row['score_retry'], row['score']), (first, retry, expected))
                    self.assertIn('cost', result)
                    self.assertTrue(result['retry_enabled'])
                    self.assertEqual(row['response'], 'first')
                    self.assertEqual(row['retry_response'], 'retry')

    def test_grader_exception_preserves_answer(self):
        for module in ('work_quality_suite', 'deep_reasoning_suite'):
            with self.subTest(module=module):
                result = self.exercise(module, grader_error=True)
                self.assertEqual(result['tasks'][0]['response'], 'first')
                self.assertIn('ValueError', result['tasks'][0]['error'])


if __name__ == '__main__':
    unittest.main()
