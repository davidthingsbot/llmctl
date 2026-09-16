# Synthetic vision diagnostics v1

A small local diagnostic suite, not a standardized multimodal benchmark. Nine generated PNGs: three easy, three medium, three provisionally hard. Pillow and DejaVuSans.ttf are required for fixture generation; run with uv's isolated Pillow environment. No OCR tools or external image analysis feed the evaluated model.

## Tasks
- Easy: access-code OCR; left/right color identification; orange-circle counting with shape/color distractors.
- Medium: bar-chart reading and difference; inventory-table lookup/filtering; flowchart branch selection.
- Hard: 18-row ledger filtering and summation; two-stage crossing-wire connectivity; schedule overlap and free-slot reasoning.

The hard tier is a design hypothesis, not calibrated difficulty. Initial GLM NVFP4 scored perfectly, so these tasks provide a functional baseline rather than discriminating top-performing models. Future versions should add visually complex screenshots, dense diagrams, near-matching text, counterfactual variants and degraded images. Do not describe this result as broad real-world vision accuracy.

## Scoring and reproducibility
Each requested field is worth one point (20 fields total). Exact typed JSON comparison; optional single JSON code fence accepted. List order is explicit in prompts. Wrong schema/case/type counts as wrong; inspect raw outputs before attributing a failure to perception. Also report perfect tasks and tier totals. No retries. Temperature zero, reasoning_effort=low, 1024 output tokens. This setting is GLM-specific, not automatically semantically equivalent on other model templates.

Fixtures have deterministic ground truth, saved expected answers and image SHA256 in each result. Only the question and image enter the model request: neither filenames nor expected answers are sent. Each request is a fresh conversation. Raw API response, usage, latency, finish reason and checks are checkpointed atomically after each task. Transport errors abort the run rather than being reported as a low model score.

## Run
```
uv run --no-project --with pillow python -m unittest discover -s evals -p test_vision_suite.py
uv run --no-project --with pillow python evals/vision_suite.py \
  --fixtures evals/fixtures/vision-v1 \
  --url http://127.0.0.1:8006/v1/chat/completions \
  --model glm53-flash-nvfp4-vision \
  --key-file /home/david/.config/vllm/api-keys \
  --output evals/results/dw-spark0/vision-v1-glm53-nvfp4.json
```
Manifest contains local absolute image paths; regenerate fixtures when moving to another checkout/machine (remove or rename the manifest, or call vision_fixtures.build_suite for that directory). Never regenerate in place while a test is running.

## First measured result
Original GLM-5.3 NVFP4 with vision, TP2, 128K context, image limit 1, video off, headless:
- Easy 4/4 fields, medium 7/7, hard 9/9.
- 9/9 perfect tasks, 20/20 fields, no truncation or API errors.
- Sum of request wall times: 48.9 seconds. Not a throughput benchmark.
- Post-run health HTTP 200; approx. 13/14 GiB MemAvailable head/worker. These are after-run readings, not continuously sampled minima.
- Data: results/dw-spark0/vision-v1-glm53-nvfp4.json.
- Preview: fixtures/vision-v1/contact-sheet.png, visually inspected before running.
