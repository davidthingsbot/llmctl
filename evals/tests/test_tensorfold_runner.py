import ast,pathlib,subprocess,sys,unittest
ROOT=pathlib.Path(__file__).resolve().parents[2]
class TensorFoldRunnerTests(unittest.TestCase):
    def test_vision_wrapper_can_import_sibling_modules(self):
        tree=ast.parse((ROOT/'evals/diagnostics/run_tensorfold_trial.py').read_text())
        wrapper=next(ast.literal_eval(n.value) for n in ast.walk(tree) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='wrapper' for t in n.targets))
        r=subprocess.run([sys.executable,'-c',wrapper,'http://127.0.0.1:18888/v1/chat/completions',str(ROOT/'evals/vision_suite.py'),'--help'],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
    def test_resume_option_is_available(self):
        r=subprocess.run([sys.executable,str(ROOT/'evals/diagnostics/run_tensorfold_trial.py'),'--help'],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertIn('--resume',r.stdout)

# All runner activity below is confined to temporary receipts and mocked processes.
import builtins
import contextlib
import importlib.util
import io
import json
import tempfile
from unittest import mock


def load_diagnostic(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'evals/diagnostics' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = load_diagnostic('run_tensorfold_trial')
guard = load_diagnostic('tensorfold_trial_memguard')
continuation = load_diagnostic('continue_tensorfold_context')


def receipt_files(out):
    return {str(p.relative_to(out)): p.read_bytes() for p in out.rglob('*')
            if p.is_file() and p.relative_to(out).parts[0] != 'attempt-backups'}


class TensorFoldReliabilityTests(unittest.TestCase):
    def test_memguard_retries_kill_errors_and_verifies_termination(self):
        for failure in [subprocess.CompletedProcess([], 1, '', 'daemon unavailable'),
                        subprocess.TimeoutExpired('docker', 20), OSError('docker unavailable'),
                        subprocess.CompletedProcess([], 0, '', '')]:
            with self.subTest(failure=failure):
                calls = []
                sleeps = []
                kills = 0

                def docker(args, **kwargs):
                    nonlocal kills
                    calls.append(args)
                    if args[1] == 'kill':
                        kills += 1
                        if kills == 1:
                            if isinstance(failure, Exception):
                                raise failure
                            return failure
                        return subprocess.CompletedProcess(args, 0, '', '')
                    # A successful kill alone is not proof of termination.
                    return subprocess.CompletedProcess(args, 0, 'true' if kills == 1 else 'false', '')

                def sleep(seconds):
                    sleeps.append(seconds)
                    if len(sleeps) > 3:
                        self.fail('guard never verified termination')

                with mock.patch.object(sys, 'argv', ['guard', '--container', 'trial']), \
                     mock.patch.object(guard.pathlib.Path, 'read_text', side_effect=[
                         'MemAvailable: 1 kB', *['MemAvailable: 99999999 kB'] * 5]), \
                     mock.patch.object(guard.subprocess, 'run', side_effect=docker), \
                     mock.patch.object(guard.time, 'sleep', side_effect=sleep), \
                     contextlib.redirect_stdout(io.StringIO()):
                    with self.assertRaises(SystemExit) as stopped:
                        guard.main()
                self.assertEqual(stopped.exception.code, 1)
                self.assertEqual(kills, 2, 'trip must stay latched after memory recovers')
                self.assertTrue(sleeps)
                self.assertIn('inspect', calls[-1])

    def test_memguard_distinguishes_absent_target_from_unavailable_docker(self):
        calls = []
        sleeps = []

        def docker(args, **kwargs):
            calls.append(args)
            if args[1:3] == ['container', 'ls']:
                # First listing fails: absence has not been established.
                return subprocess.CompletedProcess(args, 0 if sleeps else 1, '', 'unavailable')
            return subprocess.CompletedProcess(args, 1, '', 'No such container: trial')

        def sleep(seconds):
            sleeps.append(seconds)
            if len(sleeps) > 3:
                self.fail('guard did not recognize verified absence')

        with mock.patch.object(sys, 'argv', ['guard', '--container', 'trial']), \
             mock.patch.object(guard.pathlib.Path, 'read_text', return_value='MemAvailable: 1 kB'), \
             mock.patch.object(guard.subprocess, 'run', side_effect=docker), \
             mock.patch.object(guard.time, 'sleep', side_effect=sleep), \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                guard.main()
        self.assertEqual(len(sleeps), 1)
        self.assertEqual(sum(c[1:3] == ['container', 'ls'] for c in calls), 2)

    def test_memguard_survives_verification_timeout_and_present_target_inventory(self):
        inspections = 0
        sleeps = []

        def docker(args, **kwargs):
            nonlocal inspections
            if 'inspect' in args:
                inspections += 1
                if inspections == 1:
                    raise subprocess.TimeoutExpired(args, 20)
                return subprocess.CompletedProcess(args, 1, '', 'inspect failed')
            if args[1:3] == ['container', 'ls']:
                rows = [{'ID': 'a' * 64, 'Names': 'trial'}] if inspections == 2 else []
                return subprocess.CompletedProcess(args, 0, '\n'.join(map(json.dumps, rows)), '')
            return subprocess.CompletedProcess(args, 1, '', 'kill failed')

        def sleep(seconds):
            sleeps.append(seconds)
            if len(sleeps) > 3:
                self.fail('guard failed to verify absence')

        with mock.patch.object(sys, 'argv', ['guard', '--container', 'trial']), \
             mock.patch.object(guard.pathlib.Path, 'read_text', return_value='missing memory sample'), \
             mock.patch.object(guard.subprocess, 'run', side_effect=docker), \
             mock.patch.object(guard.time, 'sleep', side_effect=sleep), \
             contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(SystemExit):
                guard.main()
        self.assertEqual(len(sleeps), 2)

    def seed_resume(self, out):
        out.mkdir()
        (out / 'status.json').write_text(json.dumps({
            'model': runner.MODEL, 'recipe_commit': 'recipe', 'status': 'blocked',
            'error': 'old failure', 'stages': {}}))
        for name in ['text-smoke.json', 'deep_reasoning_suite.json', 'work_quality_suite.json',
                     'vision.json', 'concurrency-high.json', 'concurrency-off.json',
                     'publisher-repo-bench.log', 'long-100000.json', 'fixtures/manifest.json',
                     'nested/partial/receipt.bin', 'nested/attempt-backups/receipt.json']:
            path = out / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'pre-existing partial or failed receipt\x00')
        (out / 'attempt-backups/older').mkdir(parents=True)
        (out / 'attempt-backups/older/sentinel').write_text('historical')

    @contextlib.contextmanager
    def runner_environment(self, tmp, out, lock_error=False):
        def open_local(path, mode='r', *args, **kwargs):
            if str(path).endswith('experiment-sequence.lock'):
                return builtins.open(tmp / 'experiment.lock', mode, *args, **kwargs)
            if str(path).endswith('prepare.lock'):
                raise RuntimeError('mock preparation stop')
            self.fail('unexpected file access: ' + str(path))

        with mock.patch.object(sys, 'argv', ['runner', '--resume', str(out)]), \
             mock.patch.object(runner, 'open', side_effect=open_local, create=True), \
             mock.patch.object(runner.fcntl, 'flock', side_effect=BlockingIOError('locked') if lock_error else None), \
             mock.patch.object(runner, 'command', return_value=subprocess.CompletedProcess([], 0, 'recipe\n', '')), \
             mock.patch.object(runner.subprocess, 'run', side_effect=AssertionError('no workloads')), \
             mock.patch.object(runner.urllib.request, 'urlopen', side_effect=AssertionError('no requests')), \
             contextlib.redirect_stdout(io.StringIO()):
            yield

    def test_resume_archives_every_receipt_recursively_in_unique_attempts(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = pathlib.Path(directory)
            out = tmp / 'run'
            self.seed_resume(out)
            for _ in range(2):
                before = receipt_files(out)
                existing = set((out / 'attempt-backups').iterdir())
                with self.runner_environment(tmp, out):
                    with self.assertRaisesRegex(RuntimeError, 'mock preparation stop'):
                        runner.main()
                new = set((out / 'attempt-backups').iterdir()) - existing
                self.assertEqual(len(new), 1, 'resume must snapshot all artifacts before any write')
                backup = new.pop()
                self.assertEqual(receipt_files(backup), before)
                self.assertFalse((backup / 'attempt-backups').exists())
                if _ == 0:
                    first_backup, first_bytes = backup, receipt_files(backup)
            self.assertEqual(receipt_files(first_backup), first_bytes)
            self.assertEqual((out / 'attempt-backups/older/sentinel').read_text(), 'historical')

    def test_resume_lock_failure_cannot_write_or_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = pathlib.Path(directory)
            out = tmp / 'run'
            self.seed_resume(out)
            before = {str(p.relative_to(out)): p.read_bytes() for p in out.rglob('*') if p.is_file()}
            with self.runner_environment(tmp, out, lock_error=True):
                with self.assertRaises(BlockingIOError):
                    runner.main()
            self.assertEqual({str(p.relative_to(out)): p.read_bytes() for p in out.rglob('*') if p.is_file()}, before)
            missing = tmp / 'missing'
            with self.runner_environment(tmp, missing, lock_error=True):
                with self.assertRaises(BlockingIOError):
                    runner.main()
            self.assertFalse(missing.exists())

    def test_resume_snapshot_failure_aborts_before_overwriting_receipts(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp = pathlib.Path(directory)
            out = tmp / 'run'
            self.seed_resume(out)
            before = receipt_files(out)
            with self.runner_environment(tmp, out), \
                 mock.patch.object(runner.shutil, 'copytree', side_effect=OSError('snapshot failed')):
                with self.assertRaisesRegex(OSError, 'snapshot failed'):
                    runner.main()
            self.assertEqual(receipt_files(out), before)

    def seed_continuation(self, out):
        def write(name, data):
            (out / name).write_text(json.dumps(data))
        write('status.json', {'status': 'blocked', 'step': 'long-context-retrieval',
                             'error': 'retrieval failed at 100000', 'stages': {}})
        for name in ['deep_reasoning_suite.json', 'work_quality_suite.json', 'vision.json']:
            write(name, {'status': 'complete', 'complete': True, 'tasks': [{'status': 'complete'}]})
        for name in ['concurrency-high.json', 'concurrency-off.json']:
            write(name, {'levels': [1, 2, 4], 'results': [{'streams': n, 'failed': 0} for n in [1, 2, 4]]})
        (out / 'publisher-repo-bench.log').write_text(
            '== local-upstream-script\n' + 'prefill 812 tok: 0.70 s 1160 tok/s TTFT 0.71 s (1 run, each 0.70 s)\n' * 4 +
            'decode code greedy : 60.4 tok/s (median of 5)\ndecode chat sampled: 65.8 tok/s (median of 5)\n')
        for target in [32000, 100000]:
            key = 'a' * 32
            write(f'long-{target}.json', {'target': target, 'expected': key, 'correct': target == 32000,
                  'response': {'choices': [{'message': {'content': key if target == 32000 else 'Archive key: ' + key}}]}})

    @contextlib.contextmanager
    def continuation_environment(self, out, lock_error=False):
        def post(path, payload=None):
            if path == '/health':
                return {'ok': True}
            if path == '/tokenize':
                return {'count': 1000000}
            key = payload['messages'][0]['content'].splitlines()[0].split(': ')[1]
            return {'choices': [{'message': {'content': key}}]}
        with mock.patch.object(continuation, 'OUT', out), \
             mock.patch.object(continuation, 'open', side_effect=lambda *a, **kw: builtins.open(out.parent / 'experiment.lock', 'a'), create=True), \
             mock.patch.object(continuation.fcntl, 'flock', side_effect=BlockingIOError('locked') if lock_error else None), \
             mock.patch.object(continuation, 'memory', return_value={}) as memory, \
             mock.patch.object(continuation, 'post', side_effect=post) as requests, \
             mock.patch.object(continuation, 'command', side_effect=AssertionError('no subprocesses')), \
             contextlib.redirect_stdout(io.StringIO()):
            yield memory, requests

    def test_continuation_rerun_fails_closed_and_retains_predecessor(self):
        with tempfile.TemporaryDirectory() as directory:
            out = pathlib.Path(directory) / 'run'
            out.mkdir()
            self.seed_continuation(out)
            original = receipt_files(out)
            with self.continuation_environment(out):
                continuation.main()
            self.assertEqual(json.loads((out / 'status.json').read_text())['status'], 'complete_with_format_failure')
            self.assertEqual(json.loads((out / 'status-before-context-extension.json').read_text()), json.loads(original['status.json']))
            backups = list((out / 'attempt-backups').iterdir()) if (out / 'attempt-backups').exists() else []
            self.assertEqual(len(backups), 1, 'extension must retain immutable predecessor artifacts')
            self.assertEqual(receipt_files(backups[0]), original)
            before = receipt_files(out)
            with self.continuation_environment(out) as (memory, requests):
                with self.assertRaises(RuntimeError):
                    continuation.main()
                memory.assert_not_called()
                requests.assert_not_called()
            self.assertEqual(receipt_files(out), before)
            self.assertEqual(receipt_files(backups[0]), original)

    def test_failed_extension_retains_original_failure_and_immutable_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            out = pathlib.Path(directory) / 'run'
            out.mkdir()
            self.seed_continuation(out)
            before = receipt_files(out)
            with self.continuation_environment(out) as (memory, requests):
                memory.side_effect = RuntimeError('mock memory gate failed')
                with self.assertRaisesRegex(RuntimeError, 'mock memory gate failed'):
                    continuation.main()
                requests.assert_not_called()
            self.assertEqual((out / 'status.json').read_bytes(), before['status.json'])
            self.assertEqual(json.loads((out / 'context-extension-status.json').read_text())['status'], 'blocked')
            self.assertEqual(receipt_files(next((out / 'attempt-backups').iterdir())), before)

    def test_continuation_rejects_unrelated_or_incomplete_predecessors_without_writes(self):
        cases = [
            ('status.json', lambda d: d.update(step='vision')),
            ('status.json', lambda d: d.update(error='out of memory')),
            ('status.json', lambda d: d.update(status='evaluating')),
            ('deep_reasoning_suite.json', lambda d: d.update(complete=False)),
            ('work_quality_suite.json', lambda d: d['tasks'][0].update(error='API error')),
            ('work_quality_suite.json', lambda d: d['tasks'][0].update(retry_error='API error')),
            ('work_quality_suite.json', lambda d: d.update(status='partial')),
            ('vision.json', lambda d: d.update(status='partial')),
            ('vision.json', lambda d: d['tasks'][0].update(status='error')),
            ('concurrency-high.json', lambda d: d['results'].pop()),
            ('concurrency-off.json', lambda d: d['results'][1].update(failed=1)),
            ('concurrency-off.json', lambda d: d['results'][1].pop('failed')),
            ('long-32000.json', lambda d: d.update(correct=False)),
            ('long-100000.json', lambda d: d.update(correct=True)),
            ('long-100000.json', lambda d: d.update(target=200000)),
            ('long-100000.json', lambda d: d['response']['choices'][0]['message'].update(content='b' * 32)),
            ('long-100000.json', lambda d: d['response']['choices'][0]['message'].update(content=('a' * 32 + ' ') * 2)),
            ('long-100000.json', lambda d: d['response']['choices'][0]['message'].update(content='a' * 32)),
            ('publisher-repo-bench.log', None),
            ('publisher-repo-bench.log', '== local-upstream-script\nprefill incomplete\n'),
            ('publisher-repo-bench.log', 'Traceback: benchmark failed\n'),
            ('vision.json', None),
        ]
        for filename, mutate in cases:
            with self.subTest(filename=filename, mutation=mutate), tempfile.TemporaryDirectory() as directory:
                out = pathlib.Path(directory) / 'run'
                out.mkdir()
                self.seed_continuation(out)
                path = out / filename
                if mutate is None:
                    path.unlink()
                elif isinstance(mutate, str):
                    path.write_text(mutate)
                else:
                    value = json.loads(path.read_text())
                    mutate(value)
                    path.write_text(json.dumps(value))
                before = receipt_files(out)
                with self.continuation_environment(out) as (memory, requests):
                    with self.assertRaises((RuntimeError, ValueError, FileNotFoundError)):
                        continuation.main()
                    memory.assert_not_called()
                    requests.assert_not_called()
                self.assertEqual(receipt_files(out), before)
                self.assertFalse((out / 'attempt-backups').exists())

    def test_continuation_existing_artifacts_and_lock_failure_are_read_only(self):
        for existing in ['context-extension-status.json', 'status-before-context-extension.json',
                         'long-200000.json', 'long-500000.json', 'long-900000.json', None]:
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as directory:
                out = pathlib.Path(directory) / 'run'
                out.mkdir()
                self.seed_continuation(out)
                if existing:
                    (out / existing).write_text('{"status":"complete","retained":true}')
                before = receipt_files(out)
                with self.continuation_environment(out, lock_error=existing is None) as (memory, requests):
                    with self.assertRaises((RuntimeError, BlockingIOError)):
                        continuation.main()
                    memory.assert_not_called()
                    requests.assert_not_called()
                self.assertEqual(receipt_files(out), before)


if __name__ == '__main__':
    unittest.main()
