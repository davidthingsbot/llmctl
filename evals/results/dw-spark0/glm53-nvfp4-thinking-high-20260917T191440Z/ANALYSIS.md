# Original GLM NVFP4 high-thinking — completed

Verified complete, no recorded request errors, final health HTTP200. Both-Spark original NVFP4 recipe with vision enabled,128K context. Thinking enabled/high, text ceiling32768, vision16384. Tool smoke/roundtrip passed.

- Reasoning286/302 (94.7%),921.94s (15.4min), no truncations, four retries.
- Work378/438 (86.3%),7404.29s (123.4min). stream_reassembler truncated; six retries. Hard Verilog first5/30 from uncompiled code, retry0/30 from combinational feedback; preserved5.
- Vision59/78 (75.6%),30.1min sum request latency; hard_v2_logic_network truncated.

GLM EXL3 high comparison with same output ceilings: reasoning300/302 in6.9min; work415/438 in9.7min; vision74/78 in7.3min. EXL3 is the stronger measured all-round deployment in these runs. Both are4-bit routed-expert configurations; EXL3 is a format name, not3bits. Serving stack, activation precision, speculation and templates differ; do not attribute the gap solely to weight quantization or claim general superiority from one run.

For now the original NVFP4 vision model remains loaded. No consumer routing change or final default switch was executed by the test runner. Provisional recommendation remains updated GLM EXL3; preserve this NVFP4 recipe as fallback.
