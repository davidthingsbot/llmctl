"""Exercise the real dispatch tail without starting any services."""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class LiveEditTest(unittest.TestCase):
    def test_dispatch_survives_in_place_edit_while_command_waits(self):
        dispatch = (ROOT / 'llmctl').read_text().split('case "${1:-menu}" in\n', 1)[1]
        source = ('#!/bin/bash\nset -eu\n'
                  'cmd_up() { printf "WAITING\\n"; read -r answer; printf "DONE\\n"; }\n'
                  'die() { exit 9; }\n'
                  'case "${1:-menu}" in\n' + dispatch)
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / 'llmctl'
            path.write_text(source)
            process = subprocess.Popen(['bash', str(path), 'up', 'test'],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True)
            try:
                self.assertEqual(process.stdout.readline(), 'WAITING\n')
                # Same inode, longer valid Bash file; simulates an editor saving
                # dashboard changes while the model launch is blocked.
                path.write_text('# padding for live edit\n' * 1000 + source)
                subprocess.run(['bash', '-n', str(path)], check=True)
                stdout, stderr = process.communicate('continue\n', timeout=5)
                self.assertEqual(process.returncode, 0, stderr)
                self.assertEqual(stdout, 'DONE\n')
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()

if __name__ == '__main__':
    unittest.main()
