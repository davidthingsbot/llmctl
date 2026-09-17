#!/usr/bin/env bash
# Mia EXL3 launcher adapter for llmctl's foreground cluster contract.
set -euo pipefail
while (($#)); do
  case "$1" in
    --served-model-name) export SERVED_MODEL_NAME="$2"; shift 2 ;;
    --port) export PORT="$2"; shift 2 ;;
    --api-key) export VLLM_API_KEY="$2"; shift 2 ;;
    *) printf 'Unsupported llmctl launch argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done
cd "${GLM53_EXL3_DIR:-/home/david/work/glm53-exl3}"
./start.sh start
# llmctl's ExecStopPost removes vllm_node on both nodes. Remain in foreground
# until that container exits, preserving its exit status for systemd.
status=$(docker wait vllm_node)
exit "$status"
