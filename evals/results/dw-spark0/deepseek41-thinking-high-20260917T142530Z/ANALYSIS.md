# DeepSeek V4.1 high-thinking results

Completed high-thinking reasoning, work-quality, and tool protocol checks. Final live health HTTP200. Both Sparks used, original256K serving configuration retained; no vision support in this recipe.

- Reasoning299/302 (99.0%),586.59s (9.8min), no truncations, two retries.
- Work397/438 (90.6%),3471.99s (57.9min), four retries; stream_reassembler hit output cap. Completion tokens151338 incl80879 retry tokens; expensive tails dominate.
- Thinking-off baseline: reasoning232/302, work411/438. Different output ceilings:12000 off vs32768 on; cannot isolate thinking alone.
- Latest GLM EXL3 low: reasoning295/302 in269.3s; work371/438. Historical saved GLM work regrade409 is a different output set, not latest run.
- Work losses: BOM9/10 (retry perfect but discounted), COBS17/24 (retry unsuccessful), stream_reassembler0/24 (truncation/final-format failure), hard Verilog21/30 (retry30/30, discounted).
- Tool call and synthetic-tool-result roundtrip passed. No inference request errors reported in quality outputs.

Conclusion: strong thinking-enabled text reasoning, modest gain over GLM low on this set at~2.2x suite duration; work score does not improve over thinking-off because of output-budget/retry failures. Do not describe truncated cases as proven inability. The larger output cap still did not guarantee final answer completion.

Ten-minute report job removed after completion. Next authorized model: GLM EXL3 with explicit high thinking, text reasoning first, work/tool/vision afterward; no automatic rollback or repointing.
