# GLM EXL3 explicit thinking-on result

Complete, enable_thinking=true / reasoning_effort=high, TP2. Text output ceiling32768, vision16384; low-effort baseline used smaller ceilings, so not equal-compute comparison.

- Reasoning300/302 (99.3%),416.93s (6.9min), no truncation, one retry.
- Work415/438 (94.7%),580.37s (9.7min), no truncation, four retries.
- Vision74/78 (94.9%) across25 retained tasks, summed request time7.3min, no API errors; missed fields in resource scheduling, cross-reference, directed network reachability. All missed-task finishes were stop, not length.
- Thinking/final smoke and tool roundtrip passed; final endpoint health200.

DeepSeek V4.1 high comparison: reasoning299/302 in586.59s; work397/438 in3471.99s with stream-reassembly truncation. GLM is stronger/faster overall on these runs and has vision, but one-run differences and different model reasoning semantics are not controlled universal rankings.

Next authorized comparison: Qwen Flash-Next TP2 thinking enabled. Its shipped template supports reasoning_effort xhigh/medium/low, NOT high. Use supported default-strength xhigh, verify separate reasoning/final output and preserve exact request settings. No chat repointing or fallback restoration.
