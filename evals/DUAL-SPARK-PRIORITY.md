# Experiment priority: dual Spark, multimodal

David clarified that experiments should focus on models using BOTH Sparks, prioritizing vision/multimodal capability. Single-device launches are only diagnostic steps, not the evaluation target. Do not spend a full benchmark campaign on a single-Spark candidate without explicit direction.

Mistral's current trial is TP1 on Spark0, 32K context. It should not be presented as the desired final configuration. Before a TP2 trial, stage the checkpoint and a compatible runtime on Spark1; direct checks found neither /home/david/models/hf/Mistral-Medium-3.5-128B-NVFP4 nor /home/david/.venvs/vllm/bin/vllm there. No Mistral-named recipe was found in the local spark-vllm-docker checkout. This does not prove TP2 unsupported; it means a distributed deployment must be prepared and tested rather than assumed.

Current dual-Spark multimodal candidates: original GLM NVFP4 with tested vision, GLM EXL3 with vision enabled but not yet equivalently image-evaluated, Qwen Flash-Next NVFP4 TP2 with prior basic vision smoke. DeepSeek V4.1 EXL3 is dual Spark but its selected recipe is text-only due to its kernel restriction.
