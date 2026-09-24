#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
HOME_DIR="$TMP/home"
CONF_DIR="$HOME_DIR/.config/llmctl"
FAKE_BIN="$TMP/bin"
mkdir -p "$CONF_DIR/models.d" "$CONF_DIR/services.d" "$CONF_DIR/agents.d" "$FAKE_BIN"

for command in systemctl curl hostname nvidia-smi rocm-smi docker ssh; do
  printf '#!/usr/bin/env bash\nprintf "%%s\\n" %q >> %q\nexit 97\n' \
    "$command" "$TMP/external-command-touched" > "$FAKE_BIN/$command"
  chmod +x "$FAKE_BIN/$command"
done

cat > "$CONF_DIR/machine.conf" <<EOF
MACHINE_NAME="spec-fixture"
ENABLE_BUILTIN_MODELS=0
HERMES_ENABLE=0
OPENCLAW_ENABLE=0
VLLM_KEYFILE="$CONF_DIR/vllm-api-keys"
LLAMA_KEYFILE="$CONF_DIR/llama-api-keys"
EOF
# FIFOs prove discovery never opens credential files: any read would block until
# the timeout below fails the test.
mkfifo "$CONF_DIR/vllm-api-keys" "$CONF_DIR/llama-api-keys"

cat > "$CONF_DIR/models.d/alpha.conf" <<'EOF'
BACKEND=vllm
PORT=19438
MODEL_REF="example/alpha"
MODEL_ID="alpha-served"
EOF
cat > "$CONF_DIR/models.d/beta.conf" <<'EOF'
BACKEND=llamacpp
PORT=19439
MODEL_REF="/models/beta.gguf"
MODEL_ID="beta-served"
EOF
cat > "$CONF_DIR/services.d/speech.conf" <<'EOF'
KIND=whisper
PORT=19442
HOST=0.0.0.0
MODEL_REF="/models/whisper.bin"
EOF
cat > "$CONF_DIR/services.d/voice.conf" <<'EOF'
KIND=kokoro
PORT=19443
HOST=127.0.0.1
IMAGE="example/kokoro"
EOF
cat > "$CONF_DIR/services.d/vision.conf" <<'EOF'
KIND=image-inference
PORT=19466
HOST=127.0.0.1
EOF
# Discovery does not need agent definitions. A FIFO makes an accidental read
# deterministic: the command would block until timeout instead of succeeding.
mkfifo "$CONF_DIR/agents.d/must-not-read.conf"

output="$(HOME="$HOME_DIR" PATH="$FAKE_BIN:/usr/bin:/bin" \
  MACHINE_CONF="$CONF_DIR/machine.conf" AGENTS_D="$CONF_DIR/agents.d" \
  /usr/bin/timeout 5 "$ROOT/llmctl" spec)"

python3 - "$output" "$CONF_DIR" <<'PY'
import json
import sys

actual = json.loads(sys.argv[1])
config = sys.argv[2]
expected = {
    "schema_version": 1,
    "machine": {"name": "spec-fixture"},
    "models": [
        {
            "name": "alpha",
            "model_id": "alpha-served",
            "backend": "vllm",
            "base_url": "http://127.0.0.1:19438/v1",
            "port": 19438,
            "key_file": f"{config}/vllm-api-keys",
        },
        {
            "name": "beta",
            "model_id": "beta-served",
            "backend": "llamacpp",
            "base_url": "http://127.0.0.1:19439/v1",
            "port": 19439,
            "key_file": f"{config}/llama-api-keys",
        },
    ],
    "services": [
        {
            "name": "speech",
            "kind": "whisper",
            "port": 19442,
            "bind_host": "0.0.0.0",
            "endpoint": "http://127.0.0.1:19442/inference",
        },
        {
            "name": "vision",
            "kind": "image-inference",
            "port": 19466,
            "bind_host": "127.0.0.1",
            "endpoint": "http://127.0.0.1:19466/v1/analyze",
        },
        {
            "name": "voice",
            "kind": "kokoro",
            "port": 19443,
            "bind_host": "127.0.0.1",
            "endpoint": "http://127.0.0.1:19443/v1/audio/speech",
        },
    ],
}
assert actual == expected, (actual, expected)
PY

if [[ -e "$TMP/external-command-touched" ]]; then
  echo "spec contacted systemd, health endpoints, containers, hardware, hostname, or network" >&2
  exit 1
fi
