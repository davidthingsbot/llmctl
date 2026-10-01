# GLM-5.3 Flash EXL3 TensorFold: authorized trial, 2026-10-01

Source: https://x.com/miaai_lab/status/2105598458547646875?s=46
Recipe: https://github.com/MiaAI-Lab/GLM-5.3-Flash-EXL3-2x-DGX-Sparks-TensorFold
Checked out at `ed026ef92d1650120dada1294a112acb6c8f2f48` in
`/home/david/work/glm53-tensorfold`.

David authorized suitability checking, necessary downloads, loading and the usual
local evaluation battery. This authorizes an isolated test, not a persistent
default switch or repointing Hermes/browser consumers.

## Assessment

Suitable for evaluation of agentic engineering, reasoning, tools and vision on
our dual-GB10 Sparks. The verified direct CX7 link is 10.100.100.10 -> 10.100.100.11,
RoCE device rocep1s0f1, GID 5. Initial available memory was 116/117 GiB and disk
1.3/1.6 TiB. No GPU processes were running. Persistent prior EXL3 recipe is retained.

This is the same base GLM model but a new TensorFold runtime, 52 patches, and
additional lossy dense q4 quantization plus FP8 KV. Publisher's 60.4 tok/s prose,
108.8 aggregate at four streams, 1M per-request window and 2.7M shared pool are
NOT local measurements or verified simultaneous capacity. Parallel decode
exactness against its own serial path does not imply equivalence with the previous
runtime. DFlash2 licence: CC BY-NC-ND 4.0, non-commercial restriction.

## Artifacts and settings

Pinned target: `Mia-AiLab/GLM-5.3-Flash-EXL3-TR3-4bpw` at
`9eaebb7c4e96d983dcd538e18624622ba5b820a8`, approximately 176 GB.
Pinned draft: `incoai/GLM-5.3-Flash-DFlash2` at
`bf582e4eacc1810f76656d1811693ff6c6737d2a`, approximately 2.3 GB.
Prebuilt image tag: `v0.5.0-cefe8bf45d07` (~25 GB); preparation verifies matching
image IDs on both nodes and copies/size-checks checkpoint files.

Local overrides: loopback API `127.0.0.1:18888`, distinct container
`glm53-flash-tf-trial`, four streams, vision enabled, 1048576 requested context,
18 GiB host reserve and 8 GiB extra KV pool (more conservative than publisher).
Actual accepted context/pool must be read back after loading, not assumed.
No GPU clocks have been changed to reproduce publisher's 2200 MHz limit.

The stock memory guard only targets `vllm_node`; it does NOT protect this trial.
An explicit tested guard `glm53-tf-trial-memguard.service` runs on each node,
checks fresh local MemAvailable every two seconds, and kills ONLY the named trial
container below 5 GiB or if the memory sample cannot be obtained. Guards are
transient user services with verified lingering; not new reboot defaults.

## Execution and acceptance matrix

Runner: `evals/diagnostics/run_tensorfold_trial.py`.
Guard: `evals/diagnostics/tensorfold_trial_memguard.py`.
Preparation log: `/home/david/.cache/glm53-tensorfold-prepare.log`.
Runner log: `/home/david/.cache/glm53-tensorfold-trial.log`.
Results: timestamped `evals/results/dw-spark0/glm53-tensorfold-high-*/`.

Ordered stages, with preparation/guard/readiness gates:

1. Successful pinned preparation receipt and both guards active.
2. Actual real-weight startup; health, model identity, reasoning separation.
3. Text, automatic tool call, synthetic tool-result round trip, tool_choice none.
4. Extended deep reasoning and work quality: high effort, temperature zero,
   32768 token floor, one retry at 0.7 credit.
5. All 25 retained vision tasks / 78 fields, high effort, 16384 tokens, no retry.
6. Bounded concurrency 1/2/4, high effort 1024 tokens; separate thinking-off
   400-token baseline. These are throughput tests, not completed-answer quality.
7. Publisher repository's own bench script, separately labelled; this is NOT
   identical to the sparkDash headline measurement protocol. Preserve its exact
   defaults and report them rather than silently equating headline rates.
8. Safety-gated retrieval at approximately 32K/100K/200K/500K/900K prompt tokens;
   save actual token counts, time, raw answers and correctness. Not a simultaneous
   multi-stream full-context stability test.

Baseline verified from retained files:
`glm53-exl3-thinking-high-20260917T154206Z`: reasoning 300/302, work 415/438,
vision 74/78. Same high template, text/vision budgets and retry policy targeted.
Differences in current harness/runtime must still be called out in interpretation.

Runner self-test exercises CLI contracts, fixture identity/count, guard threshold
logic, and rejection of incomplete/error results. It is NOT a full serving test.
NumPy and Pillow are provided via uv's isolated environment; missing NumPy must
not silently corrupt scoring. Existing generated-code containment remains intact.
Any blocked stage retains raw/partial records and exits nonzero. No automatic
rollback on orchestration or syntax errors. A queued test is not a completed test.

## Initial state

Both-node preflight passed and prebuilt image downloads started. Real-weight
startup and evaluation scores remain pending. This document is a plan and receipt
of actions begun, not an evaluation result.

## Final outcome and publication

All planned stages subsequently executed. See
[the final analysis](results/dw-spark0/glm53-tensorfold-high-20261001T115956Z/ANALYSIS.md)
for the complete quality, timing, context and caveat record. Reasoning 298/302,
work 417/438, vision 70/78; exact single-needle retrieval passed up to 897103 actual
API prompt tokens. Status `complete_with_format_failure` preserves the 100K
correct-key/extra-prefix format failure rather than rewriting it.

Preparation reused all cached target weight blobs; the new pinned snapshot did
not require another 176 GB weight download. New runtime images were installed
on both nodes. Exact local settings and preparation/orchestration logs are stored
beside the raw results. Model stayed loaded across runner repairs; no production
default, consumer routing or reboot policy was changed.

Pre-publication checks: 105 existing evaluation unit tests passed; 12 runner
regression tests passed; root Python suite ran 29 tests with three skips and no
failures; all root shell tests passed. Existing evaluation code emitted unclosed
file ResourceWarnings. These are unit/fixture tests, not fresh inference scores.

Independent precommit review also found defects in the original diagnostic
helpers: stopping monitoring after an unsuccessful container kill, and overwriting
previous receipts on resume/continuation. The checked-in helpers were hardened
with verified-stop retries, lock-before-write, unique predecessor snapshots and
strict continuation eligibility checks. All new regressions and runner self-test
pass. `harness-as-run/` preserves the pre-hardening sources used for this trial.
Historical raw results remain untouched; tests of the hardening use mocks and do
not constitute a new model evaluation. The running guard processes have not been
replaced by this publication step; deploy the hardened guard when promoting the
trial to persistent service.

