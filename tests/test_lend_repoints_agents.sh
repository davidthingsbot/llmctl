#!/usr/bin/env bash
# `llmctl lend` moves each hermes agent onto fallback_providers[0] — the model
# block AND auxiliary blocks on a local port — and `reclaim` moves it back with
# a single gateway restart. Added 2026-09-28: relying on per-request failover
# made mr-c retry the dead :19449 twice (~3 s) every turn, and its compression
# client (pinned to a local port, no fallback of its own) failed outright.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fixture="$repo_root/tests/fixtures/hermes-local-fallback-config.yaml"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

home="$tmp/home"; config="$home/hermes-profile/config.yaml"
agent_dir="$tmp/agents.d"; stub_dir="$tmp/bin"; units="$tmp/units"; calls="$tmp/restarts"
mkdir -p "$(dirname "$config")" "$agent_dir" "$stub_dir" "$units"
cp "$fixture" "$config"; : >"$calls"
printf 'llmctl-local-test-key\n' >"$tmp/vllm-api-keys"
printf '#!/usr/bin/env bash\nexit 0\n' >"$stub_dir/vllm"

cat >"$tmp/machine.conf" <<EOT
ACCEL=cpu
ENABLE_BUILTIN_MODELS=1
VLLM_KEYFILE="$tmp/vllm-api-keys"
VLLM_BIN="$stub_dir/vllm"
HERMES_ENABLE=0
OPENCLAW_ENABLE=0
WEBUI_ENABLE=0
LEND_UNITS="borrower@0.service"
EOT
cat >"$agent_dir/fixture-hermes.conf" <<EOT
TYPE=hermes
CFG="$config"
UNIT=llmctl-test-hermes-gateway.service
FOLLOW=1
EOT
# systemctl stub: units are active iff $units/<unit> exists; restarts are logged
cat >"$stub_dir/systemctl" <<EOT
#!/usr/bin/env bash
units="$units"; calls="$calls"
EOT
cat >>"$stub_dir/systemctl" <<'EOT'
args=(); for a in "$@"; do [[ "$a" == --* ]] || args+=("$a"); done
verb="${args[0]:-}"; unit="${args[-1]:-}"
case "$verb" in
  is-active)       [[ -e "$units/$unit" ]];;
  restart)         echo "$unit" >>"$calls"; touch "$units/$unit";;
  start)           touch "$units/$unit";;
  stop)            rm -f "$units/$unit";;
  enable|disable|daemon-reload|reset-failed|is-enabled|show|cat) exit 0;;
  *) printf 'unexpected systemctl call: %s\n' "$*" >&2; exit 99;;
esac
EOT
printf '#!/usr/bin/env bash\nexit 0\n' >"$stub_dir/curl"
printf '#!/usr/bin/env bash\necho Linger=yes\n' >"$stub_dir/loginctl"
chmod +x "$stub_dir"/*

llmctl() {
  HOME="$home" PATH="$stub_dir:$PATH" MACHINE_CONF="$tmp/machine.conf" AGENTS_D="$agent_dir" STATS=0 \
    "$repo_root/llmctl" "$@"
}
get() { python3 -c 'import sys,yaml
d=yaml.safe_load(open(sys.argv[1]))
for k in sys.argv[2].split("."): d=d[k]
print(d)' "$config" "$1"; }
snap="$home/.config/llmctl/lent-agents/fixture-hermes.json"
gw=llmctl-test-hermes-gateway.service
touch "$units/llm-35b-moe-vllm.service" "$units/$gw"

# 1. lend: model + local compression go to the fallback; the auto vision block,
#    aliases, comments and unrelated keys are untouched; one gateway restart
llmctl lend "test" >"$tmp/out" 2>&1 || { cat "$tmp/out"; echo "lend failed"; exit 1; }
[[ "$(get model.base_url)" == http://dw-spark0:8005/v1 ]] || { cat "$tmp/out"; echo "lend left model on $(get model.base_url)"; exit 1; }
[[ "$(get model.default)" == GLM-5.3-Flash-EXL3 && "$(get model.api_key)" == glm-key-with:colon ]] || { echo "model block not fully retargeted"; exit 1; }
[[ "$(get auxiliary.compression.base_url)" == http://dw-spark0:8005/v1 ]] || { echo "compression stayed on $(get auxiliary.compression.base_url)"; exit 1; }
[[ "$(get auxiliary.compression.model)" == GLM-5.3-Flash-EXL3 ]] || { echo "compression model not retargeted"; exit 1; }
[[ -z "$(get auxiliary.vision.base_url)" && "$(get auxiliary.vision.provider)" == auto ]] || { echo "lend touched the auto vision block"; exit 1; }
[[ "$(get model_aliases.glm53.provider)" == GLM53Flash ]] || { echo "lend touched model_aliases"; exit 1; }
grep -q '^# hermes profile shaped like' "$config" || { echo "lend dropped comments"; exit 1; }
[[ "$(get model.context_length)" == 262144 ]] || { echo "lend clobbered unrelated keys"; exit 1; }
[[ -f "$snap" && "$(stat -c %a "$snap")" == 600 ]] || { echo "snapshot missing or not mode 600"; exit 1; }
[[ "$(wc -l <"$calls")" == 1 ]] || { cat "$calls"; echo "lend should restart the gateway exactly once"; exit 1; }

# 2. lend again: idempotent — no second restart, snapshot kept
llmctl lend again >/dev/null 2>&1
[[ "$(wc -l <"$calls")" == 1 ]] || { echo "repeat lend restarted the gateway again"; exit 1; }
[[ -f "$snap" ]] || { echo "repeat lend lost the snapshot"; exit 1; }

# 3. the user edits a retargeted field during the lend: reclaim must keep it
python3 - "$config" <<'PY'
import sys; p = sys.argv[1]; s = open(p).read()
s = s.replace("    model: GLM-5.3-Flash-EXL3\n    base_url: http://dw-spark0:8005/v1\n    api_key: glm-key-with:colon\n    timeout: 1800",
              "    model: my-choice\n    base_url: http://dw-spark0:8005/v1\n    api_key: glm-key-with:colon\n    timeout: 1800")
open(p, "w").write(s)
PY
[[ "$(get auxiliary.compression.model)" == my-choice ]] || { echo "test setup: edit did not apply"; exit 1; }

# 4. reclaim: model back on the local port; compression back and following the
#    live model (the stale :19448 gets fixed too); one gateway restart
: >"$calls"
llmctl reclaim >"$tmp/out" 2>&1 || { cat "$tmp/out"; echo "reclaim failed"; exit 1; }
[[ "$(get model.base_url)" == http://127.0.0.1:19435/v1 ]] || { cat "$tmp/out"; echo "reclaim left model on $(get model.base_url)"; exit 1; }
[[ "$(get model.api_key)" == llmctl-local-test-key ]] || { echo "reclaim did not restore the local key"; exit 1; }
[[ "$(get auxiliary.compression.base_url)" == http://127.0.0.1:19435/v1 ]] || { cat "$tmp/out"; echo "compression not back on the live model: $(get auxiliary.compression.base_url)"; exit 1; }
[[ ! -f "$snap" ]] || { echo "reclaim left the snapshot"; exit 1; }
[[ "$(wc -l <"$calls")" == 1 ]] || { cat "$calls"; cat "$tmp/out"; echo "reclaim should restart the gateway exactly once"; exit 1; }
grep -q '^# hermes profile shaped like' "$config" || { echo "reclaim dropped comments"; exit 1; }
grep -q 'kept your edits to model' "$tmp/out" || { cat "$tmp/out"; echo "reclaim did not report keeping the user's edit"; exit 1; }

# 5. set moves local auxiliary blocks along with the model
llmctl set 27b-fp8 >"$tmp/out" 2>&1 || { cat "$tmp/out"; echo "set failed"; exit 1; }
[[ "$(get auxiliary.compression.base_url)" == "$(get model.base_url)" ]] || { echo "set left compression on $(get auxiliary.compression.base_url)"; exit 1; }

echo "ok: lend moves model + local aux to the fallback, reclaim restores with one restart, set keeps aux in step"
