#!/usr/bin/env bash
# A KIND=comfyui companion service is LEND=1 by default: it needs the GPUs, so
# `service up` refuses it while models may run, `llmctl lend` starts it once
# the models are down, and `llmctl reclaim` stops it before restoring the
# models. Added 2026-09-29 when ComfyUI moved onto the DGX Sparks, whose
# unified memory cannot hold ComfyUI beside a cluster model.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

home="$tmp/home"
services_dir="$tmp/services.d"
stub_dir="$tmp/bin"
units="$tmp/units"          # one file per active unit
appdir="$tmp/ComfyUI"
mkdir -p "$home" "$services_dir" "$stub_dir" "$units" "$appdir"
printf 'llmctl-local-test-key\n' >"$tmp/vllm-api-keys"
: >"$appdir/main.py"
printf '#!/usr/bin/env bash\nexit 0\n' >"$stub_dir/python-comfy"; chmod +x "$stub_dir/python-comfy"

cat >"$tmp/machine.conf" <<EOC
ACCEL=cpu
ENABLE_BUILTIN_MODELS=1
VLLM_KEYFILE="$tmp/vllm-api-keys"
VLLM_BIN="$stub_dir/vllm"
HERMES_ENABLE=0
OPENCLAW_ENABLE=0
WEBUI_ENABLE=0
EOC
cat >"$services_dir/comfyui.conf" <<EOC
KIND=comfyui
PORT=8188
PYTHON="$stub_dir/python-comfy"
APP_DIR="$appdir"
EXTRA_ARGS="--fast-disk --enable-cors-header"
DESC="ComfyUI test"
HEALTH_TIMEOUT=3
EOC
cat >"$services_dir/whisper.conf" <<EOC
KIND=whisper
PORT=19450
MODEL_REF="$tmp/ggml.bin"
EOC

# Hermetic systemctl: units are active iff $units/<unit> exists.
cat >"$stub_dir/systemctl" <<EOC
#!/usr/bin/env bash
units="$units"
EOC
cat >>"$stub_dir/systemctl" <<'EOC'
args=(); for a in "$@"; do [[ "$a" == --* ]] || args+=("$a"); done
verb="${args[0]:-}"; unit="${args[-1]:-}"
case "$verb" in
  is-active)       [[ -e "$units/$unit" ]];;
  start|restart)   touch "$units/$unit";;
  stop)            rm -f "$units/$unit";;
  enable)          touch "$units/$unit.enabled";;
  disable)         rm -f "$units/$unit.enabled";;
  daemon-reload|reset-failed|is-enabled|show|cat) exit 0;;
  *) printf 'unexpected systemctl call in isolated test: %s\n' "$*" >&2; exit 99;;
esac
EOC
# curl: the comfyui health probe (:8188) passes only while its unit marker exists;
# every other probe (the restored model) passes outright
cat >"$stub_dir/curl" <<EOC
#!/usr/bin/env bash
for a in "\$@"; do [[ "\$a" == *:8188* ]] && { [[ -e "$units/llm-svc-comfyui.service" ]]; exit; }; done
exit 0
EOC
cat >"$stub_dir/loginctl" <<'EOC'
#!/usr/bin/env bash
echo Linger=yes
EOC
printf '#!/usr/bin/env bash\nexit 0\n' >"$stub_dir/vllm"
chmod +x "$stub_dir"/*

llmctl() {
  HOME="$home" PATH="$stub_dir:$PATH" MACHINE_CONF="$tmp/machine.conf" SERVICES_D="$services_dir" \
    AGENTS_D="$tmp/agents.d" STATS=0 "$repo_root/llmctl" "$@"
}
state="$home/.config/llmctl/lent"
model_unit="llm-35b-moe-vllm.service"
svc_unit="llm-svc-comfyui.service"

# 0. the kind registers, defaults to LEND=1, health on /system_stats
grep -q 'comfyui .*comfyui .*8188' <(llmctl services 2>&1) || { llmctl services; echo "comfyui service not listed"; exit 1; }
grep -q '"LEND' <(llmctl spec 2>&1) && { echo "LEND leaked into spec (fine if intended, but not expected)"; }

# 1. service up refuses while the box is not lent; FORCE=1 is the only way through
if llmctl service up comfyui >"$tmp/out" 2>&1; then cat "$tmp/out"; echo "service up ran a LEND=1 service while not lent"; exit 1; fi
grep -q "llmctl lend" "$tmp/out" || { cat "$tmp/out"; echo "refusal does not point at lend"; exit 1; }
[[ ! -e "$units/$svc_unit" ]] || { echo "refused service up still started the unit"; exit 1; }
FORCE=1 llmctl service up comfyui >"$tmp/out" 2>&1 || { cat "$tmp/out"; echo "FORCE=1 service up failed"; exit 1; }
[[ -e "$units/$svc_unit" ]] || { echo "FORCE=1 service up did not start the unit"; exit 1; }
[[ ! -e "$units/$svc_unit.enabled" ]] || { echo "a LEND=1 service was enabled on boot"; exit 1; }
grep -q -- '--listen 0.0.0.0 --port 8188 --fast-disk --enable-cors-header' "$home/.config/llmctl/run/run-svc-comfyui.sh" 2>/dev/null \
  || grep -rq -- '--listen 0.0.0.0 --port 8188 --fast-disk --enable-cors-header' "$home" \
  || { echo "generated run script lacks the ComfyUI launch line"; exit 1; }
llmctl service down comfyui >/dev/null 2>&1

# 2. lend: stops the model, then starts the comfyui service
touch "$units/$model_unit"
llmctl lend "comfyui on the sparks" >"$tmp/out" 2>&1 || { cat "$tmp/out"; echo "lend failed"; exit 1; }
[[ ! -e "$units/$model_unit" ]] || { echo "lend left $model_unit running"; exit 1; }
[[ -e "$units/$svc_unit" ]] || { cat "$tmp/out"; echo "lend did not start the comfyui service"; exit 1; }
[[ ! -e "$units/$svc_unit.enabled" ]] || { echo "lend enabled the comfyui service on boot"; exit 1; }
grep -q 'comfyui .*up+healthy' <(llmctl status 2>&1) || { llmctl status; echo "status does not show comfyui healthy while lent"; exit 1; }

# 3. an ordinary (LEND=0) service is untouched by lend/reclaim
[[ ! -e "$units/llm-svc-whisper.service" ]] || { echo "lend started the whisper service"; exit 1; }

# 4. reclaim: stops the comfyui service first, then restores the model
llmctl reclaim >"$tmp/out" 2>&1 || { cat "$tmp/out"; echo "reclaim failed"; exit 1; }
[[ ! -e "$units/$svc_unit" ]] || { echo "reclaim left the comfyui service running"; exit 1; }
[[ -e "$units/$model_unit" ]] || { cat "$tmp/out"; echo "reclaim did not restart $model_unit"; exit 1; }
[[ ! -e "$state" ]] || { echo "reclaim left the lend state behind"; exit 1; }

echo "ok: KIND=comfyui is a LEND=1 service — refused by service up, started by lend, stopped by reclaim"
