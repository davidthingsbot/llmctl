#!/usr/bin/env bash
# Preserve healthy loaded ranks on an orchestration/adapter failure.
set -euo pipefail
if [[ "${SERVICE_RESULT:-success}" != success ]]; then
  here=$(docker inspect --format '{{.State.Running}}' glm53-flash-tf-trial 2>/dev/null || true)
  there=$(timeout 20 ssh -o BatchMode=yes -o ConnectTimeout=10 david@10.100.100.11 \
    'docker inspect --format "{{.State.Running}}" glm53-flash-tf-trial' 2>/dev/null || true)
  # Only a confirmed stopped rank justifies teardown after a launcher failure.
  # SSH/Docker failures are unknown state, not proof the healthy ranks died.
  if [[ "$here" != false && "$there" != false ]]; then
    printf 'Adapter failed; preserving running/unknown TensorFold ranks for diagnosis.\n'
    exit 0
  fi
fi
exec /home/david/work/glm53-tensorfold/stop.sh
