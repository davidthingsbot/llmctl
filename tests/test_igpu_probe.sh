#!/usr/bin/env bash
# An Intel iGPU box (i915/xe, no smi tool, no root) must appear in the node
# line exactly like a CUDA card: igpu_csv emits nvidia-smi's csv shape from a
# fake sysfs card + fake /proc fdinfo, and node_report_line renders it.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/home/.config/llmctl"
printf 'MACHINE_NAME=igpubox\nACCEL=cpu\nENABLE_BUILTIN_MODELS=0\nHERMES_ENABLE=0\nOPENCLAW_ENABLE=0\n' > "$TMP/home/.config/llmctl/machine.conf"

# fake sysfs: one Intel card on i915 at 0000:00:02.0 (plus a connector dir and
# an AMD card that must be ignored), clock 1700 MHz, no hwmon
mkdir -p "$TMP/sys/pci/0000:00:02.0" "$TMP/sys/drivers/i915" "$TMP/sys/drm/card1/gt/gt0" "$TMP/sys/drm/card1-eDP-1" "$TMP/sys/drm/card2/device"
ln -s ../../pci/0000:00:02.0 "$TMP/sys/drm/card1/device"
ln -s ../../drivers/i915 "$TMP/sys/pci/0000:00:02.0/driver"
echo 0x8086 > "$TMP/sys/pci/0000:00:02.0/vendor"; echo 0x7d45 > "$TMP/sys/pci/0000:00:02.0/device"
echo 1700 > "$TMP/sys/drm/card1/gt/gt0/rps_act_freq_mhz"
echo 0x1002 > "$TMP/sys/drm/card2/device/vendor"

# fake /proc: two DRM clients (one duplicated across two fds), one on another
# pdev, one unreadable-looking non-DRM fd. Busy counters do not advance between
# samples, so util is 0; resident sums to 320092 + 51200 KiB = 362.6 -> 363 MiB.
mkdir -p "$TMP/proc/100/fdinfo" "$TMP/proc/200/fdinfo"
fd() { printf 'pos:\t0\nflags:\t02100002\ndrm-driver:\ti915\ndrm-client-id:\t%s\ndrm-pdev:\t%s\ndrm-resident-system0:\t%s KiB\ndrm-engine-render:\t%s ns\ndrm-engine-copy:\t0 ns\n' "$@"; }
fd 24 0000:00:02.0 320092 123456789 > "$TMP/proc/100/fdinfo/5"
fd 24 0000:00:02.0 320092 123456789 > "$TMP/proc/100/fdinfo/6"   # same client, second fd
fd 99 0000:03:00.0 999999 5 > "$TMP/proc/100/fdinfo/7"           # another GPU
fd 151 0000:00:02.0 51200 42 > "$TMP/proc/200/fdinfo/3"
printf 'pos:\t0\nflags:\t02\n' > "$TMP/proc/200/fdinfo/4"

python3 - "$ROOT/llmctl" "$TMP/harness.sh" <<'PY'
import pathlib, sys
src = pathlib.Path(sys.argv[1]).read_text()
marker = 'case "${1:-menu}" in\n'
assert marker in src
pathlib.Path(sys.argv[2]).write_text(src.split(marker, 1)[0] + '''
case "${1:-csv}" in
  csv)   igpu_csv;;
  probe) bash -c "$NODE_PROBE";;
  line)  node_report_line "$MACHINE_NAME" "$(bash -c "$NODE_PROBE")";;
  fdinfo) igpu_fdinfo 0000:00:02.0;;
esac
''')
PY
export HOME="$TMP/home" IGPU_SYS="$TMP/sys/drm" IGPU_PROC="$TMP/proc" IGPU_INTERVAL=0.05 PATH="$TMP/bin:$PATH"
mkdir -p "$TMP/bin"; printf '#!/bin/sh\nexit 1\n' > "$TMP/bin/lspci"; printf '#!/bin/sh\nexit 1\n' > "$TMP/bin/nvidia-smi"; chmod +x "$TMP/bin/"*

fdinfo="$(bash "$TMP/harness.sh" fdinfo)"
[[ "$(wc -l <<<"$fdinfo")" == 2 ]] || { echo "expected 2 clients, got: $fdinfo"; exit 11; }
grep -q '^100 24 123456789 0 327774208$' <<<"$fdinfo" || { echo "client 24 wrong: $fdinfo"; exit 12; }
grep -q '^200 151 42 0 52428800$' <<<"$fdinfo" || { echo "client 151 wrong: $fdinfo"; exit 13; }

csv="$(bash "$TMP/harness.sh" csv)"
[[ "$(wc -l <<<"$csv")" == 1 ]] || { echo "expected one card, got: $csv"; exit 21; }
memtotal=$(( $(awk '/^MemTotal/{print $2}' /proc/meminfo) / 1024 ))
expected="0, Intel GPU 0x7d45, 0, 363, $memtotal, [N/A], [N/A], 1700"
[[ "$csv" == "$expected" ]] || { echo "csv mismatch:"; echo "  got:  $csv"; echo "  want: $expected"; exit 22; }

probe="$(bash "$TMP/harness.sh" probe)"
[[ "$probe" == *"| 0, Intel GPU 0x7d45, 0, 363, $memtotal, [N/A], [N/A], 1700; |"* ]] || { echo "probe lacks the gpu segment: $probe"; exit 31; }

line="$(bash "$TMP/harness.sh" line)"
grep -q 'igpubox *cpu [0-9]*c load' <<<"$line" || { echo "no cpu line: $line"; exit 41; }
grep -q 'gpu0 Intel GPU 0x7d45 · util 0% · \[N/A\]°C · \[N/A\]W · 0.4/' <<<"$line" || { echo "gpu line wrong: $line"; exit 42; }

# the remote form must survive any login shell: it is base64 piped into bash
python3 - "$ROOT/llmctl" <<'PY'
import pathlib, sys
src = pathlib.Path(sys.argv[1]).read_text()
assert 'NODE_PROBE_REMOTE="echo $(base64 -w0 <<<"$NODE_PROBE") | base64 -d | bash"' in src
assert 'peer_sh "$1" "$NODE_PROBE_REMOTE"' in src
assert 'T_PROBE="$NODE_PROBE_REMOTE"' in src
PY
printf 'PASS: Intel iGPU probe — fdinfo clients deduped and filtered by pdev, nvidia-smi-shaped csv, node line rendered\n'
