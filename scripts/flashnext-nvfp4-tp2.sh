#!/bin/bash
# Qwen3.8-Flash-Next NVFP4 (RadixArk, 125.9 GiB: NVFP4 experts/compute, the 51 GiB n-gram table at FP8, some
# tensors bf16) as TP2 across dw-spark0 (head) + dw-spark1, official image vllm/vllm-openai:qwen38-flash-next.
# Why this one and not the FP8: the n-gram table is allocated IN FULL on every TP rank (measured 2026-09-04),
# so per box = half the compute weights + the whole table: FP8 61+51 = 112 GiB (does not fit), NVFP4 ~37+51
# = ~88 GiB (fits like GLM did at 88). Config follows the GB10 lane that worked for GLM: text-only, prefix
# caching off (vllm#54173 GDN crash on GB10), 4096 batched tokens, compiler serialised, 16 sessions (GLM's
# ladder peaked at 16). Vision stays off for now — David wants it back (cap resolution, one image) once the
# text path is measured. Pre-flight with --load-format dummy before any real load; memory guards armed.
# Pre-flight 1 (2026-09-04 18:17, 4096 batched tokens): dummy weights 85.16 GiB per box as predicted, 20 GiB
# free after load, then the first forward/compile took ~17 GiB in 10 s and the launch died at 3.4 GiB. With
# the table fully allocated at load this transient is activation, not the table, so it scales with the batched
# token limit: 4096 -> 1024 for pre-flight 2.
cd ~/src/spark-vllm-docker || exit 1
exec ./launch-cluster.sh -t vllm/vllm-openai:qwen38-flash-next \
  -v /home/david/models/hf:/models \
  -e TORCHINDUCTOR_COMPILE_THREADS=1 -e MAX_JOBS=1 -e NVCC_THREADS=1 -e VLLM_ENGINE_READY_TIMEOUT_S=3600 \
  exec vllm serve /models/Qwen3.8-Flash-Next-NVFP4 \
    --served-model-name qwen38-flash-next-nvfp4 --host 0.0.0.0 --port 8002 \
    --tensor-parallel-size 2 --gpu-memory-utilization "${GPU_UTIL:-0.83}" \
    --max-model-len "${MAX_LEN:-131072}" --max-num-seqs "${MAX_SEQS:-16}" \
    --max-num-batched-tokens "${MAX_BATCHED:-1024}" --limit-mm-per-prompt '{"image":0,"video":0}' \
    --no-enable-prefix-caching --no-enable-flashinfer-autotune \
    --enable-auto-tool-choice --tool-call-parser qwen3_xml --reasoning-parser qwen3 "$@"
