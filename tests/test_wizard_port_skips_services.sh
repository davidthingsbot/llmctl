#!/usr/bin/env bash
# `llmctl add` picks ports upward from WIZARD_BASE_PORT: it must step over a
# registered companion service's port even when that service is not listening.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/home/.config/llmctl/models.d" "$TMP/home/.config/llmctl/services.d" "$TMP/bin"
printf 'MACHINE_NAME=trial\nACCEL=cpu\nENABLE_BUILTIN_MODELS=0\nHERMES_ENABLE=0\nOPENCLAW_ENABLE=0\nWIZARD_BASE_PORT=19438\n' > "$TMP/home/.config/llmctl/machine.conf"
printf 'BACKEND=llamacpp\nPORT=19438\nMODEL_REF=/m.gguf\nMODEL_ID=m\n' > "$TMP/home/.config/llmctl/models.d/m.conf"
printf 'KIND=whisper\nPORT=19439\nMODEL_REF=/w.bin\n' > "$TMP/home/.config/llmctl/services.d/whisper.conf"
printf 'KIND=kokoro\nPORT=19440\nIMAGE=x/kokoro\n' > "$TMP/home/.config/llmctl/services.d/kokoro.conf"
printf '#!/bin/sh\nexit 0\n' > "$TMP/bin/ss"; chmod +x "$TMP/bin/ss"   # nothing is listening
python3 - "$ROOT/llmctl" "$TMP/harness.sh" <<'PY'
import pathlib, sys
src = pathlib.Path(sys.argv[1]).read_text()
marker = 'case "${1:-menu}" in\n'
assert marker in src
pathlib.Path(sys.argv[2]).write_text(src.split(marker, 1)[0] + '\nnext_free_port\n')
PY
got="$(HOME="$TMP/home" PATH="$TMP/bin:$PATH" bash "$TMP/harness.sh")"
[[ "$got" == 19441 ]] || { printf 'next_free_port gave %s, expected 19441 (skipping model 19438 and services 19439/19440)\n' "$got" >&2; exit 1; }
printf 'PASS: wizard port allocation skips registered service ports\n'
