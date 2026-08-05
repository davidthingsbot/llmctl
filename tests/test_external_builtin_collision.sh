#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
HOME_DIR="$TMP/home"
mkdir -p "$HOME_DIR/.config/llmctl/models.d" "$HOME_DIR/models" "$HOME_DIR/bin"
printf 'key\n' > "$HOME_DIR/llama-keys"
printf '#!/usr/bin/env bash\nexit 0\n' > "$HOME_DIR/bin/llama-server"
chmod +x "$HOME_DIR/bin/llama-server"
printf 'gguf\n' > "$HOME_DIR/models/local-27b.gguf"
cat > "$HOME_DIR/.config/llmctl/machine.conf" <<EOF
MACHINE_NAME="collision-test"
ENABLE_BUILTIN_MODELS=0
LLAMA_SERVER="$HOME_DIR/bin/llama-server"
LLAMA_KEYFILE="$HOME_DIR/llama-keys"
MODELS_DIR="$HOME_DIR/models"
ACCEL=cpu
EOF
cat > "$HOME_DIR/.config/llmctl/models.d/27b-q8.conf" <<EOF
BACKEND=llamacpp
PORT=19439
MODEL_REF="$HOME_DIR/models/local-27b.gguf"
MODEL_ID="local-27b"
CTX=4096
DESC="external model reusing a built-in name"
VRAM_MB=0
HEALTH_TIMEOUT=1
GPUS=""
SERVER_CTX=4096
STREAMS=1
EXTRA_ARGS=""
EOF
python3 - "$ROOT/llmctl" "$TMP/harness.sh" <<'PY'
import pathlib, sys
src = pathlib.Path(sys.argv[1]).read_text()
marker = 'case "${1:-menu}" in\n'
assert marker in src
pathlib.Path(sys.argv[2]).write_text(src.split(marker, 1)[0] + 'check_prereqs 27b-q8\nprintf "OK\\n"\n')
PY
output="$(HOME="$HOME_DIR" bash "$TMP/harness.sh" 2>&1)" || {
    printf '%s\n' "$output" >&2
    exit 1
}
[[ "$output" == *"OK"* ]] || {
    printf 'expected external built-in-name override to pass prereqs, got:\n%s\n' "$output" >&2
    exit 1
}
printf 'PASS: external model overrides built-in prerequisite recipe\n'
