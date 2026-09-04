#!/bin/bash
# DeepSeek-V4-Flash-0731 (official FP8 checkpoint, 155.4 GiB, 48 shards; experts MXFP4, attention FP8) as TP2
# across dw-spark0 (head) + dw-spark1. This is the one model with an actual dual-Spark recipe:
# eugr/spark-vllm-docker recipes/deepseek-v4-flash-0731.yaml on their prebuilt B12X image (sm_121 kernels),
# confirmed clean on 2x GB10 on 2026-09-04 with the 2026-09-03 build (eugr issue "DSV4F-0731 on b12x").
# The official vllm-openai:deepseekv4-flash-vision image has an open garbled-output bug on SM120 (vllm#50773).
# Env + command below are the recipe's, verbatim, with two deliberate changes for 121 GiB boxes:
#   gpu_memory_utilization 0.85 -> 0.80 (78 GiB of weights + ~14 GiB runtime; 0.85 would leave ~4 GiB)
#   max_num_batched_tokens 8192 -> 4096 (the profiling transient scales with it)
# Pre-flight with --load-format dummy (~/ops/dummy-check.sh) before any real load. Memory guards on both boxes.
cd ~/src/spark-vllm-docker || exit 1
exec ./launch-cluster.sh -t eugr/spark-vllm-b12x:latest \
  --apply-mod mods/instanttensor-hybrid-draft-loader \
  -v /home/david/models/hf:/models \
  -e CUTE_DSL_ARCH=sm_121a -e VLLM_USE_AOT_COMPILE=1 -e VLLM_USE_BREAKABLE_CUDAGRAPH=0 \
  -e VLLM_USE_MEGA_AOT_ARTIFACT=1 -e VLLM_MEMORY_PROFILE_INCLUDE_ATTN=1 -e VLLM_USE_FLASHINFER_SAMPLER=1 \
  -e VLLM_USE_B12X_WO_PROJECTION=1 -e VLLM_USE_B12X_MHC=1 -e VLLM_USE_B12X_FP8_GEMM=1 -e VLLM_USE_B12X_MOE=1 \
  -e VLLM_USE_B12X_SPARSE_INDEXER=1 -e VLLM_USE_V2_MODEL_RUNNER=1 -e VLLM_MOE_SKIP_PADDING=0 \
  -e B12X_MLA_SM120_UNIFIED=1 -e B12X_MOE_FORCE_A8=1 \
  -e TORCHINDUCTOR_COMPILE_THREADS=1 -e MAX_JOBS=1 -e NVCC_THREADS=1 -e VLLM_ENGINE_READY_TIMEOUT_S=3600 \
  exec vllm serve /models/DeepSeek-V4-Flash-0731 \
    --served-model-name deepseek-v4-flash --host 0.0.0.0 --port 8001 \
    --trust-remote-code --tensor-parallel-size 2 \
    --kv-cache-dtype fp8 --block-size 256 \
    --max-model-len "${MAX_LEN:-auto}" --max-num-seqs "${MAX_SEQS:-8}" \
    --max-num-batched-tokens "${MAX_BATCHED:-4096}" \
    --gpu-memory-utilization "${GPU_UTIL:-0.80}" \
    --enable-prefix-caching \
    --tokenizer-mode deepseek_v4 --tool-call-parser deepseek_v4 --enable-auto-tool-choice \
    --reasoning-parser deepseek_v4 \
    --reasoning-config '{"reasoning_parser":"deepseek_v4","reasoning_start_str":"","reasoning_end_str":""}' \
    --default-chat-template-kwargs.thinking=true --default-chat-template-kwargs.reasoning_effort=high \
    --load-format instanttensor \
    --moe-backend b12x --linear-backend b12x --attention-backend B12X \
    --max-cudagraph-capture-size 48 \
    --compilation-config '{"cudagraph_mode":"FULL_AND_PIECEWISE","custom_ops":["all"]}' \
    --speculative-config '{"method":"dspark","num_speculative_tokens":5,"draft_sample_method":"probabilistic","attention_backend":"B12X"}' "$@"
