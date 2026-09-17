#!/usr/bin/env bash
# battery-dw-amd-linux.sh <port> <served-model-id> [work|reason|conc|vision|all]...
# Runs the three-part baseline + the three vision suites against a running
# llama.cpp model on this box, writing evals/results/DW-AMD-LINUX/ under the
# leaderboard's filename convention (full-*.json, vision-*.json).
set -euo pipefail
PORT="$1"; MODEL="$2"; shift 2; PARTS="${*:-all}"
cd /home/david/work/llmctl
export PATH=/usr/local/cuda/bin:$HOME/.local/bin:$PATH   # nvcc + iverilog/vvp for the graders
URL="http://127.0.0.1:$PORT/v1/chat/completions"
KEY="$HOME/.config/llama.cpp/api-keys"
OUT="evals/results/DW-AMD-LINUX"; mkdir -p "$OUT"
PY=(uv run --no-project --python 3.12 --with numpy --with pillow python)   # numpy for the ML graders, pillow for vision
want() { [[ "$PARTS" == *all* || "$PARTS" == *"$1"* ]]; }
t0=$(date +%s)
want work   && "${PY[@]}" evals/work_quality_suite.py   --url "$URL" --model "$MODEL" --key-file "$KEY" --extended --output "$OUT/full-$MODEL.json"
want reason && "${PY[@]}" evals/deep_reasoning_suite.py --url "$URL" --model "$MODEL" --key-file "$KEY" --extended --output "$OUT/full-deep-reasoning-$MODEL.json"
want conc   && "${PY[@]}" evals/concurrency_sweep.py    --url "$URL" --model "$MODEL" --key-file "$KEY" --output "$OUT/full-concurrency-$MODEL.json"
if want vision; then
  # Qwen3.5 ignores GLM's reasoning_effort knob and thinks until max_tokens, so the
  # primary vision rows run with thinking off; the -think4096 rows give thinking a budget.
  NOTHINK='{"enable_thinking": false}'
  for fx in vision-v1:vision-v1 vision-v2:vision-hard6 vision-candidates-extra10:vision-extra10; do
    dir=${fx%%:*}; tag=${fx##*:}
    "${PY[@]}" evals/vision_suite.py --fixtures evals/fixtures/$dir --url "$URL" --model "$MODEL" --key-file "$KEY" --template-kwargs "$NOTHINK" --output "$OUT/$tag-$MODEL-nothink.json"
    "${PY[@]}" evals/vision_suite.py --fixtures evals/fixtures/$dir --url "$URL" --model "$MODEL" --key-file "$KEY" --max-tokens 4096 --output "$OUT/$tag-$MODEL-think4096.json"
  done
fi
echo "battery done for $MODEL in $(( $(date +%s) - t0 )) s"
python3 evals/leaderboard.py DW-AMD-LINUX > "$OUT/LEADERBOARD.md" && head -12 "$OUT/LEADERBOARD.md"
