#!/usr/bin/env bash
# One-shot authorized runtime-only trial; preparation failure does not stop production.
set -euo pipefail
export PATH=/home/david/.local/bin:$PATH
cd /home/david/work/glm53-tensorfold-tr3-v110
state=/home/david/.local/state/glm53-tensorfold-tr3-v110
mkdir -p "$state"
trap 'touch "$state/authorized-prepare-failed"' ERR
./scripts/prepare.sh > /home/david/.cache/glm53-tr3-v110-prepare.log 2>&1
touch "$state/authorized-prepare-success"
trap - ERR
cd /home/david/work/llmctl
exec uv run --no-project --with numpy --with pillow python evals/diagnostics/run_tr3_tensorfold_v110.py > /home/david/.cache/glm53-tr3-v110-evaluation.log 2>&1
