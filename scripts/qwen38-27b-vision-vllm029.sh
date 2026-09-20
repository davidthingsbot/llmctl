#!/usr/bin/env bash
# Qwen3.8-27B-FP8 WITH VISION, served by vLLM 0.29.0 from an isolated venv.
#
# WHY A LAUNCH SCRIPT AND NOT BACKEND=vllm: llmctl's VLLM_BIN is machine-wide
# (machine.conf) and still points at the 0.23.0 venv that serves every other
# vLLM model here. This model needs 0.29.0, so it is registered as
# BACKEND=cluster with NODES=local, which lets llmctl hand the serve args to
# this script instead of to VLLM_BIN. Nothing else on the box moves.
#
# WHY 0.29.0 IS REQUIRED (measured 2026-09-19): on 0.23.0 this model cannot
# serve images at all. mamba_cache_mode='align' is forced by the arch, and
# 0.23.0 asserts "Model Runner V2 has not yet supported mamba_cache_mode=
# 'align'", while the V1 runner dies in the multimodal profile run with
# AttributeError: 'NoneType' object has no attribute 'size'. Both runners are
# closed. 0.29.0 inverts that: align mode now REQUIRES the V2 runner, hence
# VLLM_USE_V2_MODEL_RUNNER=1 below. It is not optional.
#
# CUDA_HOME IS LOAD-BEARING: 0.29.0 refuses fp8 KV on FLASH_ATTN below SM90
# ("FP8 KV cache requires FA3 on SM90 or FA4 on SM100"), so on these sm_86
# 3090s the only fp8-KV backend is FlashInfer, which JIT-compiles kernels.
# /usr/bin/nvcc is CUDA 12.0 and rejects flashinfer's --compress-mode=size, so
# the venv's own nvcc 13.4 must come first on PATH.
# NOTE the venv shipped MISMATCHED CUDA packages (nvidia-cuda-nvcc 13.4.92 vs
# nvidia-cuda-runtime 13.0.96), which failed CCCL's nvcc-vs-headers equality
# check. Fixed by pinning nvidia-cuda-runtime==13.4.92 in that venv. If this
# script starts failing on a "CUDA compiler and CUDA toolkit headers are
# incompatible" error, re-check that those two packages still match.
set -euo pipefail
VENV=/home/david/.venvs/vllm-0.29.0
export CUDA_HOME="$VENV/lib/python3.12/site-packages/nvidia/cu13"
export PATH="$CUDA_HOME/bin:$VENV/bin:$PATH"
export CUDA_VISIBLE_DEVICES=0,1
export VLLM_USE_FLASHINFER_SAMPLER=0
export VLLM_NO_USAGE_STATS=1
export HF_HUB_OFFLINE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export VLLM_USE_V2_MODEL_RUNNER=1
exec "$VENV/bin/vllm" serve /home/david/models/hf/Qwen3.8-27B-FP8 "$@"
