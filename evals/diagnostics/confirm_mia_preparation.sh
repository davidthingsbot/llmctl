#!/usr/bin/env bash
# Wait for initial preparation, then require an actual successful idempotent prepare exit.
set -euo pipefail
export PATH=/home/david/.local/bin:$PATH
cd /home/david/work/glm53-tensorfold-mia-20261004
state=/home/david/.local/state/glm53-tensorfold-mia-v15
mkdir -p "$state"
trap 'touch "$state/authorized-prepare-failed"' ERR
exec 9>"$state/prepare.lock"
flock 9
flock -u 9
exec 9>&-
./scripts/prepare.sh > /home/david/.cache/glm53-mia-v15-prepare-confirm.log 2>&1
touch "$state/authorized-prepare-success"
