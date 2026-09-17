# Confirmed queue: original GLM NVFP4 high thinking

David explicitly requested adding/confirming the original GLM-5.3 NVFP4 high-thinking evaluation, distinct from GLM EXL3 high.

Queue: finish the currently running Qwen3.8 Flash-Next TP2 thinking-enabled comparison, then run original GLM NVFP4 with high reasoning across both Sparks and vision enabled.

Use the preserved glm53-flash-vision recipe as the starting point. Verify actual template reasoning_effort=high and reasoning/final answer separation before scoring. Do not assume enable_thinking has the same semantics as EXL3. Preserve original low-reasoning data.

Tests: deep reasoning, work quality/coding, tool calling, and all25 retained vision fixtures. Match the current high-thinking comparisons' ceilings (32768 text,16384 vision) and retry policy; record raw responses, usage, final-answer latency, truncations, and memory. Explicitly distinguish comparison against prior smaller-budget/diagnostic-composite NVFP4 results. No chat repointing, automatic rollback, or disabling memory guards. Results require actual successful execution, not merely queueing.
