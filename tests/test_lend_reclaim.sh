#!/usr/bin/env bash
# `llmctl lend` stops + un-boots every running model, records them, and blocks
# set/up until `llmctl reclaim` brings exactly those models back (repointing
# the FOLLOW=1 agents). Added 2026-09-27 when the 3090s went to ComfyUI for
# the night: the cluster-backend VRAM check only looks at host RAM, so without
# the guard a routine `llmctl up` would load onto the borrower's GPUs.
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
units="$tmp/units"          # one file per active unit
mkdir -p "$profile_dir" "$agent_dir" "$stub_dir" "$units"
cp "$fixture" "$config"
printf 'llmctl-local-test-key\n' >"$tmp/vllm-api-keys"

cat >"$tmp/machine.conf" <<EOF
ACCEL=cpu
ENABLE_BUILTIN_MODELS=1
VLLM_KEYFILE="$tmp/vllm-api-keys"
VLLM_BIN="$stub_dir/vllm"
HERMES_ENABLE=0
OPENCLAW_ENABLE=0
WEBUI_ENABLE=0
LEND_UNITS="borrower@0.service borrower@1.service"
EOF

cat >"$agent_dir/fixture-hermes.conf" <<EOF
TYPE=hermes
CFG="$config"
UNIT=llmctl-test-hermes-gateway.service
FOLLOW=1
EOF

# Hermetic systemctl: model units are active iff $units/<unit> exists; the agent
# gateway is always inactive; start/stop/enable/disable just flip the marker.
cat >"$stub_dir/systemctl" <<EOF
#!/usr/bin/env bash
units="$units"
EOF
cat >>"$stub_dir/systemctl" <<'EOF'
args=(); for a in "$@"; do [[ "$a" == --* ]] || args+=("$a"); done
verb="${args[0]:-}"; unit="${args[-1]:-}"
case "$verb" in
  is-active)       [[ "$unit" != llmctl-test-* && -e "$units/$unit" ]];;
  start|restart)   touch "$units/$unit";;
  stop)            rm -f "$units/$unit";;
  enable|disable|daemon-reload|reset-failed|is-enabled|show|cat) exit 0;;
  *) printf 'unexpected systemctl call in isolated test: %s\n' "$*" >&2; exit 99;;
esac
EOF
cat >"$stub_dir/curl" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
cat >"$stub_dir/loginctl" <<'EOF'
#!/usr/bin/env bash
echo Linger=yes
EOF
chmod +x "$stub_dir"/*

llmctl() {
  HOME="$home" PATH="$stub_dir:$PATH" MACHINE_CONF="$tmp/machine.conf" AGENTS_D="$agent_dir" STATS=0 \
    "$repo_root/llmctl" "$@"
}
state="$home/.config/llmctl/lent"
unit="llm-35b-moe-vllm.service"

touch "$units/$unit"                       # model is running

# 1. lend: stops it, records it, reason survives quoting
llmctl lend "comfyui video, don't touch" >"$tmp/out" 2>&1 || { cat "$tmp/out"; echo "lend failed"; exit 1; }
[[ ! -e "$units/$unit" ]] || { echo "lend left $unit running"; exit 1; }
[[ -f "$state" ]] || { echo "lend wrote no state file"; exit 1; }
for b in borrower@0.service borrower@1.service; do
  [[ -e "$units/$b" ]] || { echo "lend did not start LEND_UNITS $b"; exit 1; }
done
grep -q "comfyui video, don't touch" <(llmctl status 2>&1) || { echo "status does not show the lend"; exit 1; }

# 2. set/up refuse while lent; FORCE=1 is the only way through
if llmctl up --no-point 27b-q8 >/dev/null 2>&1; then echo "up ran while lent"; exit 1; fi
if llmctl set 27b-q8 >/dev/null 2>&1; then echo "set ran while lent"; exit 1; fi
[[ -z "$(ls "$units" | grep -v '^borrower@')" ]] || { echo "a refused up/set still started something: $(ls "$units")"; exit 1; }

# 3. lend again is a no-op that reports, not a second overwrite
llmctl lend other >/dev/null 2>&1
( source "$state"; [[ "$LENT_REASON" == "comfyui video, don't touch" && "${LENT_MODELS[*]}" == 35b-moe-vllm ]] ) \
  || { cat "$state"; echo "second lend clobbered the state"; exit 1; }

# 4. a reclaim that fails (vllm missing) keeps the box marked lent
if llmctl reclaim >/dev/null 2>&1; then echo "reclaim succeeded without vllm"; exit 1; fi
( source "$state"; [[ "${LENT_MODELS[*]}" == 35b-moe-vllm ]] ) || { echo "failed reclaim lost the lend state"; exit 1; }
printf '#!/usr/bin/env bash\nexit 0\n' >"$stub_dir/vllm"; chmod +x "$stub_dir/vllm"

# 5. reclaim: brings back exactly what was lent and repoints the agent
llmctl reclaim >"$tmp/out" 2>&1 || { cat "$tmp/out"; echo "reclaim failed"; exit 1; }
[[ -e "$units/$unit" ]] || { cat "$tmp/out"; echo "reclaim did not restart $unit"; exit 1; }
[[ ! -e "$state" ]] || { echo "reclaim left the lend state behind"; exit 1; }
[[ -z "$(ls "$units" | grep '^borrower@')" ]] || { echo "reclaim left LEND_UNITS running: $(ls "$units")"; exit 1; }
base="$(python3 -c 'import sys,yaml; print(yaml.safe_load(open(sys.argv[1]))["model"]["base_url"])' "$config")"
[[ "$base" == http://127.0.0.1:19435/v1 ]] || { echo "reclaim did not repoint the agent: $base"; exit 1; }

# 6. reclaim when not lent is harmless
llmctl reclaim >/dev/null 2>&1 || { echo "reclaim errored when not lent"; exit 1; }

echo "ok: lend stops + records models and blocks set/up; reclaim restores and repoints"
