"""Small, shared safety primitives for the evaluation harnesses."""
import json
import math
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import tempfile
import time


# Per tool process, independent of the controller's own cgroup/memory budget.
VERILOG_MEMORY_BYTES = 512 * 1024 * 1024
TOOL_OUTPUT_BYTES = 1024 * 1024


def _bounded_exec(args):
    """Set hard limits in a fresh interpreter, then exec; never run unbounded."""
    try:
        import resource
        memory, cpu = map(int, args[:2])
        for kind, limit in ((resource.RLIMIT_AS, memory),
                            (resource.RLIMIT_CPU, cpu), (resource.RLIMIT_CORE, 0)):
            resource.setrlimit(kind, (limit, limit))
            if resource.getrlimit(kind) != (limit, limit):
                raise RuntimeError('resource limit was not applied')
    except Exception as exc:
        print(f'resource bounds unavailable: {type(exc).__name__}: {exc}', file=sys.stderr)
        raise SystemExit(125)
    os.execvp(args[2], args[2:])


def bounded_run(args, *, timeout, memory_bytes=VERILOG_MEMORY_BYTES,
                output_limit=TOOL_OUTPUT_BYTES):
    """Bound address space, CPU/wall time and combined captured output.

    No preexec_fn: graders can be called by multithreaded controllers. Children
    inherit the limits and a new process group allows cleanup of tool helpers.
    This is resource containment for Verilog tools, not a hostile-code sandbox.
    """
    if os.name != 'posix' or timeout <= 0 or memory_bytes <= 0 or output_limit <= 0:
        raise RuntimeError('resource bounds unavailable or invalid')
    command = [sys.executable, str(Path(__file__).resolve()),
               str(memory_bytes), str(max(1, math.ceil(timeout))), *map(str, args)]
    deadline = time.monotonic() + timeout
    streams = [bytearray(), bytearray()]
    with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          start_new_session=True) as process:
        try:
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ, 0)
                selector.register(process.stderr, selectors.EVENT_READ, 1)
                while selector.get_map() or process.poll() is None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(args, timeout,
                                                        bytes(streams[0]), bytes(streams[1]))
                    for key, _ in selector.select(min(remaining, 0.1)):
                        chunk = os.read(key.fileobj.fileno(), 65536)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        if sum(map(len, streams)) + len(chunk) > output_limit:
                            raise RuntimeError(f'tool output limit exceeded ({output_limit} bytes)')
                        streams[key.data].extend(chunk)
            result = subprocess.CompletedProcess(args, process.wait(),
                        *(data.decode('utf-8', errors='replace') for data in streams))
            if result.returncode == 125:
                raise RuntimeError(result.stderr.strip() or 'resource bounds unavailable')
            return result
        finally:
            # Also reap descendants which kept pipes open or survived the driver.
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()


def atomic_write_json(path, value):
    """Keep either the previous complete checkpoint or the new one on disk."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.' + path.name + '.', delete=False) as handle:
            temporary = handle.name
            json.dump(value, handle, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


if __name__ == '__main__':
    _bounded_exec(sys.argv[1:])
