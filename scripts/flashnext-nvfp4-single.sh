#!/bin/bash
# Qwen3.8-Flash-Next NVFP4 (RadixArk) on ONE Spark via blazux/qwen3.8-Flash-DGX: the 44 GiB n-gram table is
# served from NVMe by mmap instead of living in the unified pool, so the model fits a single GB10 with ~76 GiB
# of weights resident. The image (qwen38-flash-dgx, built 2026-09-04 from the same vllm-openai:qwen38-flash-next
# digest) also fixes prefix caching, the non-deterministic top-k, and the FP8-PLE loader bug (vllm#54765) that
# stops stock vLLM from loading this checkpoint at all. Weights: ~/models/hfcache is a hardlink view of
# ~/models/hf/Qwen3.8-Flash-Next-NVFP4 in the HF cache layout serve.sh expects. Vision stays ON (no mm limit).
# llmctl appends --served-model-name/--port/--api-key: they go to vLLM via EXTRA (last occurrence wins) and the
# host port comes from --port. The container is named vllm_node so the memory guard covers it, and this script
# stays in the foreground on the container so systemd owns its lifetime.
PORT_HOST=8002; EXTRA_ARGS=()
while (($#)); do case "$1" in --port) PORT_HOST="$2"; EXTRA_ARGS+=("$1" "8000"); shift 2;; *) EXTRA_ARGS+=("$1"); shift;; esac; done
cd ~/src/qwen3.8-Flash-DGX || exit 1
NAME=vllm_node IMAGE=qwen38-flash-dgx HF_CACHE=/home/david/models/hfcache PORT=$PORT_HOST \
  SEQS="${MAX_SEQS:-16}" GPU_MEM="${GPU_UTIL:-0.80}" MTP="${MTP:-2}" CTX="${MAX_LEN:-262144}" PREWARM=1 \
  EXTRA="${EXTRA_ARGS[*]}" scripts/serve.sh || exit 1
trap 'docker rm -f vllm_node >/dev/null 2>&1' TERM INT
docker logs -f vllm_node &
docker wait vllm_node
