#!/usr/bin/env bash
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
cp "$fixture" "$tmp/source-before.yaml"

cat >"$tmp/vllm-api-keys" <<'EOF'
llmctl-local-test-key
EOF

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
FOLLOW=0
EOF

# Keep the regression hermetic: no health request and no live user service lookup
# may escape this temporary fixture.
cat >"$stub_dir/curl" <<'EOF'
#!/usr/bin/env bash
exit 1
EOF
cat >"$stub_dir/systemctl" <<'EOF'
#!/usr/bin/env bash
[[ " $* " == *" is-active "* ]] && exit 3
printf 'unexpected systemctl call in isolated test: %s\n' "$*" >&2
exit 99
EOF
chmod +x "$stub_dir/curl" "$stub_dir/systemctl"

HOME="$home" \
PATH="$stub_dir:$PATH" \
MACHINE_CONF="$tmp/machine.conf" \
AGENTS_D="$agent_dir" \
  "$repo_root/llmctl" point 27b-fp8 fixture-hermes >/dev/null

python3 - "$config" <<'PY'
import sys
import yaml

with open(sys.argv[1], encoding="utf-8") as stream:
    config = yaml.safe_load(stream)

model = config["model"]
expected = {
    "default": "qwen3.6-27b-fp8",
    "provider": "openai",
    "base_url": "http://127.0.0.1:19434/v1",
    "api_key": "llmctl-local-test-key",
    "context_length": 200000,
    "fallback": ["anthropic/claude-sonnet-4"],
}
assert model == expected, f"unexpected repointed model block: {model!r}"
assert config["agent"] == {"max_turns": 37}
assert config["display"] == {"skin": "nord"}
assert config["auxiliary"] == {
    "vision": {"model": "google/gemini-2.5-flash"}
}
PY

cmp -s "$fixture" "$tmp/source-before.yaml"
cmp -s "$fixture" "$repo_root/tests/fixtures/hermes-cloud-config.yaml"
