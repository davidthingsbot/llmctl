#!/bin/bash
# Qwen3.8-Flash-Next NVFP4 (RadixArk, 126 GiB) as TP2+EP+MTP3 across dw-spark0 (head) + dw-spark1, following
# MiaAI-Lab/Qwen3.8-Flash-Next-Dual-DGX-Sparks @ c2325b2 (2026-09-05; reproduced on 2x GB10 by AI-hobbyist88 #30
# with this exact checkpoint at 1M, calvarado2004 #41 needle-clean to 937K, chuck-ads #28 at 262K). Why this
# fits where the 09-04 attempt did not: with expert parallel and the recipe's patched FP8 PLE loader the 51 GiB
# n-gram table is sharded (~25 GiB per box) instead of replicated, so weights land at ~64.5 GiB per box.
# The recipe's four bind-mounted patches (extracted from the image and patched by its files/*.py) live at the
# same path on both boxes, ~/opt/flashnext-patch: ple_layer (FP8 PLE resolver, vllm#53899 logic), modelopt
# (MXFP8 shapes FlashInfer cannot run -> BF16 emulation, incl. all visual.*; FP8_BLOCK_SCALES MoE branch, unused
# here), and the two QSA files (fp8 KV cache, 1.70x the pool). The RadixArk checkpoint already declares the PLE
# dtype and has unquantized MTP experts, so the recipe's config.json shims (nvidia checkpoint only) are not
# needed; today's nvidia re-export breakage (#37/#38) does not apply. Launcher: eugr/spark-vllm-docker, no Ray
# (it adds --nnodes/--node-rank/--master-addr itself). Vision ON as the recipe verified (OCR at 4K). YaRN x4
# only above the native 262144. Serve args are the recipe's defaults verbatim (util 0.835, 8 seqs, 8192 batched).
# Pre-flight with ~/ops/dummy-check.sh before any real load; memory guards armed; page cache evicted first
# (recipe issue #35: a full page cache OOMs the load at 73-97% on GB10).
# RESULT 2026-09-06: SERVING. Real load 537-578 s, 65.7 GiB weights per box, healthy at ~12.5 min, coherent; vision
# works. util 0.835 (recipe default) left spark0 at 3.5 GiB available = the memguard line, so 0.78 is the default:
# 11/16 GiB free, fp8 KV pool 3.34M tokens (3.34 resident 1M requests). Batch-1 decode 36.7 tok/s thinking off.
# ~/ops/dummy-check.sh CANNOT gate this model: vLLM's dummy init upcasts fp8 params to fp16, and the 51B-entry PLE
# table becomes ~100 GiB (OOM-killed by the 110 GiB container cap in ~10 s). Guard real loads with memguard instead.
P=/home/david/opt/flashnext-patch; PKG=/usr/local/lib/python3.12/dist-packages/vllm
MAX_LEN="${MAX_LEN:-1000000}"; YARN=()
if [ "$MAX_LEN" -gt 262144 ]; then
  YARN=(--hf-overrides '{"text_config":{"rope_parameters":{"rope_type":"yarn","factor":4.0,"original_max_position_embeddings":262144}}}')
fi
cd ~/src/spark-vllm-docker || exit 1
exec ./launch-cluster.sh -t vllm/vllm-openai:qwen38-flash-next \
  -v /home/david/models/hf:/models \
  -v $P/ple_layer_patched.py:$PKG/models/qwen3_8_flash_next/nvidia/ple_layer.py:ro \
  -v $P/modelopt_patched.py:$PKG/model_executor/layers/quantization/modelopt.py:ro \
  -v $P/qsa_ops_patched.py:$PKG/models/qwen3_8_flash_next/nvidia/ops/qsa.py:ro \
  -v $P/qsa_nvidia_patched.py:$PKG/models/qwen3_8_flash_next/nvidia/qsa.py:ro \
  -e HF_HUB_OFFLINE=1 -e TRANSFORMERS_OFFLINE=1 -e VLLM_ALLOW_LONG_MAX_MODEL_LEN=1 \
  -e TORCHINDUCTOR_COMPILE_THREADS=1 -e MAX_JOBS=1 -e NVCC_THREADS=1 -e VLLM_ENGINE_READY_TIMEOUT_S=3600 \
  exec vllm serve /models/Qwen3.8-Flash-Next-NVFP4 \
    --served-model-name qwen38-flash-next-tp2 --host 0.0.0.0 --port 8004 \
    --tensor-parallel-size 2 --gpu-memory-utilization "${GPU_UTIL:-0.72}" \
    --max-model-len "$MAX_LEN" --max-num-seqs "${MAX_SEQS:-8}" --max-num-batched-tokens "${MAX_BATCHED:-4096}" \
    --kv-cache-dtype fp8 --load-format safetensors --safetensors-load-strategy lazy \
    --enable-chunked-prefill --enable-expert-parallel --all2all-backend allgather_reducescatter \
    --mm-encoder-tp-mode data \
    --speculative-config '{"method":"mtp","num_speculative_tokens":3}' \
    --compilation-config '{"mode":0,"cudagraph_mode":"FULL_DECODE_ONLY"}' \
    --enable-auto-tool-choice --tool-call-parser qwen3_coder --reasoning-parser qwen3 \
    "${YARN[@]}" "$@"
