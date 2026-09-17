"""Adapter tests with a fake upstream launcher and Docker; never starts GPUs."""
import os
import pathlib
import subprocess
import tempfile
import unittest

ADAPTER = pathlib.Path(__file__).resolve().parents[1] / 'scripts/glm53-exl3-tp2.sh'

class AdapterTest(unittest.TestCase):
    def test_passes_identity_and_auth_and_waits_for_container(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp)
            launch = p / 'start.sh'
            launch.write_text('#!/bin/bash\nset -eu\n[[ "$1" == start ]]\n[[ "$SERVED_MODEL_NAME" == GLM-5.3-Flash-EXL3 ]]\n[[ "$PORT" == 8005 ]]\n[[ "$VLLM_API_KEY" == test-only-key ]]\n')
            launch.chmod(0o755)
            docker = p / 'docker'
            docker.write_text('#!/bin/bash\n[[ "$*" == "wait vllm_node" ]] || exit 8\nprintf "0\\n"\n')
            docker.chmod(0o755)
            env = dict(os.environ, GLM53_EXL3_DIR=tmp, PATH=tmp + ':' + os.environ['PATH'])
            result = subprocess.run(['bash', str(ADAPTER), '--served-model-name', 'GLM-5.3-Flash-EXL3', '--port', '8005', '--api-key', 'test-only-key'], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

if __name__ == '__main__':
    unittest.main()
