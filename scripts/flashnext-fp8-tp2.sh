#!/bin/bash
# Qwen3.8-Flash-Next-FP8 (172.78 GiB official checkpoint) as TP2 across dw-spark0 (head) + dw-spark1,
# official image vllm/vllm-openai:qwen38-flash-next, eugr/spark-vllm-docker launcher, no Ray.
#
# Sizing (measured 2026-09-04): weights land at 86.22 GiB PER SPARK (61 GiB compute + half of the
# vocab-sharded 51 GiB n-gram table). First attempt at --gpu-memory-utilization 0.80 / 256K context
# took spark0 DOWN: NVRM out-of-memory from 00:25 through 00:32, reboot 00:34, with the GLM download
# and an open-webui pull also churning page cache. Budget now 0.77 = 93.6 GiB, leaving ~7 GiB for
# activations + KV, and NOTHING else may run on either box during load (pause downloads first).
# Prefix caching OFF (vllm#54173 illegal memory access in the GDN path on GB10).
# No VLLM_PLE_CPU_OFFLOAD: on GB10 host and GPU memory are one pool, offload buys nothing.
# Compiler serialised (TORCHINDUCTOR_COMPILE_THREADS=1) per the dw-spark0 inventory notes.
# Attempt 2 (0.77, 128K, 4 seqs) loaded fine and then lost 22 GiB PER BOX in the 40 s after loading:
# the memory-profiling dummy run at the default 16384 batched tokens through 512 experts, plus the
# multimodal profile (this checkpoint carries a 27-layer vision tower, encoder budget 16384 tokens).
# Memory guards killed both containers at 2 GiB available; both machines survived. Attempt 3 caps the
# profile: text-only (--limit-mm-per-prompt image=0,video=0) and 4096 batched tokens.
cd ~/src/spark-vllm-docker || exit 1
exec ./launch-cluster.sh -t vllm/vllm-openai:qwen38-flash-next \
  -v /home/david/models/hf:/models \
  -e TORCHINDUCTOR_COMPILE_THREADS=1 -e MAX_JOBS=1 -e NVCC_THREADS=1 \
  exec vllm serve /models/Qwen3.8-Flash-Next-FP8 \
    --served-model-name qwen38-flash-next-fp8 --host 0.0.0.0 --port 8000 \
    --tensor-parallel-size 2 --gpu-memory-utilization "${GPU_UTIL:-0.77}" \
    --max-model-len "${MAX_LEN:-131072}" --max-num-seqs "${MAX_SEQS:-4}" \
    --max-num-batched-tokens "${MAX_BATCHED:-4096}" --limit-mm-per-prompt '{"image":0,"video":0}' \
    --no-enable-prefix-caching --no-enable-flashinfer-autotune \
    --enable-auto-tool-choice --tool-call-parser qwen3_xml --reasoning-parser qwen3
