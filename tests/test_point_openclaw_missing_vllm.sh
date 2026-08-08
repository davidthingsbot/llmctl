#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fixture="$repo_root/tests/fixtures/openclaw-no-vllm"
sandbox="$(mktemp -d)"
trap 'rm -rf "$sandbox"' EXIT

home="$sandbox/home"
config="$sandbox/openclaw"
agents_d="$sandbox/agents.d"
bin="$sandbox/bin"
mkdir -p "$home" "$config" "$agents_d" "$bin"
cp -R "$fixture"/. "$config"/

keyfile="$sandbox/vllm-api-keys"
printf '%s\n' 'fixture-local-key' > "$keyfile"

machine_conf="$sandbox/machine.conf"
cat > "$machine_conf" <<EOF
ACCEL=cpu
ENABLE_BUILTIN_MODELS=1
VLLM_KEYFILE="$keyfile"
HERMES_ENABLE=0
OPENCLAW_ENABLE=0
WEBUI_ENABLE=0
EOF

cat > "$agents_d/pinned-openclaw.conf" <<EOF
TYPE=openclaw
CFG="$config"
UNIT=fixture-openclaw-gateway.service
FOLLOW=0
EOF

# Prevent even read-only contact with the real gateway or model service. A named,
# pinned agent avoids web UI operations, while HOME/MACHINE_CONF/AGENTS_D confine
# every configuration path to the sandbox.
cat > "$bin/systemctl" <<'EOF'
#!/usr/bin/env bash
exit 1
EOF
cat > "$bin/curl" <<'EOF'
#!/usr/bin/env bash
exit 1
EOF
chmod +x "$bin/systemctl" "$bin/curl"

HOME="$home" \
MACHINE_CONF="$machine_conf" \
AGENTS_D="$agents_d" \
PATH="$bin:$PATH" \
  "$repo_root/llmctl" point 27b-fp8 pinned-openclaw

python3 - "$config" <<'PY'
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
main = json.loads((root / "openclaw.json").read_text())
models = json.loads((root / "agents/main/agent/models.json").read_text())
auth = json.loads((root / "agents/main/agent/auth-profiles.json").read_text())

expected_provider = {
    "baseUrl": "http://127.0.0.1:19434/v1",
    "models": [{
        "id": "qwen3.6-27b-fp8",
        "name": "qwen3.6-27b-fp8",
        "contextWindow": 128000,
    }],
}
assert main["models"]["providers"]["vllm"] == expected_provider
assert main["agents"]["defaults"]["model"]["primary"] == "vllm/qwen3.6-27b-fp8"
assert main["models"]["providers"]["openai"]["models"][0]["id"] == "gpt-5.5"
assert main["agents"]["defaults"]["workspace"] == "/tmp/preserved-workspace"
assert main["unrelated"] == {"preserve": True}

assert models["providers"]["vllm"] == expected_provider
assert models["providers"]["openai"]["models"][0]["id"] == "gpt-5.5"
assert models["unrelated"] == {"preserve": True}

assert auth["profiles"]["vllm:default"] == {
    "provider": "vllm",
    "type": "api_key",
    "key": "fixture-local-key",
}
assert auth["profiles"]["openai:default"]["key"] == "fixture-cloud-key"
assert auth["unrelated"] == {"preserve": True}
PY
