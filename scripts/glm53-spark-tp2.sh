#!/bin/bash
# GLM-5.3-Flash NVFP4-Spark (local-inference-lab, 174.8 GiB) as TP2 across dw-spark0 + dw-spark1 on the eugr
# B12X recipe (recipes/glm-5.3-flash.yaml, added 2026-09-04), verbatim except: model by path, and util/KV
# left as env knobs because the recipe's 0.87 + 10G KV assumes the whole 128 GB board; on these boxes the
# pre-flight decides. This is the same model as glm53-flash (RedHatAI NVFP4 + Libertai kernel, 14 tok/s);
# the point is the B12X stack + 5-token MTP speculative decode that gave DeepSeek 35-59 tok/s.
cd ~/src/spark-vllm-docker || exit 1
exec ./launch-cluster.sh -t eugr/spark-vllm-b12x:latest \
  -v /home/david/models/hf:/models \
  -e CUTE_DSL_ARCH=sm_121a -e SAFETENSORS_FAST_GPU=1 -e VLLM_ENABLE_ROCE_ALLREDUCE=1 -e VLLM_ROCE_ALLREDUCE_MAX_SIZE=2MB \
  -e VLLM_WORKER_MULTIPROC_METHOD=spawn -e VLLM_SSM_CONV_STATE_LAYOUT=DS -e VLLM_USE_AOT_COMPILE=1 \
  -e VLLM_USE_MEGA_AOT_ARTIFACT=1 -e VLLM_USE_V2_MODEL_RUNNER=1 -e VLLM_ENABLE_PCIE_ALLREDUCE=0 -e B12X_POLICY_MODE=auto \
  -e INSTANTTENSOR_BACKEND=BUFFERED -e INSTANTTENSOR_BUFFER_SIZE=67108864 -e INSTANTTENSOR_CHUNK_SIZE=8388608 \
  -e INSTANTTENSOR_CONCURRENCY=1 -e INSTANTTENSOR_IO_DEPTH=3 \
  -e TORCHINDUCTOR_COMPILE_THREADS=1 -e MAX_JOBS=1 -e NVCC_THREADS=1 -e VLLM_ENGINE_READY_TIMEOUT_S=3600 \
  exec vllm serve /models/GLM-5.3-Flash-NVFP4-Spark \
    --served-model-name glm53-spark --host 0.0.0.0 --port 8003 \
    --tensor-parallel-size 2 --pipeline-parallel-size 1 --decode-context-parallel-size 1 \
    --mamba-cache-mode align --enable-prefix-caching --enable-chunked-prefill \
    --dtype bfloat16 --kv-cache-dtype fp8 --quantization modelopt_mixed \
    --attention-backend B12X --block-size 256 --moe-backend b12x --linear-backend b12x \
    --no-enable-flashinfer-autotune \
    --load-format instanttensor --model-loader-extra-config '{"instanttensor_copy":false}' \
    --max-model-len "${MAX_LEN:-262144}" --max-num-seqs "${MAX_SEQS:-8}" --max-num-batched-tokens "${MAX_BATCHED:-4096}" \
    --speculative-config '{"method":"mtp","num_speculative_tokens":5,"moe_backend":"humming","attention_backend":"B12X"}' \
    --reasoning-parser glm45 --tool-call-parser glm47 --enable-auto-tool-choice \
    --kv-cache-memory-bytes "${KV_BYTES:-8G}" --gpu-memory-utilization "${GPU_UTIL:-0.83}" "$@"
