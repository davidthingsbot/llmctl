# Qwen3.8 Flash-Next TP2 thinking-enabled (xhigh)

Complete; final live health HTTP200. enable_thinking=true, reasoning_effort=xhigh,32768 text output ceiling,16384 vision ceiling. Prior thinking-off results used12000 text/4096 vision ceilings, so improvements are not attributable solely to thinking.

- Reasoning287/302 (95.0%),1597.44s (26.6min). Truncations recorded on adversarial_epistemology and optimization_hard.
- Work357/438 (81.5%),7523.79s (125.4min). Truncations on ml_easy,cobs_codec,verilog_medium,verilog_hard. Total completion tokens346139 including105612 retry tokens. Output-budget exhaustion and long tails materially affect the result.
- Vision74/78 (94.9%),10.9min sum of request durations. Matches GLM EXL3 high aggregate but different misses: ledger2/3, waveform0/3; these finish normally, not truncated.
- Tool checks passed.

Latest GLM EXL3 high comparison: reasoning300/302 in6.9min; work415/438 in9.7min; vision74/78 in7.3min. Thus Qwen reaches comparable measured vision accuracy but not the same quality/latency on text suites in these configurations. This is one-run configuration evidence, not a universal model-family ranking.

Next user-confirmed run: original GLM NVFP4 high thinking, separate from EXL3, with same generous output ceilings and all25 vision tasks. No chat repointing or automatic rollback.
