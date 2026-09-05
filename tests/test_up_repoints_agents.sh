#!/usr/bin/env bash
# `llmctl up` repoints FOLLOW=1 agents to the model it brought up (or found
# already up), exactly like `set`; `--no-point` leaves them alone.
# Regression for 2026-09-04: on dw-spark0 every model was started via `up`
# from the ops pipelines, so hermes stayed on a dead port for three days.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fixture="$repo_root/tests/fixtures/hermes-cloud-config.yaml"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

home="$tmp/home"
profile_dir="$home/hermes-profile"
config="$profile_dir/config.yaml"
agent_dir="$tmp/agents.d"
stub_dir="$tmp/bin"
mkdir -p "$profile_dir" "$agent_dir" "$stub_dir"
cp "$fixture" "$config"

printf 'llmctl-local-test-key\n' >"$tmp/vllm-api-keys"

cat >"$tmp/machine.conf" <<EOF
ACCEL=cpu
ENABLE_BUILTIN_MODELS=1
VLLM_KEYFILE="$tmp/vllm-api-keys"
HERMES_ENABLE=0
OPENCLAW_ENABLE=0
WEBUI_ENABLE=0
EOF

cat >"$agent_dir/fixture-hermes.conf" <<EOF
TYPE=hermes
CFG="$config"
UNIT=llmctl-test-hermes-gateway.service
FOLLOW=1
EOF

# Hermetic: the model unit reports active (so `up` takes the already-running
# path and never starts anything), the agent gateway reports inactive, health
# checks fail, and nothing else may escape to the real user manager.
cat >"$stub_dir/curl" <<'EOF'
#!/usr/bin/env bash
exit 1
EOF
cat >"$stub_dir/systemctl" <<'EOF'
#!/usr/bin/env bash
if [[ " $* " == *" is-active "* ]]; then
  [[ " $* " == *" llmctl-test-hermes-gateway.service "* ]] && exit 3
  exit 0
fi
printf 'unexpected systemctl call in isolated test: %s\n' "$*" >&2
exit 99
EOF
cat >"$stub_dir/loginctl" <<'EOF'
#!/usr/bin/env bash
echo Linger=yes
EOF
chmod +x "$stub_dir"/*

run_up() {
  HOME="$home" PATH="$stub_dir:$PATH" MACHINE_CONF="$tmp/machine.conf" AGENTS_D="$agent_dir" \
    "$repo_root/llmctl" up "$@" >/dev/null 2>&1
}

model_block() {
  python3 - "$config" <<'PY'
import sys, yaml
m = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))["model"]
print(m.get("default"), m.get("base_url"), m.get("api_key"))
PY
}

before="$(model_block)"

# 1. --no-point: config untouched
run_up --no-point 35b-moe-vllm
[[ "$(model_block)" == "$before" ]] || { echo "--no-point moved the agent: $(model_block)"; exit 1; }

# 2. plain up: FOLLOW=1 agent now targets the model
run_up 35b-moe-vllm
expected="qwen3.6-35b-a3b-fp8 http://127.0.0.1:19435/v1 llmctl-local-test-key"
[[ "$(model_block)" == "$expected" ]] || { echo "up did not repoint: got '$(model_block)', want '$expected'"; exit 1; }

# 3. several models: the LAST one named wins
run_up 27b-q8 35b-moe-vllm
[[ "$(model_block)" == "$expected" ]] || { echo "multi-model up pointed at the wrong model: $(model_block)"; exit 1; }

cmp -s "$fixture" "$repo_root/tests/fixtures/hermes-cloud-config.yaml"
echo "ok: llmctl up repoints following agents (and --no-point does not)"
