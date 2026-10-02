#!/usr/bin/env bash
# llmctl TensorFold cluster contract, fixed-port keyfile-only authentication.
set -euo pipefail
PORT=8005
while (($#)); do
  case "$1" in
    --served-model-name) [[ "$2" == GLM-5.3-Flash-EXL3 ]] || exit 2; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --api-key) printf 'Use protected keyfile authentication, not argv.\n' >&2; exit 2 ;;
    *) printf 'Unsupported TensorFold launch argument\n' >&2; exit 2 ;;
  esac
done
PYTHON=/home/david/.venvs/tensorfold-frontend/bin/python
"$PYTHON" -c 'import aiohttp'
timeout 30 ssh -o BatchMode=yes -o ConnectTimeout=10 david@10.100.100.11 \
  'systemctl --user start glm53-tensorfold-memguard.service'
/home/david/work/glm53-tensorfold/start.sh
"$PYTHON" /home/david/work/llmctl/scripts/tensorfold_frontend.py --port "$PORT" &
frontend=$!
cleanup() { kill "$frontend" 2>/dev/null || true; wait "$frontend" 2>/dev/null || true; }
trap cleanup EXIT
trap 'exit 0' TERM INT
while kill -0 "$frontend" 2>/dev/null; do
  [[ "$(docker inspect --format '{{.State.Running}}' glm53-flash-tf-trial)" == true ]] || exit 1
  systemctl --user is-active --quiet glm53-tensorfold-memguard.service || exit 1
  remote=$(timeout 20 ssh -o BatchMode=yes -o ConnectTimeout=10 david@10.100.100.11 \
    'systemctl --user is-active --quiet glm53-tensorfold-memguard.service && docker inspect --format "{{.State.Running}}" glm53-flash-tf-trial') || exit 1
  [[ "$remote" == true ]] || exit 1
  sleep 10 &
  wait $! || true
done
wait "$frontend"
