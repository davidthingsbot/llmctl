# Work-quality local-model evaluation

`work_quality_suite.py` is a small, reproducible domain suite for the engineering and agent work done on this machine. It deliberately favors practical tasks over generic academic trivia.

## Tasks and weighting

| Task | Points | What it tests |
|---|---:|---|
| Strict protocol JSON | 12 | Exact schema following and known acquisition-policy retention |
| BOM consolidation | 10 | Electrical validity, SKU consolidation and basic economics |
| Executable frame-decoder repair | 20 | Endianness, exact length, CRC scope and runnable code correctness |
| Embedded C review | 12 | Bounds, integrity, authentication ordering and unsafe binary handling |
| Protocol architecture | 18 | Separation of acquisition/transform/read/event responsibilities and reproducibility |
| Long-context retrieval | 16 | Eight exact facts distributed through a roughly 35K-token engineering log |
| Scope control | 6 | Minimal approved change without stakeholder-driven scope expansion |
| Acquisition timing | 6 | Sensor-link bandwidth, overhead and utilization arithmetic |

Total: 100 points.

Objective tasks use exact JSON checks or executable tests. The open protocol and C-review tasks use explicit keyword/concept rubrics, followed by manual response inspection. Models run at temperature zero with thinking disabled. Raw prompts, responses, usage, timings and rubric details are retained in `results/`.

## DW-X1Pro results — 2026-08-05

| Task | 35B-A3B Q5 | 27B dense Q8 | Coder-Next IQ4_XS |
|---|---:|---:|---:|
| Strict protocol JSON | 12/12 | 12/12 | 12/12 |
| BOM consolidation | 10/10 | 10/10 | 10/10 |
| Executable code repair | 20/20 | 20/20 | 20/20 |
| Embedded C review | 12/12 | 10/12 | 10/12 |
| Protocol architecture | 12/18 | 12/18 | 10/18 |
| 35K-token retrieval | 16/16 | 16/16 | 16/16 |
| Scope control | 6/6 | 6/6 | 6/6 |
| Acquisition timing | 0/6 | 1/6 | 0/6 |
| **Total** | **88/100** | **87/100** | **84/100** |
| Suite wall time | **218.59 s** | **937.11 s** | **232.94 s** |
| Relative to 35B | 1.00x | 4.29x | 1.07x |

### Interpretation

- **35B-A3B Q5 remains the best practical default.** It had the highest score, the only perfect C-review result, low memory pressure, and nearly the same suite time as Coder-Next.
- **27B dense Q8 quality was close on this small suite, but its economics are poor.** It was one point behind 35B while taking 4.29 times as long. Its 2.9 tok/s decode rate dominates real use.
- **Coder-Next is strong for bounded coding tasks.** It passed every executable decoder test and was the fastest generator in throughput testing. Its open embedded-protocol answer was materially weaker: it retained monolithic SCAN behavior, stored transformed rather than reproducible raw/retained data, coupled event reporting to acquisition behavior, and proposed pausing continuous acquisition rather than rejecting the ownership conflict.
- **All three retrieved every fact from the long context**, so the tested 35K-token retrieval case does not distinguish them.
- **All three failed the acquisition arithmetic.** None should be trusted to calculate link budgets unaided. Production workflows should continue using an actual calculation tool and then ask the model to interpret checked numbers.
- The open protocol task also exposed a shared verbosity problem: all models consumed the 520-token ceiling and left requirements unresolved. For architecture work, request a strict decision table or structured schema, then review it against explicit invariants.

## Deep-reasoning suite — 2026-08-05

`deep_reasoning_suite.py` is a separate 100-point suite focused on non-engineering reasoning: a uniquely solved logic grid, fuzzy regression-discontinuity inference, sequential Bayesian updating, scientific hypothesis discrimination, adversarial historical evidence, value of information, Wason conditional logic, and policy reasoning under uncertainty.

| Task | 35B-A3B Q5 | 27B dense Q8 | Coder-Next IQ4_XS |
|---|---:|---:|---:|
| Logic grid | 0/12 | 0/12 | **6/12** |
| Causal inference | 6/14 | 6/14 | **11/14** |
| Bayesian updating | 8/12 | 8/12 | 8/12 |
| Hypothesis discrimination | **12/12** | **12/12** | 11/12 |
| Adversarial epistemology | 14/14 | 14/14 | 14/14 |
| Value of information | 8/12 | **9/12** | **9/12** |
| Wason selection | 9/10 | **10/10** | **10/10** |
| Complex policy reasoning | 12/14 | 12/14 | **14/14** |
| **Total** | **69/100** | **71/100** | **83/100** |
| Suite wall time | 98.38 s | 728.25 s | **96.17 s** |
| Relative to 35B | 1.00x | 7.40x | 0.98x |

### Deep-reasoning interpretation

- **Coder-Next won this suite decisively.** It was the only model to partially solve the unique logic grid, handled the fuzzy causal design much more completely, and earned full policy and Wason scores. It also completed slightly faster than 35B.
- **Dense 27B narrowly exceeded 35B but took 7.40 times as long.** The two-point advantage on one deterministic run is not enough to offset its impractical decode speed.
- **35B remained strongest on scientific mechanism discrimination**, tying dense 27B at 12/12 and exceeding Coder by one point.
- **All three computed the first positive-test posterior correctly and the second incorrectly**, despite the prompt explicitly granting conditional independence.
- **All three made material expected-value mistakes.** They generally selected the right contingent actions and policy, but produced incorrect conditional EVs and net test values.
- The result changes the role recommendation: Coder-Next is not merely a fast code model; on the deterministic suite it is the preferred local model for structured standalone reasoning when its 44.25 GiB VRAM footprint is acceptable. The blind open-response review below prevents generalizing that result to all forms of deep thought. The 35B remains the better always-on default because it uses about 12.25 GiB less VRAM and remains strong for practical engineering work.

### Independent blind review of open responses

Three independent judges scored only the raw historical-evidence and policy responses under labels A/B/C. These scores are supplementary and do not modify the 100-point deterministic totals.

| Model | Judge totals (/20) | Mean | Open-response rank |
|---|---|---:|---:|
| 27B dense Q8 | 19.0, 19.5, 16.0 | **18.17** | **1** |
| 35B-A3B Q5 | 17.2, 18.5, 17.0 | **17.57** | **2** |
| Coder-Next IQ4_XS | 15.5, 17.5, 14.0 | **15.67** | **3** |

Two judges ranked dense 27B first and one ranked 35B first; all three ranked Coder last. Coder's historical-evidence answer opened by increasing belief, then concluded that personal diversion remained weak, creating an internal directional inconsistency. Judges also penalized unsupported numerical policy thresholds and truncation. Dense 27B gave the best average open argument but remains impractically slow; 35B is therefore the practical choice for open-ended local analysis. Coder remains the strongest measured option for structured causal, conditional and constrained reasoning.

## DW-ASUS-LINUX results — 2026-08-09 (Devstral vs the incumbent)

The first paired run on the dual-3090 box. **These are not comparable to the
DW-X1Pro tables above** — different hardware, different quantisations. They are
comparable to each other: same machine, same harness, thinking disabled on both.

| | Devstral-Small-2-24B FP8 | Qwen3.6-27B FP8 (`27b-fp8`) |
|---|---:|---:|
| Work quality | **73/100** | **83/100** |
| Deep reasoning | **51/100** | **70/100** |
| Work suite wall time | 44.4 s | 57.0 s |
| Reasoning suite wall time | 34.0 s | 41.6 s |

| Work task | Devstral | 27b-fp8 | | Reasoning task | Devstral | 27b-fp8 |
|---|---:|---:|---|---|---:|---:|
| Strict protocol JSON | 12/12 | 12/12 | | Logic grid | 3/12 | 0/12 |
| BOM consolidation | 6/10 | 10/10 | | Causal inference | 3/14 | 6/14 |
| Executable code repair | 17/20 | 20/20 | | Bayesian updating | 4/12 | 8/12 |
| Embedded C review | 10/12 | 8/12 | | Hypothesis discrim. | 8/12 | 12/12 |
| Protocol architecture | 6/18 | 10/18 | | Adversarial epist. | 12/14 | 14/14 |
| 35K retrieval | 16/16 | 16/16 | | Value of information | 5/12 | 9/12 |
| Scope control | 6/6 | 6/6 | | Wason selection | 4/10 | 9/10 |
| Acquisition timing | 0/6 | 1/6 | | Complex policy | 12/14 | 12/14 |

**Devstral was rejected as a replacement.** It is 21-42% faster at every
concurrency level with far better TTFT, but it won one work task out of eight and
one reasoning task out of eight. The result that decided it is executable code
repair, 17/20 against 20/20 — the executed-against-hidden-harness task a
coding-specialised model should own. Full analysis and the throughput tables are
in `docs/mistral-lineup-survey-2026-08.md`.

Note the logic grid: 27b-fp8 scores 0/12 here as it did on DW-X1Pro, so that task
still fails to separate anything at the top and Devstral's 3/12 is not a win worth
counting.

### `--no-template-kwargs`

Both suites send `chat_template_kwargs: {enable_thinking: false}` by default.
vLLM rejects that outright for **Mistral-tokenizer models** with HTTP 400
(`chat_template is not supported for Mistral tokenizers`), so those runs need
`--no-template-kwargs`. It is left ON by default because omitting it is a no-op
for Mistral (no thinking mode to disable) but is **not** a no-op for the Qwen
models — flipping the default would silently break comparability with every
result recorded above.

## Caveats

- This is one deterministic run per model, not a statistical quality estimate.
- **Do not benchmark throughput with `llmctl bench` for terse models.** It
  reported 24-33 tok/s for Devstral, which stops after ~11 tokens on the bench
  prompt so fixed overhead dominates; forced-length generation measured 57.9.
- **Models served with `--reasoning-parser` stream into `reasoning_content`, not
  `content`.** A throughput script counting only `content` records zero tokens
  for `27b-fp8` and reports, wrongly, that nothing was generated.
- The suite is intentionally tailored to current work and is not comparable to MMLU, HumanEval or public leaderboard scores.
- Exact and executable grading is reliable; keyword-rubric task totals are directional. The raw responses must remain available for manual review.
- The 35B code response was regraded after fixing an evaluator sandbox defect: the sandbox initially omitted `bytes` and did not expose the provided `crc16` function in candidate globals. The saved candidate itself was correct, and final-grader consistency was verified across all three result files.

## Run

With the desired model already active:

```bash
python3 evals/work_quality_suite.py \
  --url http://127.0.0.1:PORT/v1/chat/completions \
  --model SERVED_MODEL_ID \
  --key-file ~/.config/llama.cpp/api-keys \
  --output evals/results/MACHINE/MODEL.json

python3 evals/deep_reasoning_suite.py \
  --url http://127.0.0.1:PORT/v1/chat/completions \
  --model SERVED_MODEL_ID \
  --key-file ~/.config/llama.cpp/api-keys \
  --output evals/results/MACHINE/deep-reasoning-MODEL.json
```

The key is read for authentication and is never written to the result file.
