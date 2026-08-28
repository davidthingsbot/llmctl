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

| | Devstral-Small-2-24B FP8 | Mistral-Small-4-119B IQ2_M | Qwen3.6-27B FP8 (`27b-fp8`) |
|---|---:|---:|---:|
| Work quality | 73/100 | 70/100 | **83/100** |
| Deep reasoning | 51/100 | 53/100 | **70/100** |
| Blind open-response (mean /20) | 10.60 | 7.63 | **17.27** |
| Work suite wall time | 44.4 s | 37.9 s | 57.0 s |
| Reasoning suite wall time | 34.0 s | 16.2 s | 41.6 s |

| Work task | Dev | S4 | 27b | | Reasoning task | Dev | S4 | 27b |
|---|---:|---:|---:|---|---|---:|---:|---:|
| Strict protocol JSON | 12/12 | 12/12 | 12/12 | | Logic grid | 3/12 | 3/12 | 0/12 |
| BOM consolidation | 6/10 | 1/10 | 10/10 | | Causal inference | 3/14 | 3/14 | 6/14 |
| Executable code repair | 17/20 | 17/20 | 20/20 | | Bayesian updating | 4/12 | 4/12 | 8/12 |
| Embedded C review | 10/12 | 6/12 | 8/12 | | Hypothesis discrim. | 8/12 | 7/12 | 12/12 |
| Protocol architecture | 6/18 | **18/18** | 10/18 | | Adversarial epist. | 12/14 | 12/14 | 14/14 |
| 35K retrieval | 16/16 | 10/16 | 16/16 | | Value of information | 5/12 | 4/12 | 9/12 |
| Scope control | 6/6 | 6/6 | 6/6 | | Wason selection | 4/10 | 8/10 | 9/10 |
| Acquisition timing | 0/6 | 0/6 | 1/6 | | Complex policy | 12/14 | 12/14 | 12/14 |

Two entries deserve attention. **Small 4 scored a perfect 18/18 on protocol
architecture** — the open design task no model had ever beaten, previous best
anywhere 12/18 — while scoring only **10/16 on long-context retrieval** where
both others were perfect, at just ~35K depth. A model whose whole argument is
cheap long context, missing facts well inside its window, is a hard sell; the
2-bit quant is the leading suspect.

**`logic_grid` does not discriminate and arguably misleads.** It has one unique
solution (verified by brute force) and is graded by exact row match, so partial
luck scores. 27b-fp8's 0/12 answer was a well-formed permutation — four distinct
days, four distinct topics — that simply picked the wrong one, while both
challengers scored 3/12 by getting the single row that follows directly from one
clue, and Small 4 did so while placing two researchers on the same day and
giving Dion a topic that clue 1 assigns outright. Since the suite disables
thinking and demands JSON only, there is no scratchpad for the sequential search
the puzzle needs.

**Both challengers were rejected.** Small 4's own result is covered in the
survey doc: it confirmed the *hardware* claim (a 119B model does hold 4x128K on
two 3090s) while losing on quality, and its measured KV came in 35% above
prediction.

**Devstral was rejected as a replacement.** It is 21-42% faster at every
concurrency level with far better TTFT, but it won one work task out of eight and
one reasoning task out of eight. The result that decided it is executable code
repair, 17/20 against 20/20 — the executed-against-hidden-harness task a
coding-specialised model should own. Full analysis and the throughput tables are
in `docs/mistral-lineup-survey-2026-08.md`.

Note the logic grid: 27b-fp8 scores 0/12 here as it did on DW-X1Pro, so that task
still fails to separate anything at the top and Devstral's 3/12 is not a win worth
counting.

### Blind review of open responses — DW-ASUS-LINUX

Three independent judges scored the two open tasks (`adversarial_epistemology`,
`complex_policy_reasoning`) under blind labels, as on DW-X1Pro. Supplementary;
does not modify the deterministic totals.

| Model | Judge totals (/20) | Mean | Rank |
|---|---|---:|---:|
| Qwen3.6-27B FP8 | 17.5, 17.6, 16.7 | **17.27** | **1** |
| Devstral-Small-2-24B FP8 | 10.7, 11.3, 9.8 | **10.60** | 2 |
| Mistral-Small-4-119B IQ2_M | 8.4, 7.8, 6.7 | **7.63** | 3 |

Unanimous 3-0-0. (This three-way run supersedes an earlier two-way review of
Devstral vs 27b-fp8; the ranking between those two was the same.) **This is the most important qualification on the table above: the
deterministic rubric OVERSTATES both challengers, and overstates Small 4 most.**
Both scored 12/14 and 12/14 on these two tasks — for each, its best showing on
the whole reasoning suite — yet blind review puts Small 4 LAST at 7.63 against
17.27. The rubric rewards mentioning the right concepts; the judges penalised
getting them backwards. Twice now, on two different models. Treat rubric scores
on open-ended tasks as directional only, exactly as the Caveats section says.

Judges converged on the same concrete fault in **Small 4**: it asserts the ledger
is "consistent with the claim of diversion" while concluding the opposite, an
internal contradiction no keyword rubric can see; it also confuses two of the
sources, truncates mid-conclusion, and answers the policy task by restating the
prompt's own bullets while 20% over the word limit.

For **Devstral**, judges converged on: it misclassifies a
contemporaneous diary as a *secondary* source, never states which direction
belief should move, requests next-evidence that is near-circular, inverts the
calibration point (claiming calibration equalises error rates across groups),
invents unmoored numerical thresholds, and truncates mid-sentence while over the
word limit, never reaching distribution shift, strategic adaptation or stopping
conditions. Its one acknowledged edge was proposing a randomised trial.

**Method note, recorded because the first attempt was flawed:** an initial pass
was discarded because the extracted prompt files were 0 bytes — the results JSON
does not retain prompts — so judges were reconstructing the task from the answers.
Prompts were pulled from `deep_reasoning_suite.py` and all three judges re-ran.
Both passes gave the same unanimous ranking with near-identical scores, but only
the second is recorded. If the results JSON retained prompts this would be a
one-step process; worth fixing.

### `--no-template-kwargs`

Both suites send `chat_template_kwargs: {enable_thinking: false}` by default.
vLLM rejects that outright for **Mistral-tokenizer models** with HTTP 400
(`chat_template is not supported for Mistral tokenizers`), so those runs need
`--no-template-kwargs`. It is left ON by default because omitting it is a no-op
for Mistral (no thinking mode to disable) but is **not** a no-op for the Qwen
models — flipping the default would silently break comparability with every
result recorded above.

## dw-bee-linux results — 2026-08-28

The first run on the Ryzen 7 255 / Radeon 780M mini box. **Not comparable to
either table above** — different hardware, different quantisations, and the only
machine here where the model shares one DDR5 bus with the CPU through a 17.59 GiB
Vulkan heap. The two models are comparable to each other: same machine, same
harness, thinking disabled on both, llama.cpp Vulkan in both cases.

| | Qwen3.5-35B-A3B IQ4_NL (`qwen35b`) | Qwen3.5-9B Q4_K_M (`qwen9b`) |
|---|---:|---:|
| Work quality | **85/100** | 77/100 |
| Deep reasoning | **71/100** | 57/100 |
| Work suite wall time | 545.10 s | **389.35 s** |
| Reasoning suite wall time | 240.48 s | **172.31 s** |

| Work task | 35B | 9B | | Reasoning task | 35B | 9B |
|---|---:|---:|---|---|---:|---:|
| Strict protocol JSON | 12/12 | 12/12 | | Logic grid | 0/12 | 3/12 |
| BOM consolidation | 9/10 | **2/10** | | Causal inference | 6/14 | 4/14 |
| Executable code repair | 20/20 | 17/20 | | Bayesian updating | 8/12 | 4/12 |
| Embedded C review | 8/12 | **10/12** | | Hypothesis discrim. | 12/12 | 9/12 |
| Protocol architecture | 14/18 | 14/18 | | Adversarial epist. | 14/14 | 12/14 |
| 35K retrieval | 16/16 | 16/16 | | Value of information | 8/12 | 4/12 |
| Scope control | 6/6 | 6/6 | | Wason selection | 9/10 | 9/10 |
| Acquisition timing | 0/6 | 0/6 | | Complex policy | 14/14 | 12/14 |

### Interpretation

- **35B-A3B is the better model on both suites and should stay the default**, as
  it already is. It wins work quality by 8 and deep reasoning by 14, at roughly
  1.4x the wall time — a far better trade than the 4.29x and 7.40x penalties the
  dense 27B carried on DW-X1Pro.
- **`qwen9b`'s 2/10 on BOM consolidation is the lowest score that task has ever
  recorded, and it is not an arithmetic failure.** The task offers a cheaper 25 V
  capacitor for a rail with a verified 36 V transient. The 9B computed both
  numbers correctly — $16.00 annual saving and $40 setup, the two points it
  earned — then selected the 25 V part and returned `voltage_valid: true` and
  `add_new_sku: true`. It got the economics right and the derating wrong. Mistral
  Small 4 scored 1/10 here but missed the arithmetic too; this is a cleaner and
  more worrying failure, because the model looks confident and numerate while
  choosing a part that fails in service. Do not let a 9B make component
  selections unreviewed.
- **`qwen35b` scored 14/18 on protocol architecture**, the second-highest result
  ever recorded on that task and the best by any Qwen — DW-X1Pro's ceiling was
  12/18 and `27b-fp8` managed 10/18. It also took 14/14 on complex policy
  reasoning, which previously only Coder-Next had reached. The open-task rubric
  is directional only (see Caveats), so this warrants a blind review before it is
  treated as a real capability gain.
- **The 9B beat the 35B on embedded C review, 10/12 against 8/12.** Small enough
  to be noise on a single deterministic run, but it is the one work task where
  the smaller model led.
- **The 35K retrieval task still separates nothing.** Both models scored 16/16,
  as every Qwen has on every machine — now including a 9B dense model at Q4_K_M.
  The task needs to get longer or be retired.
- **Acquisition timing remains unbeaten at 0/6 for both.** Across every machine
  and every model in this repo, no result has exceeded 1/6. The recommendation
  stands: compute link budgets with a tool, then ask the model to interpret
  checked numbers.
- **No blind open-response review was run for this machine.** The DW-X1Pro and
  DW-ASUS-LINUX sections both show the deterministic rubric overstating models on
  the two open tasks, twice. The 35B's 14/14 and 14/14 on adversarial
  epistemology and complex policy should be read with that history in mind.

### Long-context prerequisite — `qwen9b` served context raised 16K -> 64K

`long_context_retrieval` is a 37,271-token prompt. `qwen9b` was configured
`SERVER_CTX=16384`, so those 16 points were structurally unreachable and the
suite could not be run comparably at all. Its GGUF reports
`n_ctx_train = 262144`, so 16K was a conservative config choice rather than a
model limit; it was raised to 65536 for this run and kept there.

The cost is real and specific to this box. The 780M's 17.59 GiB Vulkan heap is
4.00 GiB of carved-out VRAM plus 13.59 GiB of GTT, and GTT is drawn from the
27.18 GiB `MemTotal` — so the roughly 2.2 GiB of extra KV comes mostly out of
system RAM, not out of a separate pool. Start-bench generation fell from
13.2 tok/s at 16K to 10.3-12.5 tok/s at 64K. The 16/16 retrieval result was
worth it, but note that unlike a discrete-GPU box, raising context here competes
directly with CPU memory.

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
