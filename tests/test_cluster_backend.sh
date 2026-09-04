#!/usr/bin/env bash
# BACKEND=cluster + PEERS: conf parsing, node probing with one unreachable peer,
# the per-node memory pre-check, and the generated unit's teardown on every node.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
[[ "${KEEP:-0}" == 1 ]] || trap 'rm -rf "$TMP"' EXIT
HOME_DIR="$TMP/home"
mkdir -p "$HOME_DIR/.config/llmctl/models.d" "$HOME_DIR/bin"
printf 'vllm-key\n' > "$HOME_DIR/vllm-keys"
# the launch script a cluster model points at
printf '#!/usr/bin/env bash\necho "launch $*"\n' > "$HOME_DIR/launch.sh"; chmod +x "$HOME_DIR/launch.sh"
# fakes: ssh answers for 10.0.0.2 with a GB10-shaped probe line (memavail 2000 MiB,
# nvidia-smi memory [N/A]) and hangs up on 10.0.0.3; docker/systemctl are no-ops
cat > "$HOME_DIR/bin/ssh" <<'SSH'
#!/usr/bin/env bash
addr=""; while (($#)); do case "$1" in -o) shift 2;; *) addr="$1"; shift; break;; esac; done
[[ "$addr" == 10.0.0.2 ]] || exit 255
[[ "$*" == true ]] && exit 0
echo '20 0.10 0.20 0.30 127000000 2048000 | 0, NVIDIA GB10, 5, [N/A], [N/A], 40, 12.00;'
SSH
printf '#!/usr/bin/env bash\nexit 0\n' > "$HOME_DIR/bin/docker"
printf '#!/usr/bin/env bash\nexit 0\n' > "$HOME_DIR/bin/systemctl"
chmod +x "$HOME_DIR"/bin/*
cat > "$HOME_DIR/.config/llmctl/machine.conf" <<EOF2
MACHINE_NAME="cl-test"
ENABLE_BUILTIN_MODELS=0
ACCEL=cpu
VLLM_KEYFILE="$HOME_DIR/vllm-keys"
PEERS="good=10.0.0.2 bad=10.0.0.3"
EOF2
cat > "$HOME_DIR/.config/llmctl/models.d/both.conf" <<EOF2
BACKEND=cluster
PORT=18000
MODEL_REF="$HOME_DIR/launch.sh"
MODEL_ID="both-id"
VRAM_MB=1000
EOF2
cat > "$HOME_DIR/.config/llmctl/models.d/one.conf" <<EOF2
BACKEND=cluster
PORT=18001
MODEL_REF="$HOME_DIR/launch.sh"
VRAM_MB=1000
NODES="good"
EOF2
cat > "$HOME_DIR/.config/llmctl/models.d/hungry.conf" <<EOF2
BACKEND=cluster
PORT=18002
MODEL_REF="$HOME_DIR/launch.sh"
VRAM_MB=5000
NODES="good"
EOF2
python3 - "$ROOT/llmctl" "$TMP/harness.sh" <<'PY'
import pathlib, sys
src = pathlib.Path(sys.argv[1]).read_text()
marker = 'case "${1:-menu}" in\n'
assert marker in src
body = r'''
[[ "${BACKEND[both]}" == cluster && "${NODES[both]}" == "good bad" ]] || { echo "FAIL: NODES default should be every peer, got '${NODES[both]}'"; exit 1; }
[[ "${NODES[one]}" == good && "${KEYFILE[one]}" == "$VLLM_KEYFILE" && "${TIMEOUT[one]}" == 2400 ]] || { echo "FAIL: cluster conf keys"; exit 1; }
[[ "${PEER_ADDR[good]}" == 10.0.0.2 && "${PEER_ADDR[bad]}" == 10.0.0.3 ]] || { echo "FAIL: PEERS parse"; exit 1; }
out="$(node_report 2>&1)"
grep -q "good .*cpu 20c load 0.10 0.20 0.30 · ram 119.2/121.1 GiB used (2.0 avail)" <<<"$out" || { echo "FAIL: peer line: $out"; exit 1; }
grep -q "gpu0 NVIDIA GB10 · util 5% · 40°C · 12.00W · unified memory" <<<"$out" || { echo "FAIL: peer gpu line: $out"; exit 1; }
grep -q "bad .*unreachable" <<<"$out" || { echo "FAIL: unreachable peer not flagged: $out"; exit 1; }
grep -q "cl-test .*cpu" <<<"$out" || { echo "FAIL: local node missing: $out"; exit 1; }
vram_ok one >/dev/null 2>&1 || { echo "FAIL: vram_ok should pass with 2000 MiB available and 1000 needed"; exit 1; }
vram_ok hungry >/dev/null 2>&1 && { echo "FAIL: vram_ok should fail when a node has 2000 MiB and 5000 are needed"; exit 1; }
vram_ok both >/dev/null 2>&1 && { echo "FAIL: vram_ok should fail when a node does not answer"; exit 1; }
(check_prereqs one) || { echo "FAIL: check_prereqs one"; exit 1; }
(check_prereqs both) >/dev/null 2>&1 && { echo "FAIL: check_prereqs should die on the unreachable node"; exit 1; }
write_unit one
grep -q 'ExecStopPost='"$RUN_DIR"'/teardown-one.sh' "$SYSTEMD_USER_DIR/llm-one.service" || { echo "FAIL: unit lacks teardown"; exit 1; }
grep -q "ssh .*10.0.0.2 'docker rm -f vllm_node'" "$RUN_DIR/teardown-one.sh" || { echo "FAIL: teardown does not reach the peer"; cat "$RUN_DIR/teardown-one.sh"; exit 1; }
grep -q '^docker rm -f vllm_node' "$RUN_DIR/teardown-one.sh" || { echo "FAIL: teardown skips the local node"; exit 1; }
grep -q -- '--served-model-name one --port 18001' "$RUN_DIR/run-one.sh" || { echo "FAIL: run script args"; cat "$RUN_DIR/run-one.sh"; exit 1; }
grep -q -- '--api-key' "$RUN_DIR/run-one.sh" || { echo "FAIL: run script has no api key"; exit 1; }
[[ "$("$RUN_DIR/run-one.sh")" == "launch --served-model-name one --port 18001 --api-key vllm-key" ]] || { echo "FAIL: run script exec: $("$RUN_DIR/run-one.sh")"; exit 1; }
printf 'OK\n'
'''
pathlib.Path(sys.argv[2]).write_text(src.split(marker, 1)[0] + body)
PY
output="$(HOME="$HOME_DIR" PATH="$HOME_DIR/bin:$PATH" bash "$TMP/harness.sh" 2>&1)" || {
    printf '%s\n' "$output" >&2
    exit 1
}
[[ "$output" == *"OK"* ]] || { printf 'unexpected output:\n%s\n' "$output" >&2; exit 1; }
printf 'PASS: cluster backend — peers parsed, unreachable node flagged, per-node memory check, teardown on every node\n'
