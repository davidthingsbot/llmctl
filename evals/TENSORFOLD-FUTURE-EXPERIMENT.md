# TensorFold — future experiment

Status: recorded for future consideration; not authorized for deployment or scheduled.

David requested preserving this candidate after research into MiaAI Lab's TensorFold recipes.

## Candidates

- Qwen3.8 Flash Next on one DGX Spark: https://github.com/MiaAI-Lab/Qwen3.8-Flash-Next-Single-DGX-Spark-TensorFold
- TensorFold: https://github.com/MiaAI-Lab/TensorFold
- GLM CUDA support: https://github.com/ashhart/TensorFold/blob/main/docs/recipes/glm-5.3-flash.md

## Research findings, not local measurements

Mia's Qwen recipe reports 62.4 tok/s single-stream prose and 119.3 aggregate at five streams, 262144 context per stream, thinking, tools, image/video input. It uses a different ~106 GiB checkpoint. Default estimated memory is 102.5 GiB on one Spark; four streams offer more headroom.

TensorFold supports GLM on two CUDA ranks but serves one GLM request at a time. Our Mia EXL3 checkpoint is experimental; published affine-checkpoint throughput cannot be attributed to our EXL3 weights.

## Proposed evaluation, pending authorization

Add a separate reversible llmctl recipe, preserve the GLM default and rollback state, retain memory guards, and verify that guards cover the actual backend. Compare reasoning-enabled engineering, tools and vision, then matched publisher and realistic throughput protocols. Do not load alongside the existing dual-Spark GLM. Do not download weights, stop services, or repoint consumers without approval.
