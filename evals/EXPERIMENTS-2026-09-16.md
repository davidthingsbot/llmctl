# GLM text and vision experiments — 2026-09-16

This report indexes the measured results, corrections and deferred decisions. No new model responses were generated for the same-grader text regrade. No model routing change is implied by this commit.

## Current conclusions

- Updated GLM-5.3 EXL3 is a provisional default candidate after remaining tests, with the original NVFP4 setup retained as fallback. See [decision](results/dw-spark0/same-grader-regrade-20260916/DECISION.md).
- The original GLM NVFP4 also works with vision in a conservative configuration: TP2, 131072 context, two sequences, one image per request, video disabled, GPU utilization 0.80, skipped peak multimodal profiling, processor cache disabled. The original text-only launch script was not overwritten. Trial entry on the test machine: `glm53-flash-vision`, port 8006.
- Headless operation plus these configurations survived the completed tests. This is not a proof of indefinite stability or full configured-context capacity.

## Corrected text-quality results

Same hardened graders, NumPy 2.4.6, saved first answers and retries, existing 0.7 retry-credit rule:

| Model | Work quality | Deep reasoning |
|---|---:|---:|
| Original GLM NVFP4 | 403/438 (92.0%) | 279/302 (92.4%) |
| Updated GLM EXL3 | 409/438 (93.4%) | 282/302 (93.4%) |

The initially reported EXL3 work score of 347/438 was misleading: the eval Python lacked NumPy. Regrading its three ML answers restored 62 points. The old NVFP4 hard FIFO had timed out but earned 12 partial points; under the hardened failure policy it receives zero. The six-point corrected work difference is too small to establish model superiority. Historical retries received different original checker feedback, so regrading does not create a fully controlled new experiment.

[Detailed failure analysis and regrade data](results/dw-spark0/same-grader-regrade-20260916/ANALYSIS.md).

EXL3's separate ~32K and ~100K retrieval tests passed in 23.5 and 71.8 seconds. Five-second memory sampling during that run recorded minima of 9.19/8.64 GiB available on head/worker; these are sampled, not guaranteed instantaneous minima. [Run directory](results/dw-spark0/glm53-fair-headless-low-20260916T194745Z/).

## Harness failure and hardening

Generated asynchronous FIFO RTL contained circular combinational full/empty logic. Icarus vvp grew uncontrollably before simulation startup; the evaluation scope's 4 GiB memory cap and memory.oom.group killed the controller too. GLM remained alive. A simulation-time watchdog and single-threading do not contain this failure.

Verilog tools now have independent 512 MiB address-space limits, CPU/wall limits and 1 MiB combined captured-output limits. Verilator runs before simulation; explicit circular-logic diagnostics skip simulation. Nonzero/unfinished simulations cannot claim successful execution. Both text suites checkpoint atomically and preserve received answers before grading. These controls are resource containment, NOT a security sandbox for arbitrary generated code; other code graders are not all covered by the new Verilog bounds.

[Preserved failing RTL, testbench, diagnostic corrected copy and reproduction log](diagnostics/verilog-hard-runaway/README.md). The corrected copy is diagnostic only and was never substituted into model scores.

## Vision fixtures and measured comparison

All tasks are retained, regardless of discrimination. There are **25 unique tasks: 3 easy, 3 medium, 19 provisionally hard**. The original suite has nine; the two new hard batches add six and ten. Thirty in the extra-ten batch refers to graded fields, not task count. Expansion to thirty hard tasks was not approved or performed.

- [Original nine tasks](VISION.md): NVFP4 passed 9/9 tasks, 20/20 fields.
- [Six new hard tasks](VISION-HARD.md).
- [Ten additional hard tasks](VISION-EXTRA10.md).
- [Retention policy](VISION-RETENTION.md).

### New sixteen-task comparison

| Run | Correct fields | Perfect tasks | Output budget |
|---|---:|---:|---|
| GLM NVFP4 first pass | 39/58 | 9/16 | 1024 max output tokens |
| GPT-6 Astra blind pass | 58/58 | 16/16 | CLI default; not matched to GLM |
| GLM diagnostic substitution | 46/58 | 10/16 | Two truncated tasks rerun at 4096 |

The substitution is NOT a new uniform-budget benchmark. The cube task changed from no final answer (length limit) to 5/5 with a larger budget. Circuit tracing changed from truncation to 2/5: it produced a complete answer but misidentified gate input connections.

Candidate discriminators with completed imperfect GLM answers and perfect Astra answers:

| Task | GLM fields | Astra fields |
|---|---:|---:|
| Rotated mechanical dimensions | 0/3 | 3/3 |
| Scaled plate geometry and holes | 1/3 | 3/3 |
| Closed-road route planning | 0/2 | 2/2 |
| Clock-edge waveform binding | 2/3 | 3/3 |
| Document/amendment reconciliation | 3/4 | 4/4 |
| Logic-network tracing (4096 diagnostic) | 2/5 | 5/5 |

These are one-pass candidates, not established repeatable discriminators. No final six-only selection was made; all nineteen hard tasks stay available. Frontier here means ONE tested model, GPT-6 Astra, not frontier models generally.

### Comparison controls and limitations

Same original PNGs and questions, fresh independent contexts, expected answers held in the grader. Frontier processes ran in empty temporary working directories with only their image; instructions prohibited tools, source access and network research. Recorded events report no tool use. GLM temperature=0; Astra used CLI default temperature. Both requested low reasoning effort, but that label and image preprocessing are not guaranteed equivalent across providers. The frontier CLI had no matching hard output-token cap. Therefore these results are exploratory visual-task calibration, not compute-matched rankings. No independent second frontier model or repeatability/holdout validation has yet run.

PNG contact sheets were visually reviewed; generator tests check arithmetic, unique routes, circuit connectivity, spatial transforms, fixture counts and rendering bounds. Tests and source inspection do not prove every synthetic diagram is unambiguous to all readers. Individual images, not thumbnail sheets, were submitted.

### Raw vision artifacts

Under [results/dw-spark0](results/dw-spark0/):
- `vision-v1-glm53-nvfp4.json`
- `vision-extra10-glm53-nvfp4-r1.json`, `vision-hard6-glm53-nvfp4-r1.json`
- `vision-extra10-frontier-r1.json`, `vision-hard6-frontier-r1.json`, plus per-task JSONL/stderr directories
- `vision-hard6-glm53-nvfp4-budget4096.json`

Some generic-runner result files retain `suite: synthetic-vision-v1`; use their task IDs and matching fixture manifests to identify the actual batch. This metadata limitation is disclosed rather than silently rewriting historical raw results.

## Invalid or superseded historical data

- `full-glm53-exl3.json`, `full-deep-reasoning-glm53-exl3.json`, `full-concurrency-glm53-exl3.json`: interrupted 500K run / connection failures. Not valid aggregate quality scores.
- `full-*-glm53-exl3-250k.json`: older EXL3 settings, thinking disabled; not directly comparable with the newer low-effort run.
- `glm53-fair-headless-low-20260916T174603Z/`: memory samples from the interrupted simulator run; no completed suite.
- `glm53-fair-headless-low-20260916T194745Z/`: completed runtime/stability run, but original work total is superseded by the NumPy-equipped saved-answer regrade.
- Cold concurrency sweep includes JIT latency; use the separately recorded warm sweep when discussing steady-state behavior.

Do not turn a process exit code of zero into a passing eval claim: inspect task errors, truncation, completion status and missing dependencies.

## Reproduction

Use an isolated dependency-complete interpreter:

```sh
uv run --no-project --with numpy --with pillow python -m unittest discover -s evals -p 'test_*.py'
```

See VISION.md, VISION-HARD.md and VISION-EXTRA10.md for image generation and API runs. Manifests and diagnostic runners contain test-host absolute paths; regenerate manifests for another checkout and adapt diagnostic paths. Credentials are read at runtime from key files, not stored in results. Generated simulation binaries and caches are not part of this record. The experimental EXL3 adapter remains local pending its extra-argument compatibility fix.
