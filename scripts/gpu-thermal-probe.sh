#!/usr/bin/env bash
#
# gpu-thermal-probe.sh — monitored warm-up test for the 3090 pair, with auto-abort.
#
# WHY: on 2026-07-19 10:34:55 GPU 0 (PCI 01:00, the older board) hit Xid 79
# "GPU has fallen off the bus" ~37 min into serving 27b-fp8 (TP=2) with NO
# power cap applied (both cards at the 390W factory limit). The driver then
# required a node reboot. This script reproduces load *under supervision*:
# it logs temps/power/clocks every 2s, fires inference queries at a running
# llmctl model, and kills the load the moment any GPU crosses the abort
# temperature or the kernel logs a new NVRM/Xid error — well before the
# fall-off-the-bus regime.
#
# Usage:
#   scripts/gpu-thermal-probe.sh                    # monitor only, no load
#   scripts/gpu-thermal-probe.sh --load             # monitor + fire queries at :19434
#   scripts/gpu-thermal-probe.sh --load --port 19436 --concurrency 2 --duration 600
#   scripts/gpu-thermal-probe.sh --load --abort-c 78
#
# Defaults: abort at 83°C (warn at 75), 3 concurrent streams, 300s of load,
# then 60s of cooldown logging. CSV logs land in ~/gpu-thermal-logs/.
# Exit codes: 0 = completed clean, 2 = aborted on temperature, 3 = aborted on Xid.
#
# Before running with --load: start a model first (e.g. `llmctl start 27b-fp8`)
# and strongly consider capping power first:  sudo nvidia-smi -pl 300
set -u

LOAD=0; PORT=19434; CONC=3; DURATION=300; ABORT_C=83; WARN_C=75; COOLDOWN=60
while [[ $# -gt 0 ]]; do
  case "$1" in
    --load) LOAD=1;;
    --port) PORT="$2"; shift;;
    --concurrency) CONC="$2"; shift;;
    --duration) DURATION="$2"; shift;;
    --abort-c) ABORT_C="$2"; shift;;
    *) echo "unknown arg: $1" >&2; exit 1;;
  esac
  shift
done

LOGDIR="$HOME/gpu-thermal-logs"
mkdir -p "$LOGDIR"
CSV="$LOGDIR/probe-$(date +%Y%m%d-%H%M%S).csv"
API_KEY_FILE="$HOME/.config/vllm/api-keys"
KERNEL_BASELINE=$(dmesg 2>/dev/null | grep -cE 'NVRM|Xid'); KERNEL_BASELINE=${KERNEL_BASELINE:-0}

echo "timestamp,index,temp_c,power_w,util_pct,sm_mhz,fan_pct,mem_used_mib" > "$CSV"
echo "[probe] logging to $CSV  (abort=${ABORT_C}C warn=${WARN_C}C)"

LOAD_PIDS=()
start_load() {
  local key=""
  [[ -r "$API_KEY_FILE" ]] && key=$(head -1 "$API_KEY_FILE")
  local model
  model=$(curl -sf -m 5 -H "Authorization: Bearer $key" "http://127.0.0.1:$PORT/v1/models" \
          | grep -o '"id":"[^"]*"' | head -1 | cut -d'"' -f4)
  if [[ -z "$model" ]]; then
    echo "[probe] no model answering on :$PORT — start one with llmctl first" >&2
    return 1
  fi
  echo "[probe] load: $CONC streams against $model on :$PORT for ${DURATION}s"
  for i in $(seq 1 "$CONC"); do
    (
      while :; do
        curl -sf -m 180 "http://127.0.0.1:$PORT/v1/chat/completions" \
          -H "Authorization: Bearer $key" -H "Content-Type: application/json" \
          -d '{"model":"'"$model"'","max_tokens":1024,"temperature":1.0,"messages":[{"role":"user","content":"Write a long, detailed essay about the history of thermodynamics. Do not stop early."}]}' \
          > /dev/null
      done
    ) &
    LOAD_PIDS+=($!)
  done
}

stop_load() {
  for p in "${LOAD_PIDS[@]:-}"; do kill "$p" 2>/dev/null; done
  pkill -P $$ curl 2>/dev/null
  LOAD_PIDS=()
}
trap 'stop_load' EXIT

if [[ $LOAD -eq 1 ]]; then
  start_load || exit 1
fi

START=$SECONDS
END=$((SECONDS + DURATION))
PHASE="load"
[[ $LOAD -eq 0 ]] && PHASE="monitor"
RC=0

while :; do
  now=$SECONDS
  if [[ "$PHASE" == "load" && $now -ge $END ]]; then
    echo "[probe] duration reached, stopping load; ${COOLDOWN}s cooldown"
    stop_load; PHASE="cooldown"; END=$((now + COOLDOWN))
  elif [[ "$PHASE" == "cooldown" && $now -ge $END ]]; then
    break
  elif [[ "$PHASE" == "monitor" && $now -ge $END ]]; then
    break
  fi

  line=$(nvidia-smi --query-gpu=index,temperature.gpu,power.draw,utilization.gpu,clocks.sm,fan.speed,memory.used \
         --format=csv,noheader,nounits 2>/dev/null)
  ts=$(date +%H:%M:%S)
  maxt=0
  while IFS=, read -r idx t p u c f m; do
    t=$(echo "$t" | tr -d ' ')
    echo "$ts,$idx,$t,$p,$u,$c,$f,$m" >> "$CSV"
    [[ "$t" =~ ^[0-9]+$ ]] && (( t > maxt )) && maxt=$t
  done <<< "$line"

  kerr=$(dmesg 2>/dev/null | grep -cE 'NVRM|Xid'); kerr=${kerr:-0}
  if (( kerr > KERNEL_BASELINE )); then
    echo "[probe] NEW KERNEL NVRM/Xid ERROR — aborting load immediately"
    stop_load; RC=3; PHASE="cooldown"; END=$((SECONDS + COOLDOWN))
    KERNEL_BASELINE=$kerr
  fi
  if (( maxt >= ABORT_C )); then
    echo "[probe] ${maxt}C >= abort threshold ${ABORT_C}C — killing load, cooling down"
    stop_load; [[ $RC -eq 0 ]] && RC=2; PHASE="cooldown"; END=$((SECONDS + COOLDOWN))
  elif (( maxt >= WARN_C )); then
    echo "[probe] warn: max temp ${maxt}C @ ${ts} (phase=$PHASE)"
  fi
  sleep 2
done

echo "[probe] done (rc=$RC). Per-GPU maxima:"
awk -F, 'NR>1 {if ($3>m[$2]) m[$2]=$3; if ($4>p[$2]) p[$2]=$4} END {for (i in m) printf "  GPU %s: max %s C, max %s W\n", i, m[i], p[i]}' "$CSV"
echo "[probe] full log: $CSV"
exit $RC
