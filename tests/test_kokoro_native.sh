#!/usr/bin/env bash
# kokoro kind without docker: PYTHON= + APP_DIR= generate a uvicorn launcher,
# IMAGE= still means docker, and a half-configured native service is refused.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/home/.config/llmctl/services.d" "$TMP/home/bin" "$TMP/app/api/src/models/v1_0"
printf 'MACHINE_NAME=trial\nACCEL=cpu\nENABLE_BUILTIN_MODELS=0\nHERMES_ENABLE=0\nOPENCLAW_ENABLE=0\n' > "$TMP/home/.config/llmctl/machine.conf"
printf '#!/bin/sh\nexit 0\n' > "$TMP/home/bin/python"; chmod +x "$TMP/home/bin/python"
: > "$TMP/app/api/src/main.py"
printf 'KIND=kokoro\nPORT=19443\nHOST=0.0.0.0\nPYTHON=%s/home/bin/python\nAPP_DIR=%s/app\nENV_EXTRA="USE_GPU=true"\n' "$TMP" "$TMP" > "$TMP/home/.config/llmctl/services.d/voice.conf"
printf 'KIND=kokoro\nPORT=19444\nIMAGE="example/kokoro"\n' > "$TMP/home/.config/llmctl/services.d/container.conf"
printf 'KIND=kokoro\nPORT=19445\nPYTHON=%s/home/bin/python\n' "$TMP" > "$TMP/home/.config/llmctl/services.d/half.conf"
python3 - "$ROOT/llmctl" "$TMP/harness.sh" <<'PY'
import pathlib, sys
src = pathlib.Path(sys.argv[1]).read_text()
marker = 'case "${1:-menu}" in\n'
assert marker in src
pathlib.Path(sys.argv[2]).write_text(src.split(marker, 1)[0] + '''
name="${1:-voice}"
[[ "${S_KIND[$name]:-}" == kokoro ]] || exit 21
[[ "$(svc_endpoint voice)" == http://*:19443/v1/audio/speech ]] || exit 23
if [[ "$name" == container ]]; then write_service_run_script container; exit 0; fi
svc_check_prereqs "$name"
write_service_run_script "$name"
''')
PY
HOME="$TMP/home" bash "$TMP/harness.sh" voice
python3 - "$TMP/home/.config/llmctl/run-svc-voice.sh" "$TMP" <<'PY'
import pathlib, sys
run = pathlib.Path(sys.argv[1]).read_text(); tmp = sys.argv[2]
assert 'uvicorn api.src.main:app' in run
assert f'cd "{tmp}/app"' in run
assert '--host 0.0.0.0 --port 19443' in run
assert 'export USE_GPU=false' in run
assert run.index('export USE_GPU=false') < run.index('export USE_GPU=true'), 'ENV_EXTRA must come last so it overrides'
assert 'docker' not in run
PY
HOME="$TMP/home" bash "$TMP/harness.sh" container
grep -q 'docker run' "$TMP/home/.config/llmctl/run-svc-container.sh"
HOME="$TMP/home" bash "$TMP/harness.sh" half > "$TMP/out" 2>&1 && { printf 'native kokoro without APP_DIR accepted\n' >&2; exit 1; }
grep -q 'APP_DIR' "$TMP/out"
printf 'PASS: kokoro native launcher, docker launcher kept, half-configured native refused\n'
