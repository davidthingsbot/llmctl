#!/bin/bash
# GLM-5.3-Flash (RedHatAI NVFP4, 184.2 GiB, 320B-A18B, Glm5Next: 45 layers, linear attention + DeepSeek sparse
# attention, 288 experts / 8 active) as TP2 across dw-spark0 (head) + dw-spark1. Image vllm/vllm-openai:glm53-flash
# (the qwen38-flash-next image has no Glm5Next in its registry). Launcher: eugr/spark-vllm-docker, no Ray.
# Sizing: 92 GiB of weights per box + ~14 GiB runtime, so util 0.83 (101 GiB) leaves ~9 GiB for activations
# and KV and ~6 GiB for the OS. Text-only, small batch, prefix caching off (vllm#54458 hybrid page alignment),
# compiler serialised, downloads paused during load. Memory guard (~/ops/memguard.sh) armed on both boxes.
#
# RESULT 2026-09-04 08:31: MEMORY FITS, SOFTWARE DOES NOT. Weights loaded in 5m50s (11 shards stream far better
# than Flash-Next's 131), 88.45 GiB per box, and available memory held at 17-23 GiB through compile and CUDA
# graph profiling. Then the MLA cache-write kernel asserted: "concat_and_cache_mla: pe_dim must be 64 for
# fp8_ds_mla". GB10 is sm_121, so vLLM picks FLASHINFER_MLA_SPARSE_SM120, whose packed KV layout hardcodes
# DeepSeek's 512 NoPE + 64 RoPE entry; GLM-5.3-Flash's MLA is rope-free (qk_rope_head_dim=0, nope 256, lora 512)
# and has no sparse-attention path on the SM120 family in this image. Exact match: vllm-project/vllm#53963
# (open, 2026-08-26). bf16 KV fails differently (no backend), and the community got TP2 working on 2x RTX PRO
# 6000 only with a third-party overlay carrying several kernel workarounds. Not a flag fix. Parked.
#
# UNPARKED the same morning: Libertai/vllm-sparse-mla-blackwell is that kernel, built for sm_120/121, GB10 listed
# as "verified, serving production", with a 2x GB10 GLM-5.3-Flash table in its README (14.5 tok/s plain, 24 with
# MTP; CUDA graphs a net loss on GB10, eager + fp8 KV the best balance). Built on spark0 with GLM53_ARCHS=121a
# into ~/opt/glm53ext (mounted at /opt/ext, on PYTHONPATH, enabled by env). Config below follows their GB10 lane
# and the TP2 config in vllm#53963 (2026-08-31): eager, fp8 KV, block 256, flashinfer_cutlass MoE, small batch.
# SERVING 2026-09-04 08:49: pre-flight (~/ops/dummy-check.sh, random weights) passed in 146 s; real load 5m52s,
# 88.44 GiB per box, healthy at 521 s. Available KV 9.21 GiB = 1,164,044 tokens (fp8 KV, hybrid model).
# Steady state ~8.5 GiB available on spark0, ~11 on spark1 — downloads must stay paused while it serves.
# Smoke test: coherent, 13.7-14.1 tok/s at batch 1 (README's 2x GB10 figure is 14.46; MTP would give ~24).
# Thinking is on by default; enable_thinking=false still yields reasoning-style prose before the answer.
# The template's only switch is reasoning_effort (low|high|max, default max); the evals use low.
# 2026-09-04 13:50: --max-num-seqs 2 -> 8. The 2 came from a 2x96GB config; the KV pool (1.16M tokens)
# is carved out at startup regardless, so the cap only sets occupancy. Ladder at 2 was 14/27/27/27;
# at 8 it was 14/26/44/69/69 (16 streams queued, 4->8 still 1.57x), so 16 at 14:20 the same day.
cd ~/src/spark-vllm-docker || exit 1
exec ./launch-cluster.sh -t vllm/vllm-openai:glm53-flash \
  -v /home/david/models/hf:/models -v /home/david/opt/glm53ext:/opt/ext \
  -e PYTHONPATH=/opt/ext -e VLLM_GLM53_CUDA_SPARSE_MLA=1 -e VLLM_GLM53_MOE_INPUT_SCALE=1.0 \
  -e VLLM_USE_BREAKABLE_CUDAGRAPH=0 \
  -e TORCHINDUCTOR_COMPILE_THREADS=1 -e MAX_JOBS=1 -e NVCC_THREADS=1 -e VLLM_ENGINE_READY_TIMEOUT_S=3600 \
  exec vllm serve /models/GLM-5.3-Flash-NVFP4 \
    --served-model-name glm53-flash-nvfp4 --host 0.0.0.0 --port 8000 \
    --tensor-parallel-size 2 --gpu-memory-utilization "${GPU_UTIL:-0.83}" \
    --max-model-len "${MAX_LEN:-65536}" --max-num-seqs "${MAX_SEQS:-16}" \
    --max-num-batched-tokens "${MAX_BATCHED:-2048}" --limit-mm-per-prompt '{"image":0,"video":0}' \
    --kv-cache-dtype fp8 --block-size 256 --enforce-eager --disable-custom-all-reduce \
    --moe-backend flashinfer_cutlass --no-enable-flashinfer-autotune --no-enable-prefix-caching \
    --enable-auto-tool-choice --tool-call-parser glm47 --reasoning-parser glm45 "$@"
