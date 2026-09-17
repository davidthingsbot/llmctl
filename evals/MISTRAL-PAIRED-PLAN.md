# Authorized paired Mistral evaluation plan

David approved evaluating dual-Spark Mistral Medium3.5 NVFP4 in non-thinking mode first, then thinking mode, before returning to DeepSeek/GLM/Qwen for similar paired tests.

The checkpoint chat_template.jinja explicitly supports reasoning_effort none|high (default none) and renders MODEL_SETTINGS. Verify both live modes, tokenizer fidelity and reasoning/final separation before the full suite. Do not substitute a think-step-by-step prompt.

Hold constant: same checkpoint, quantization, two-node serving configuration, one-image vision path, all25 retained visual fixtures, text prompts, exact grading and retry policy. Use equal generous output ceilings in BOTH modes: proposed32768 text /16384 vision, subject to live template/response sanity checks and128K server context. Record any truncation separately, never call it a perception/reasoning failure without inspection. Record request latency to final answer, generated tokens (including reasoning), preserved raw output, memory and throughput. A setting label alone does not establish equal reasoning effort across different models.

Run sequentially: none vision + work + deep reasoning + concurrency, then high equivalents. No automatic rollback or chat repointing; guard both nodes. Per-task JSON and logs must survive interruption. Never omit numerical dependencies: run eval interpreter with NumPy and Pillow.

Dual-Spark runtime preparation is currently delegated. Mistral weights and isolated tokenizer are already mirrored. Deployment report will be /home/david/work/mistral-vision/tp2/REPORT.md. Do not start the battery until that report and live health/image/mode checks verify readiness.
