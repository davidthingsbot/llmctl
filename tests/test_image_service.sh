#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/home/.config/llmctl/services.d" "$TMP/home/bin"
printf 'MACHINE_NAME=trial\nACCEL=cpu\nENABLE_BUILTIN_MODELS=0\nHERMES_ENABLE=0\nOPENCLAW_ENABLE=0\n' > "$TMP/home/.config/llmctl/machine.conf"
printf '#!/bin/sh\nexit 0\n' > "$TMP/home/bin/python"
chmod +x "$TMP/home/bin/python"
printf 'KIND=image-inference\nPORT=19466\nHOST=127.0.0.1\nPYTHON=%s/home/bin/python\nSERVICE_SCRIPT=%s/image_service.py\nWEIGHTS_DIR=%s/models\n' "$TMP" "$ROOT" "$TMP" > "$TMP/home/.config/llmctl/services.d/vision.conf"
mkdir -p "$TMP/models"
for name in object_detection_yolox_2022nov.onnx face_detection_yunet_2023mar.onnx face_recognition_sface_2021dec_int8.onnx; do printf 'test weights\n' > "$TMP/models/$name"; done
python3 - "$ROOT/llmctl" "$TMP/harness.sh" <<'PY'
import pathlib, sys
src = pathlib.Path(sys.argv[1]).read_text()
marker = 'case "${1:-menu}" in\n'
assert marker in src
pathlib.Path(sys.argv[2]).write_text(src.split(marker, 1)[0] + '''
[[ "${S_KIND[vision]:-}" == image-inference ]] || exit 21
[[ "${S_HOST[vision]}" == 127.0.0.1 ]] || exit 22
[[ "$(svc_endpoint vision)" == http://127.0.0.1:19466/v1/analyze ]] || exit 23
svc_check_prereqs "${1:-vision}"
write_service_run_script "${1:-vision}"
''')
PY
HOME="$TMP/home" bash "$TMP/harness.sh"
python3 - "$TMP/home/.config/llmctl/run-svc-vision.sh" "$ROOT/image_service.py" <<'PY'
import pathlib, sys
run = pathlib.Path(sys.argv[1]).read_text()
assert sys.argv[2] in run
assert '127.0.0.1' in run
assert '--port 19466' in run
assert '--weights-dir' in run and '/models' in run
assert 'docker run' not in run
PY
# HOST=0.0.0.0 is allowed (LAN use, firewall-guarded like whisper/kokoro) and reaches the launcher
printf 'KIND=image-inference\nPORT=19467\nHOST=0.0.0.0\nPYTHON=%s/home/bin/python\nSERVICE_SCRIPT=%s/image_service.py\nWEIGHTS_DIR=%s/models\n' "$TMP" "$ROOT" "$TMP" > "$TMP/home/.config/llmctl/services.d/lan.conf"
HOME="$TMP/home" bash "$TMP/harness.sh" lan
grep -q -- '--host 0.0.0.0 --port 19467' "$TMP/home/.config/llmctl/run-svc-lan.sh"
printf 'PASS: image service registry, loopback default, generated launcher, LAN host honoured\n'
