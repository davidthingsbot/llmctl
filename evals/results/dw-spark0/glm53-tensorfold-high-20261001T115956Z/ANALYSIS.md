# TensorFold trial: interim analysis

Run: `glm53-tensorfold-high-20261001T115956Z`.
Previous baseline: `glm53-exl3-thinking-high-20260917T154206Z`.
Both use high effort, temperature zero, 32768 text token floor, one retry with
0.7 credit; retained vision uses 16384 tokens and no retry. Different serving
runtime, additional dense q4 quantization and kernel arithmetic mean these are
whole-recipe comparisons, not an isolated engine experiment.

## Completed quality results

- Reasoning: 298/302 vs 300/302. Only credited task change:
  hypothesis_discrimination 12 -> 10.
- Work: 417/438 vs 415/438. Only credited task change:
  protocol_architecture 14 -> 16.
- Vision: 70/78 vs 74/78. Changes: hard_v2_crossing_plot 5 -> 4;
  hard_v2_logic_network 5 -> 0; hard_v2_resources 3 -> 4;
  hard_v2_cross_reference 4 -> 5. Aggregate hides a substantial logic-network
  regression and two improvements; inspect individual raw answers.
- No text truncations in either new text suite. Reasoning retries: two vs one;
  work retries: four vs four.
- Text/tool/round-trip/tool_choice none smoke passed; model healthy after tests.

## Observed task completion time

- Reasoning suite wall: 174.43s vs 416.93s (approximately 2.39x shorter).
- Work suite wall: 436.61s vs 580.37s (approximately 1.33x shorter).

Wall times include harness/checking overhead. These are single retained suite
runs, not matched repeated timing trials; historical deployment conditions and
output lengths differ. New reasoning completion tokens 10309 vs 11441;
new work completion tokens 22238 vs 20004. Faster generation is not alone proof
of faster time to a correct answer or uniformly better task quality.

## Throughput receipts (different protocols, not interchangeable)

Publisher repository `tools/bench.py`, single request, median of five 256-token
ceiling runs after prefill/warmup, defaults thinking enabled (max effort), prose
sampling defaults temperature 1/top-p .95, code temperature zero:

- Code greedy decode: 60.4 tok/s.
- Chat sampled decode: 65.8 tok/s.
- Server-reported decode-only tokens/time; excludes prefill and TTFT.
- Fresh random-prose prefill at 50302 tokens: 1910 tok/s, TTFT 26.47s.
- Other prefill receipts: 812 tokens 1160 tok/s; 3166 tokens 1701 tok/s;
  12598 tokens 1816 tok/s.

This script is NOT the sparkDash protocol underlying the announcement's 60.4
single-stream and 108.8 four-stream prose claim. Do not claim exact reproduction.
No GPU clock cap was changed to the publisher's 2200 MHz setting.

Local concurrency harness: the fixed 150-word accelerator explanation, temperature
0.7, 1/2/4 stream levels in increasing order; server-reported usage divided by
wall time including TTFT. Cache/warm state not controlled as a fresh-prefix trial:

- High effort, 1024-token ceiling: aggregate 44.8 / 77.0 / 143.7 tok/s;
  actual total output 236 / 472 / 944 tokens.
- Explicit thinking off, 400-token ceiling: aggregate 42.4 / 60.0 / 106.6 tok/s;
  actual total output 203 / 406 / 812 tokens.
- No failed requests. Per-stream rates and TTFT in the JSON receipts.

Neither these short concurrency tests nor repo benchmarks prove long-context
concurrency stability. Do not headline 42.4 as the universal speed or conflate
143.7 aggregate with single-stream speed.

## Context and interrupted runner

Actual allocated per-request context 1048576; shared pool 2207744 tokens,
not the publisher's 2684928 pool (local reserves are more conservative).
Configured capacity is not tested usable capacity.

- 31939 actual API prompt tokens: exact key returned; 16.52s end-to-end.
- 99723 actual API prompt tokens: correct key with extra `Archive key:` prefix;
  52.00s end-to-end. STRICT FORMAT FAILURE, retrieval successful. The original
  `long-100000.json` keeps `correct=false`; no answer/result was rewritten.
- Original runner stopped on strict mismatch. `continue_tensorfold_context.py`
  continues only the unstarted approximately 200K/500K/900K checks, recording
  exact-only correctness separately from recovery of the unique expected key.
  Extension completed successfully: 199363 actual API prompt tokens, 111.69s;
  498537 tokens, 349.54s; 897103 tokens, 795.08s. All three returned the exact key
  without extra text. These are single-needle retrieval tests with 512-token
  output ceiling, temperature zero and thinking disabled, not proof of deep
  comprehension or simultaneous full-length conversations.
- Initial vision runner failed BEFORE any image request because runpy omitted
  the script directory from sys.path. Exact-child regression failed then passed
  after repair. Model was not restarted. Failed log/status retained.

No default/consumer routing change, rollback or persistent service enablement.
All planned battery stages have now run. Final status is
`complete_with_format_failure`, preserving the strict 100K formatting failure.
Fresh final health was OK, zero running requests; both guards remained active.
Observed idle MemAvailable after the 897K test: approximately 10 GiB on head,
12 GiB on worker (not a measured peak minimum).

## Recommendation and boundaries

Candidate is suitable for engineering/analysis trial use: nearly unchanged text
scores, materially shorter observed text-suite completion times, working tools,
and verified single-request retrieval up to 897103 prompt tokens. It is not an
unqualified improvement: retained vision dropped 74 -> 70, including a five-point
logic-network regression; one strict formatting violation persists. Keep prior
recipe intact and obtain authorization before any default/routing change.
No claim of exact announcement benchmark reproduction, four simultaneous 1M
requests, long-context reasoning quality or persistent reboot operation is made.
