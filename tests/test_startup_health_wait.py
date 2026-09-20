"""Startup regression using fake commands and a logical clock; no services run."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
UNIT = "llm-startup-test.service"

# Each line is ActiveState, SubState, Job (- means empty), Result. The last
# snapshot persists. sleep advances the clock instead of waiting in real time.
FAKE_COMMAND = r'''#!/bin/bash
set -euo pipefail
command="${0##*/}"
tick=$(cat "$FIXTURE/tick")
printf '%s %s\n' "$command" "$*" >> "$FIXTURE/calls"
case "$command" in
  sleep)
    [[ "$*" == 1 ]]
    echo "$((tick + 1))" > "$FIXTURE/tick"
    ;;
  curl)
    [[ "$*" == *"http://127.0.0.1:18099/health"* ]]
    (( tick >= HEALTH_AT ))
    ;;
  loginctl)
    [[ "$1" == show-user ]]
    echo Linger=yes
    ;;
  systemctl)
    [[ "$1" == --user ]]
    shift
    case "$1" in
      is-active) [[ "$*" == "is-active --quiet llm-startup-test.service" ]]; exit 3 ;;
      daemon-reload) [[ "$#" == 1 ]] ;;
      start)
        [[ "$*" == "start llm-startup-test.service" ]]
        touch "$FIXTURE/started"
        exit "$START_RC"
        ;;
      stop|enable) [[ "$2" == llm-startup-test.service && "$#" == 2 ]] ;;
      show)
        [[ -f "$FIXTURE/started" && "$*" == *llm-startup-test.service* ]]
        state=$(sed -n "$((tick + 1))p" "$FIXTURE/states")
        [[ -n "$state" ]] || state=$(tail -1 "$FIXTURE/states")
        # Failed/empty property queries are uncertainty, not terminal states.
        [[ "$state" != query-error ]] || exit 1
        [[ "$state" != empty ]] || exit 0
        read -r active sub job result <<< "$state"
        printf 'Result=%s\nSubState=%s\nActiveState=%s\n' "$result" "$sub" "$active"
        [[ "$job" != missing ]] || exit 0
        [[ "$job" != - ]] || job=""
        printf 'Job=%s\n' "$job"
        ;;
      *) echo "unexpected systemctl: $*" >&2; exit 99 ;;
    esac
    ;;
  *) echo "unexpected command: $command $*" >&2; exit 99 ;;
esac
'''


class StartupHealthWaitTest(unittest.TestCase):
    def run_start(self, states, health_at=999, timeout=30, start_rc=0, direct=False):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            home = fixture / "home"
            config = home / ".config/llmctl"
            models = config / "models.d"
            models.mkdir(parents=True)
            bin_dir = fixture / "bin"
            bin_dir.mkdir()
            for command in ("systemctl", "curl", "sleep", "loginctl", "vllm",
                            "docker", "ssh", "sudo", "journalctl"):
                path = bin_dir / command
                path.write_text(FAKE_COMMAND)
                path.chmod(0o755)
            (fixture / "key").write_text("test-key\n")
            (fixture / "tick").write_text("0\n")
            (fixture / "states").write_text("\n".join(states) + "\n")
            machine = config / "machine.conf"
            machine.write_text(
                f"ACCEL=cpu\nENABLE_BUILTIN_MODELS=0\nVLLM_BIN={bin_dir}/vllm\n"
                f"VLLM_KEYFILE={fixture}/key\nHERMES_ENABLE=0\n"
                "OPENCLAW_ENABLE=0\nWEBUI_ENABLE=0\nLEGACY_UNITS=\n"
            )
            model = models / "startup-test.conf"
            model_text = (
                "BACKEND=vllm\nPORT=18099\nMODEL_REF=test/model\n"
                f"HEALTH_TIMEOUT={timeout}\n"
            )
            model.write_text(model_text)
            env = dict(os.environ, HOME=str(home), FIXTURE=str(fixture),
                       PATH=f"{bin_dir}:{os.environ['PATH']}", STATS="0",
                       MACHINE_CONF=str(machine), AGENTS_D=str(config / "agents.d"),
                       STATS_FILE=str(fixture / "stats.jsonl"),
                       HEALTH_AT=str(health_at), START_RC=str(start_rc))
            command = ["bash", str(ROOT / "llmctl"), "up", "--no-point", "startup-test"]
            if direct:
                # Like test_cluster_backend.sh: retain real definitions and
                # initialization, replace only dispatch to inspect stdout.
                source = (ROOT / "llmctl").read_text().split('case "${1:-menu}" in\n', 1)[0]
                harness = fixture / "wait.sh"
                harness.write_text(source + '\nwait_health_timed startup-test 30 12\n')
                (fixture / "started").touch()
                command = ["bash", str(harness)]
            result = subprocess.run(command, env=env, capture_output=True,
                                    text=True, timeout=15)
            ticks = int((fixture / "tick").read_text())
            calls = (fixture / "calls").read_text().splitlines()
            self.assertEqual(model.read_text(), model_text)
            self.assertFalse(any("unexpected" in line for line in result.stderr.splitlines()), result.stderr)
            # No launch, prior-model restoration, or other unit mutation can
            # hide behind a permissive systemctl stub.
            mutations = [line for line in calls if line.startswith("systemctl --user ")
                         and line.split()[2] in ("start", "stop", "enable", "restart", "disable")]
            expected = [] if direct else [f"systemctl --user start {UNIT}",
                                          f"systemctl --user {'enable' if result.returncode == 0 else 'stop'} {UNIT}"]
            self.assertEqual(mutations, expected, result.stderr)
            if not direct:
                self.assertTrue((config / "run-startup-test.sh").exists())
                self.assertTrue((home / ".config/systemd/user" / UNIT).exists())
            return result, ticks, calls

    def assert_terminal(self, states, state):
        result, ticks, _ = self.run_start(states)
        self.assertNotEqual(result.returncode, 0)
        self.assertLessEqual(ticks, len(states) + 2, result.stderr)
        self.assertIn(state, result.stderr)
        self.assertIn(UNIT, result.stderr)
        self.assertIn(f"systemctl --user status {UNIT}", result.stderr)
        self.assertIn("llmctl logs startup-test", result.stderr)
        self.assertNotIn("after 30s", result.stderr)
        self.assertNotIn("READY", result.stdout)
        self.assertNotIn("loading:", result.stderr)

    def test_failed_unit_exits_promptly(self):
        self.assert_terminal(["active running - success", "failed failed - exit-code"], "failed")

    def test_terminal_inactive_exits_promptly(self):
        self.assert_terminal(["inactive dead - success"], "inactive")

    def test_restart_limit_failure_exits_promptly(self):
        self.assert_terminal(["activating auto-restart - exit-code",
                              "failed failed - start-limit-hit"], "start-limit-hit")

    def test_activating_and_running_reach_health(self):
        result, ticks, _ = self.run_start(["activating start 41 success"] * 3 +
                                          ["active running - success"], health_at=12)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(ticks, 12)
        self.assertIn("READY in 12s", result.stdout)
        self.assertIn("loading: 10s elapsed", result.stderr)

    def test_auto_restart_delay_and_transient_terminal_states_recover(self):
        states = (["failed failed - exit-code"] +
                  ["activating auto-restart - exit-code"] * 12 +
                  ["inactive dead - success", "activating auto-restart-queued 42 exit-code",
                   "deactivating stop-sigterm 42 exit-code", "active running - success"])
        result, ticks, _ = self.run_start(states, health_at=len(states))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(ticks, len(states))

    def test_pending_restart_job_is_not_terminal(self):
        for state in ("inactive dead 42 success", "failed failed 42 exit-code"):
            with self.subTest(state=state):
                result, ticks, _ = self.run_start([state] * 4 + ["active running - success"], health_at=5)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(ticks, 5)

    def test_uncertain_state_queries_do_not_confirm_terminal_state(self):
        for unknown in ("query-error", "empty", "inactive dead missing success"):
            with self.subTest(unknown=unknown):
                result, _, _ = self.run_start(["failed failed - exit-code", unknown,
                                               "inactive dead - success", "active running - success"], health_at=4)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_health_success_retains_elapsed_only_stdout(self):
        result, ticks, _ = self.run_start(["active running - success"], health_at=12, direct=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "12\n")
        self.assertEqual(ticks, 12)
        self.assertIn("typical ~12s", result.stderr)

    def test_immediate_health_success(self):
        result, ticks, _ = self.run_start(["failed failed - exit-code"], health_at=0)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(ticks, 0)
        self.assertIn("READY in 0s", result.stdout)

    def test_unhealthy_running_unit_still_times_out(self):
        result, ticks, _ = self.run_start(["active running - success"], timeout=12)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(ticks, 12)
        self.assertIn("12s", result.stderr)
        self.assertIn("llmctl logs startup-test", result.stderr)

    def test_rejected_start_does_not_enter_health_wait(self):
        result, ticks, calls = self.run_start(["inactive dead - success"], start_rc=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(ticks, 0, result.stderr)
        self.assertFalse(any(line.startswith("curl ") for line in calls))
        self.assertIn(UNIT, result.stderr)
        self.assertIn("llmctl logs startup-test", result.stderr)
        self.assertNotIn("after 30s", result.stderr)


if __name__ == "__main__":
    unittest.main()
