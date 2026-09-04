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
cd ~/src/spark-vllm-docker || exit 1
exec ./launch-cluster.sh -t vllm/vllm-openai:glm53-flash \
  -v /home/david/models/hf:/models \
  -e TORCHINDUCTOR_COMPILE_THREADS=1 -e MAX_JOBS=1 -e NVCC_THREADS=1 -e VLLM_ENGINE_READY_TIMEOUT_S=3600 \
  exec vllm serve /models/GLM-5.3-Flash-NVFP4 \
    --served-model-name glm53-flash-nvfp4 --host 0.0.0.0 --port 8000 \
    --tensor-parallel-size 2 --gpu-memory-utilization "${GPU_UTIL:-0.83}" \
    --max-model-len "${MAX_LEN:-65536}" --max-num-seqs "${MAX_SEQS:-4}" \
    --max-num-batched-tokens "${MAX_BATCHED:-4096}" --limit-mm-per-prompt '{"image":0,"video":0}' \
    --no-enable-prefix-caching --no-enable-flashinfer-autotune \
    --enable-auto-tool-choice --tool-call-parser glm47 --reasoning-parser glm45
