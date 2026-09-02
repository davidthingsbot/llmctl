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

## dw-bee-linux — llama.cpp rebuild, 2026-08-29

The March build (`451ef08`) was replaced with **b10276 / commit
`6ea215d171fd31df943bf1ac8227129f2b963160`** — the same commit dw-x1pro-linux
validated — built Release + Vulkan + `GGML_NATIVE` + OpenMP at
`/home/david/work/llama.cpp/build-vk`. **16617/16617 Vulkan backend tests
passed**, matching x1pro's figure exactly.

**A claim in the earlier survey was wrong and is corrected here.** The March
build was said to be unable to load Qwen3.6 or GLM-4.7. It was not: b10276 has
no `qwen36` architecture either. Qwen GGUFs reuse architecture ids — the local
Qwen3.5-35B-A3B file declares `general.architecture = qwen35moe` — and
`glm4moe` was already present in March. Architecture strings are a poor proxy
for model support. What the rebuild genuinely adds is `deepseek4`,
`deepseek32`, `gemma4`, `mistral4`, `minimax-m3`, `granite-4.0/4.1`,
`hunyuan-vl`, `glm-dsa` and `step35`. The DeepSeek-V4 gate was real; the
Qwen3.6 gate was not.

**Build trap.** `find_package(SPIRV-Headers CONFIG REQUIRED)` succeeds but never
propagates its include directory, so `ggml-vulkan.cpp` fails with 36
`'spv' has not been declared` errors on any machine without distro SPIR-V
headers in `/usr/include`. With no passwordless sudo here, SPIRV-Headers
`vulkan-sdk-1.4.309.0` is vendored at `/home/david/work/.local-deps` and the
build needs `CPLUS_INCLUDE_PATH` pointing at it.

### `-ngl` must be tuned at production context, not benchmark context

Same model, same settings, old build vs new at `-ngl 30`:

| | old `451ef08` | new `b10276` |
|---|---:|---:|
| pp2048 | 197.63 | 171.27 |
| tg128 | 8.87 | **13.11** |

That prefill loss is not a regression, it is a stale tuning. Sweeping `-ngl` on
the new build rises monotonically on **both** axes:

| `-ngl` | 0 | 20 | 30 | 36 | 38 |
|---|---:|---:|---:|---:|---:|
| pp2048 | 66.14 | 132.80 | 170.87 | 214.25 | **230.08** |
| tg128 | 8.57 | 11.14 | 13.09 | 17.93 | **18.99** |

At `-ngl 38` the new build beats the old on prefill *and* more than doubles
generation. **`-ngl 30` is nonetheless still shipped**, because that sweep ran
at pp2048 where KV is negligible. At the production 131072 context KV costs
2.5 GiB, so 38 of 40 layers plus KV plus compute needs ~18.3 GiB against a
17.59 GiB heap and will not fit. The re-tune has to be done at real context.

## dw-bee-linux — gpt-oss-20b evaluated and rejected as default, 2026-08-29

Selected as the size-down candidate on a single criterion: it is the only model
in its class that fits the 17.59 GiB Vulkan heap **whole**. Its MoE weights are
natively MXFP4 and barely re-quantize, so every quant from Q2_K to Q8_0 lands
between 10.68 and 11.27 GiB — Q8_0 is taken because there is no reason to take
less. Only 12 of its 24 layers carry real KV (24 KiB/token), so 131072 context
costs 3.00 GiB at f16. Measured resident: **14.18 GiB, nothing spilled**.

| | qwen35b (35B-A3B IQ4_NL) | gpt-oss-20b (Q8_0) |
|---|---:|---:|
| Prefill | 179.0 t/s | **341-345 t/s** |
| Generation | 10.5 t/s | **25.4-28.2 t/s** |
| Weights | 16.59 GiB, partial offload | **11.27 GiB, full offload** |

### The recorded scores are artifacts — see `*-TRUNCATED.json`

gpt-oss **always** emits a harmony analysis channel. There is no off switch:
`--reasoning off` is a no-op (it governs extraction, not generation) and
`reasoning_effort: "none"` behaves as `"low"`. Server-side
`--chat-template-kwargs '{"reasoning_effort":"low"}'` halves the overhead and is
not overridden by a request-level `enable_thinking`, so the suites ran
unmodified — but their per-task `max_tokens` are sized for thinking-disabled
models. Reasoning consumed the budget and the answer was never written.

| Task | Budget | Recorded | At budget 1500 | Tokens used |
|---|---:|---:|---:|---:|
| `long_context_retrieval` | 220 | 0/16 | **16/16** | 311 |
| `value_of_information` | 340 | 0/12 | **9/12** | 449 |
| `bayesian_reasoning` | 280 | 0/12 | **8/12** | 309 |

`acquisition_timing`'s HTTP 500 is the same cause: truncation mid-channel makes
llama.cpp's harmony parser reject the output with *"does not match the expected
peg-native format"*. Corrected totals are roughly **82/100 work and 72/100
reasoning** against qwen35b's 85/71 — but stitched from per-task reruns, not a
recorded single pass. **This is a harness limitation, not a model defect:** any
reasoning model hits it, and the suites need a documented max-tokens multiplier
before one can be scored.

### Two real tasks found what the rubric could not

Given an actual sizing question from this box — does a 16.59 GiB model fit a
17.59 GiB heap at 131072 context — it **inverted the meaning of `-ngl`**, read
"offload" as *away from* the GPU, omitted the weights from the GPU budget
entirely, concluded 3.50 GiB, and answered **yes to both questions**, explicitly
recommending in production the `-ngl 38` setting that cannot fit. It invented a
supporting mechanism about streaming 16.6 GiB of weights per forward pass.

On a review of `conf_is_safe`, the credential guard in `llmctl`, it found two
real gaps (`bearer` and `private_key` are absent from the keyword list;
`user:pass` with no `@` evades the URL pattern) but claimed `access_token`,
`client_secret`, `api-key-file` and `password_file` were all missed when the
regex catches every one — the pattern anchors on `[^[:alnum:]]` before the
keyword and carries an explicit `([-_]?file)?` group. It also reported a syntax
error in a function that was merely truncated in the prompt.

**Verdict: keep, do not promote.** Excellent for bounded checkable work — 20/20
on executable code repair, 16/16 on retrieval, at 2.5x the incumbent's
generation speed in two thirds of the memory. Not trustworthy for unsupervised
engineering judgement. This is the deterministic-rubric overstatement the
DW-X1Pro and DW-ASUS-LINUX sections both document, for a third time: the rubric
put it level with the 35B, and two real tasks did not. It is also the strongest
argument yet for giving this machine the blind open-response review the other
two have.

## dw-bee-linux — Qwen3.6-35B-A3B tested and rejected, 2026-08-29

The generational upgrade, tested at the one quant this box can actually run.
Every variable except the model generation is held equal: same architecture
family (35B total / 3B active), same quant format (UD-IQ4_NL), same size class
(16.81 vs 16.59 GiB), same `-ngl 30`, same 131072 context, same b10276 build,
same day.

| | Qwen3.**5** IQ4_NL (incumbent) | Qwen3.**6** IQ4_NL | Qwen3.6 Q5_K_M on x1pro |
|---|---:|---:|---:|
| Work quality | **85/100** | 81/100 | 88/100 |
| Deep reasoning | **71/100** | 61/100 | 69/100 |
| Prefill | 169-179 t/s | 150.6 t/s | — |
| Generation | 11-12.3 t/s | 12.2 t/s | — |

Only the middle column is a valid comparison; the x1pro figure is a different
machine, quant and offload regime, per the rule stated for the tables above.

| Work task | 3.5 | 3.6 | | Reasoning task | 3.5 | 3.6 |
|---|---:|---:|---|---|---:|---:|
| Strict protocol JSON | 12/12 | 12/12 | | Logic grid | 0/12 | 0/12 |
| BOM consolidation | **9/10** | **3/10** | | Causal inference | 6/14 | 6/14 |
| Executable code repair | 20/20 | 20/20 | | Bayesian updating | **8/12** | **4/12** |
| Embedded C review | 8/12 | **10/12** | | Hypothesis discrim. | **12/12** | 10/12 |
| Protocol architecture | 14/18 | 14/18 | | Adversarial epist. | 14/14 | 14/14 |
| 35K retrieval | 16/16 | 16/16 | | Value of information | **8/12** | 6/12 |
| Scope control | 6/6 | 6/6 | | Wason selection | 9/10 | 9/10 |
| Acquisition timing | 0/6 | 0/6 | | Complex policy | **14/14** | 12/14 |

### Interpretation

- **The newer generation is worse here, on both suites.** Reasoning loses four
  tasks and wins none. Work loses one task and wins one.
- **The work loss is a self-contradiction, not ignorance.** On
  `bom_consolidation` Qwen3.6 returned `voltage_valid: false` — correctly
  judging the 25 V candidate invalid for a rail with a verified 36 V transient
  — and then selected that exact part anyway with `add_new_sku: true`, while
  reporting `annual_unit_savings_usd` as 16000 instead of 16.00, a 1000x error.
  This is the internal-inconsistency failure the blind judges caught in
  Mistral-Small-4; here the deterministic rubric happened to catch it.
- **The incumbent's 9/10 understates it.** Its lost point was
  `setup_cost_usd: 0.0`, which is defensible: it declined the new SKU, so the
  $40 qualification cost is never incurred. The rubric wants 40 regardless.
  Worth fixing if that task is ever revised.
- **The likely cause is quant sensitivity, not a weak model.** The same
  Qwen3.6-35B-A3B scores 88/69 at UD-Q5_K_M on dw-x1pro-linux, fully offloaded
  with q8_0 KV. It drops 7 points of work quality across the Q5 -> IQ4_NL gap
  while Qwen3.5 holds 85 at IQ4_NL. **This box cannot close that gap:** Q5_K_M
  is 24.64 GiB against a 17.59 GiB Vulkan heap and 27.18 GiB MemTotal, and does
  not fit at any `-ngl`.
- **`general.architecture = qwen35moe`.** Qwen reuses architecture ids across
  generations, confirming the correction recorded above: the March build would
  have loaded this model all along, and there never was a Qwen3.6 arch gate.
- Speed is indistinguishable from the incumbent at matched quant and `-ngl`, as
  expected for identical active-parameter count.

**Qwen3.5-35B-A3B IQ4_NL remains the default.** Three candidates have now been
measured against it on this box — the 9B, gpt-oss-20b and Qwen3.6 — and none
displaced it.

## dw-spark0 results — 2026-08-23, machine record recovered 2026-08-31

The first DGX Spark run: GB10 Blackwell (sm_121), 128 GB unified LPDDR5X at
~273 GB/s, 20 cores. **Not comparable to any table above** — different hardware,
different quantisations, and the only machine here whose GPU and CPU share one
memory pool. The two models are comparable to each other: same machine, same
harness, thinking disabled on both, llama.cpp in both cases.

Both are compressions of the same base model, DeepSeek-V4-Flash-0731 (284B total
/ 13B active, MIT, 1M native context), pruned from 256 routed experts per layer
down to 132. They differ only in *how*: **REAP** prunes the low-saliency experts
and drops them; **REAM** merges them into the survivors.

| | REAP-150B MXFP4 (`deepseek-flash-150b`) | REAM-120B NVFP4 (`deepseek-vllm-120b`) |
|---|---:|---:|
| Work quality | **91/100** | 69/100 |
| Deep reasoning | **57/100** | 52/100 |
| Work suite wall time | 162.57 s | **106.39 s** |
| Reasoning suite wall time | 145.15 s | **94.64 s** |

| Work task | REAP | REAM | | Reasoning task | REAP | REAM |
|---|---:|---:|---|---|---:|---:|
| Strict protocol JSON | 12/12 | 12/12 | | Logic grid | 0/12 | 0/12 |
| BOM consolidation | **10/10** | 1/10 | | Causal inference | **0/14** | 6/14 |
| Executable code repair | 20/20 | 20/20 | | Bayesian updating | 4/12 | 4/12 |
| Embedded C review | 10/12 | 10/12 | | Hypothesis discrim. | 12/12 | 8/12 |
| Protocol architecture | **16/18** | 8/18 | | Adversarial epist. | 12/14 | 14/14 |
| 35K retrieval | 16/16 | 16/16 | | Value of information | **10/12** | 4/12 |
| Scope control | 6/6 | 2/6 | | Wason selection | 9/10 | 2/10 |
| Acquisition timing | 1/6 | 0/6 | | Complex policy | 10/14 | 14/14 |

### Interpretation

- **REAP-150B scored 91/100 on Spark #1 and 81/100 on Spark #2 — the same
  weights file, the same flags, a rebuilt machine.** Read the 91 as the top of a
  range, not a record. At 91 it would lead this repo; at 81 it sits below
  DW-X1Pro's `qwen3.6-35b-a3b-q5` (88) and level with the DW-ASUS-LINUX
  incumbent. See **Reproducibility** below — the entire 10-point gap comes from
  two keyword-rubric tasks, and every exact and executed task reproduced
  bit-for-bit. The claim that survives is narrower and still interesting: it beat
  the dense-27B line on the exactly-graded half of the suite, twice.
- **This is the first time the active-parameter rule has been broken.** Five
  times running — 122B-A10B, 284B-A13B, Mistral Small 4 at ~6.6B active, and
  others — the model with more *active* parameters won, and a 27B dense beat
  everything larger. Here a 13B-active MoE beats a 27.8B dense model. The
  difference is generation, not size: DeepSeek V4-Flash is April 2026,
  contemporary with Qwen3.8, where every previous large challenger was
  Qwen3.5-era or older. Size still buys nothing on its own; being current does.
- **REAP vs REAM is a 22-point gap on the work suite from an identical base
  model, identical expert count and identical size.** The whole difference is
  pruning versus merging. It shows up as a *quantitative* collapse, not a general
  one: REAM matched REAP exactly on strict JSON (12/12), code repair (20/20),
  embedded C (10/12) and retrieval (16/16), then scored 1/10 on BOM
  consolidation, 8/18 on protocol architecture and 2/6 on scope control. The
  publisher's own numbers say the same thing — mean 0.8248 for REAP against
  0.6952 for REAM, with REAP at 132 experts actually scoring +0.80 mean *above*
  the unpruned 284B base while REAM loses 12.16. **Take REAP, never REAM.**
- **REAM also emitted raw `<tool_calls>` XML that the `deepseek_v4` parser did
  not catch**, which is a serving defect on top of the quality one.
- **`value_of_information` 10/12 is the best result that task has ever
  recorded** (previous ceiling 9/12, on DW-X1Pro). `protocol_architecture` 16/18
  is second only to Mistral Small 4's anomalous 18/18 on DW-ASUS-LINUX.
- **REAP scored 0/14 on causal inference while the model it beats by 22 points
  scored 6/14.** The suite ceiling on that task is 12/14 (`gpt-oss-20b`). A
  0 from the strongest work model on the suite is more likely a formatting or
  parsing failure than a reasoning one, and the saved response should be read
  before the number is trusted.
- **Deep reasoning 57/100 is mid-table** — below `qwen3.8-27b-fp8`'s 71 and well
  below `qwen3-coder-next-iq4-xs`'s 83. The division of labour that follows:
  **REAP-150B for engineering work, a Qwen for open reasoning.**
- **Acquisition timing scored 1/6, which ties the ceiling** rather than breaking
  it. Across every machine and model in this repo nothing has exceeded 1/6. The
  standing recommendation holds: compute link budgets with a tool, then ask the
  model to interpret checked numbers.
- **No blind open-response review was run for this machine.** The DW-X1Pro and
  DW-ASUS-LINUX sections both show the deterministic rubric overstating models on
  the open tasks. REAP's 16/18 on protocol architecture should be read with that
  history in mind — it is exactly the shape of result that the blind judges have
  twice contradicted.

### Reproducibility — the rubric tasks are the only thing that moved

Both suites were re-run on Spark #2 on 2026-08-31 against the identical GGUF,
with llama.cpp master `458681e` (8 days newer than Spark #1's build), results in
`*-RERUN-spark2.json`. **Work 91 -> 81, deep reasoning 57 -> 57.**

| Grading | Tasks | Result |
|---|---|---|
| Exact match | strict_protocol_json, bom_consolidation, long_context_retrieval, scope_control, acquisition_timing, logic_grid, causal_inference, bayesian_reasoning, hypothesis_discrimination, value_of_information, wason_selection | **all identical** |
| Executed | code_repair | **identical, 20/20 both** |
| Keyword rubric | embedded_c_review 10->6, protocol_architecture 16->10, adversarial_epistemology 12->10, complex_policy_reasoning 10->12 | **every one moved** |

Deep reasoning held at 57 only because its two rubric swings cancelled (-2, +2).
Nothing else changed anywhere.

The mechanism, measured by diffing the saved responses:

| Task | chars | similarity | score |
|---|---|---|---|
| `strict_protocol_json` | 217 -> 217 | **1.000, byte-identical** | 12 = 12 |
| `code_repair` | 481 -> 453 | 0.964 | 20 = 20 |
| `protocol_architecture` | 2229 -> 2265 | **0.073** | 16 -> 10 |

At temperature 0 a short constrained answer is bit-reproducible across different
silicon and different CUDA builds. A long free-form answer is **93% different** —
floating-point divergence between builds compounds over thousands of tokens into
a different essay — and the keyword rubric then scores that essay six points
apart. The executed task is unbothered.

**CONSEQUENCE FOR EVERY TABLE IN THIS FILE: cross-machine comparisons are sound
on the exact and executed tasks and are worth about +/-6 points on the rubric
tasks.** The three earlier sections each noted the rubric overstating models
against blind judges; this is the first measurement of how much it moves on its
own, with the model held constant. Prefer the exactly-graded subtotal when
ranking models across machines, and treat a rubric-driven margin under ~10 points
as no margin at all.

### Serving facts, and a caution about how they were nearly lost

Measured on the first Spark, 2026-08-23, and reproduced on its replacement,
2026-08-31 (see `inventory/machines/dw-spark0/`):

| | Spark #1, 2026-08-23 | Spark #2, 2026-08-31 |
|---|---:|---:|
| Load time | not recorded | 86 s |
| Prefill | ~590 tok/s | 589.0 tok/s |
| Single-stream generation | 15.3 tok/s | 15.8 tok/s |
| TTFT | ~250 ms | 2.59 s (1526-token prompt) |
| Resident footprint at 4x256K | ~90 G | 101.5 G |

- **Aggregate throughput is FLAT at ~15.4 tok/s across 1, 2 and 4 streams.** A
  bandwidth-bound MoE decode whose experts differ per token gets *zero* batching
  gain on ~273 GB/s; per-stream throughput simply divides. Do not size
  concurrency on this machine expecting the vLLM-style scaling that the dual-3090
  box shows (4.98x on Qwen3.6-35B-A3B). This is the single most important
  operational fact about the Spark.
- KV measured **8.33 KiB/token** by memory differencing, so 1M total context
  costs ~8.5 G and four 256K slots fit inside the 115000 MB budget.
- `VRAM_PER_GPU_MB` must be set **by hand**. `nvidia-smi` reports `[N/A]` for
  every memory field on GB10 unified memory; llmctl falls back to `MemTotal`
  (124609) and 115000 is the value that leaves the OS its ~9.6 G.
- **MXFP4_MOE is the baseline, not a quantisation.** DeepSeek ships the routed
  experts in MXFP4 already and llama.cpp's converter repacks them without
  changing a value, so the GGUF is numerically identical to the safetensors
  checkpoint. Every rung below it (Q3_K_M / IQ3_XXS / Q2_K) is a requantisation
  of already-4-bit data and costs more than the same rung would from bf16.
- **There is no vendor-blessed recipe for this configuration.** The official vLLM
  recipe covers the unpruned 148.66 GiB FP8 checkpoint and lists DGX Spark only
  as a *cluster* target. The 85 GB REAP MXFP4 build under llama.cpp is what makes
  a single Spark viable, and it is off the supported path by construction.

**The machine record for the first Spark was never committed, and the box was
wiped on 2026-08-31.** Only the four result files in `evals/results/dw-spark0/`
had been pushed — under a filename convention that does not match the one in
**Run** below (`MODEL-work.json` / `MODEL-reasoning.json` instead of
`MODEL.json` / `deep-reasoning-MODEL.json`). The `machine.conf`, the `models.d/`
recipes and `stats.jsonl` were lost with the reinstall; everything above was
reconstructed from a manual backup taken 40 minutes before the wipe. **Run
`llmctl machine record` and commit it on the day a machine is brought up**, not
when the results happen to be interesting.

## Thinking on vs off, and what the token budgets were hiding — dw-spark0, 2026-09-01

Every result above this section was measured with `enable_thinking: False`. This
is the first measurement of a thinking model with thinking ON, run on
`qwen38-flash-next`, and it found two things: thinking is a large win on
reasoning and worthless on work, and **the per-task token budgets have been
silently capping scores across every machine in this file.**

### The budgets truncate, and always have

`max_tokens` caps total generation. The budgets (160 for `strict_protocol_json`,
520 for `protocol_architecture`, ...) are sized for a direct answer. Scanning
every recorded result for `completion_tokens >= budget`:

**55 truncated task-runs, 7 of which scored zero.** `protocol_architecture` hit
its 520-token ceiling in 12 runs across ALL FOUR machines; `embedded_c_review`
hit 420 in 7. Nobody's score on those two tasks measures the model — it measures
what fits in the budget. Both are keyword-rubric tasks, which is a second
mechanism behind the rubric volatility measured in the section above, alongside
float divergence between builds.

Quantified on `qwen38-flash-next`, thinking off, by re-running at 4x budget with
the new `--token-budget-scale`:

| | 1x budget | 4x budget |
|---|---:|---:|
| Work quality | 87 | **93** |
| Deep reasoning | 78 | 78 |

Six points of work quality were being thrown away by truncation alone
(`protocol_architecture` 10 -> 16). Deep reasoning was already clean.

The seven truncation zeros, for the record: `gpt-oss-20b` accounts for five and
was already known (its files are named `*-TRUNCATED.json`); `qwen3.8-27b-fp8`
NOPARSER lost `value_of_information` to it, which is why that run scores 64
against 71 with the parser enabled. The remaining one was NOT caught:
**REAP-150B's `causal_inference` 0/14 on both Sparks was truncated at 360/360**,
so the earlier note in this file claiming the task discriminates and REAP-150B
simply fails it is wrong — it was cut off, and may be losing on verbosity.

### Thinking on: a large win on reasoning, nothing on work

`qwen38-flash-next`, thinking off at 4x against thinking on at 8x (both
untruncated except where noted), via `--no-template-kwargs --strip-reasoning`:

| Reasoning task | off | on | | Work task | off | on |
|---|---:|---:|---|---|---:|---:|
| Logic grid | 0/12 | **12/12** | | Strict protocol JSON | 12/12 | 12/12 |
| Bayesian updating | 8/12 | **12/12** | | Executable code repair | 20/20 | 20/20 |
| Value of information | 10/12 | **12/12** | | 35K retrieval | 16/16 | 16/16 |
| Complex policy | 10/14 | **14/14** | | Scope control | 6/6 | 6/6 |
| Hypothesis discrim. | 12/12 | 12/12 | | BOM consolidation | 10/10 | *runs to 3002 tok* |
| Adversarial epist. | 14/14 | 14/14 | | Embedded C review | 12/12 | *truncated at 3360* |
| Wason selection | 10/10 | 9/10 | | Protocol architecture | 16/18 | *truncated at 4160* |
| Causal inference | 14/14 | *truncated at 2880* | | Acquisition timing | 1/6 | *truncated at 1440* |
| **Total** | **78** | **85** | | **Total** | **93** | *not measurable* |

- **`logic_grid` 0 -> 12/12 overturns this file's standing verdict on that task.**
  It is recorded above as non-discriminating, with the hypothesis that "the suite
  disables thinking and demands JSON only, removing the sequential search the
  puzzle needs". That hypothesis is correct, and the conclusion inverts: the task
  discriminates fine and every 0/12 ever recorded on it was measuring the
  harness, not the model.
- **Deep reasoning 78 -> 85, and the true figure is higher.** `causal_inference`
  scores 14/14 with thinking off and is the only remaining zero, so an
  untruncated thinking-on run lands nearer 99.
- **On work, thinking changes nothing where it completes.** Four tasks score
  identically. It is not that thinking fails on work — it is that these are
  format-constrained extraction tasks where deliberation has nothing to add.
- **And it is expensive.** `bom_consolidation` answers in 75 tokens with thinking
  off, scoring 10/10. With thinking on it terminates normally — `finish_reason:
  stop` — after **3002 tokens and 114 seconds**, having produced 11.5 KB of
  reasoning, and scores **9/10**. Forty times the tokens for a slightly worse
  answer.

**RULE, now measured rather than assumed: thinking ON for reasoning, OFF for
structured output.** It is a per-request decision via `chat_template_kwargs`, so
an agent can switch by task type rather than committing the server to one mode.

### Consequences for the tables above

1. `protocol_architecture` and `embedded_c_review` scores are capped by the
   harness on every machine. Mistral Small 4's anomalous 18/18 and everyone
   else's 10-16 were all measured against a 520-token ceiling.
2. Any thinking-capable model evaluated here has been measured with its main
   capability disabled. That is the correct default for comparability, but it is
   a floor, not a characterisation.
3. Raising the budget makes results incomparable with everything recorded at
   1.0, which is why `--token-budget-scale` defaults to 1.0 and why a thinking-on
   run must be paired with a thinking-off run at the same scale.

## Harder tasks — the `--extended` set, 2026-09-01

The eight default tasks are saturating. Across every run recorded in this repo:

| | runs | full marks | zeros |
|---|---:|---:|---:|
| `strict_protocol_json` | 16 | **16** | 0 |
| `scope_control` | 16 | 15 | 0 |
| `long_context_retrieval` | 16 | 14 | 0 |
| `code_repair` | 16 | 13 | 0 |
| `adversarial_epistemology` | 16 | 10 | 0 |
| `acquisition_timing` | 16 | 0 | **11** |

`strict_protocol_json` has never scored anything but 12/12; `scope_control` has
only ever scored 2 or 6. Five tasks are saturated and two are floors, so the
suite increasingly separates models only by the occasional zero — and today's
truncation finding showed how many of those zeros were mechanical.

`--extended` appends eight harder tasks, all **exactly or executably graded**,
never keyword-rubric, because the rubric tasks carry +/-6 points of noise with
the model held constant. It changes the denominator, so extended results compare
only with other extended results; the suite id becomes `work_quality_v1+hard` /
`deep_reasoning_v1+hard`.

| task | max | graded by |
|---|---:|---|
| `cobs_codec` | 24 | executed — known vectors, round-trip, overhead bound |
| `stream_reassembler` | 24 | executed — split chunks, resync, false sync in payload |
| `verilog_fifo` | 26 | **Icarus simulation + Verilator lint** |
| `cuda_reduction` | 26 | **nvcc compile + GPU execution + compute-sanitizer** |
| `cpp_mlp` | 28 | **g++ compile + run: finite-difference gradient check, XOR training** |
| `numpy_backprop` | 26 | **executed: finite-difference gradient check, circle dataset** |
| `kv_sizing` | 16 | exact numeric |
| `causal_identification` | 18 | exact |
| `resource_optimization` | 16 | exact, optimum brute-forced by the grader |
| `thermal_physics` | 16 | exact numeric |

Each was validated against a correct reference AND against plausible bugs, so the
scores form a gradient rather than pass/fail:

| task | correct | plausible bug | worse bug |
|---|---:|---:|---:|
| `cobs_codec` | 24 | 18 (254-byte boundary) | 13 (no grouping) |
| `stream_reassembler` | 24 | 21 (loses frame after bad checksum) | |
| `verilog_fifo` | 26 | 22 (blocking assignment) | 15 (`full` never asserts) |
| `cuda_reduction` | 26 | 24 (barrier in divergent branch) | 8 (no bounds guard) |
| `cpp_mlp` | 28 | 20 (forgets averaging) | 13 (missing tanh derivative) |
| `numpy_backprop` | 26 | 18 (zero init) | 14 (missing tanh derivative) |
| `resource_optimization` | 16 | 12 (right set, wrong greedy) | 4 (greedy as optimal) |
| `thermal_physics` | 16 | 13 (rise reported as temperature) | |

### The two ML tasks are graded by gradient checking

Both ask for a two-layer network's forward pass, loss and ANALYTIC gradients —
`cpp_mlp` from scratch in C++ with nothing but `<cmath>`, `numpy_backprop`
vectorised with numpy. Neither is graded by "does it look like backprop": every
parameter is perturbed and the analytic gradient compared against the finite
difference, to 1e-4 (C++) and 1e-5 (numpy). A derivation that is plausible and
wrong cannot pass, and the classic error — dropping the tanh derivative
`(1 - h^2)` — lands at 13/28 and 14/26 respectively.

Two failures the gradient check alone would miss, so both are tested separately:

- **Symmetric initialisation.** Zero-initialised weights give perfectly CORRECT
  gradients and a network that cannot learn, because every hidden unit stays
  identical. `numpy_backprop` checks initialisation variance and training
  accuracy independently of the gradient check; that variant scores 18/26 with
  `gradient_matches_numeric` still true.
- **Accumulating instead of overwriting gradients.** The C++ harness calls the
  candidate TWICE INTO THE SAME BUFFER. Passing a fresh `std::vector` would not
  test it — vectors zero-initialise, so accumulation silently gives the right
  answer, and that variant scored 28/28 until the buffer was reused.

`numpy_backprop` permits `import numpy` and nothing else; every other import
scores zero, which closes the `from sklearn.linear_model import LogisticRegression`
path. Training uses a dataset the GRADER generates (inside-vs-outside a circle),
not the XOR in the prompt, so memorising the example does not help. Requires
`sudo apt install -y python3-numpy` — the system interpreter is
externally-managed, so pip cannot install into it.

Three points worth keeping:

- **`verilog_fifo` scores on two independent axes.** Icarus says whether it
  *works*; Verilator lint says whether it is synthesisable RTL rather than
  something that merely simulates. A blocking assignment in a sequential block
  passes every behavioural check and is caught only by lint — which is exactly
  the class of bug that reaches silicon.
- **`cuda_reduction` pads and POISONS the input past `n`.** Without that, a
  kernel with no bounds guard reads freshly-zeroed memory and passes by luck; it
  scored full marks until the tail was poisoned, and 8/26 after.
- **Tooling absence degrades, it does not fail.** Missing iverilog/verilator/nvcc
  records `simulator: absent` or `nvcc: absent` and falls back to structural
  checks, and a busy GPU records `gpu: unavailable`. A machine without the
  toolchain still produces a valid, visibly weaker number instead of scoring a
  correct model zero. Install with `sudo apt install -y iverilog verilator`;
  compute-sanitizer ships with CUDA.

`extract_code` was also generalised to accept any language fence. It previously
matched only ```` ```python ```` or a bare fence, so a ```` ```verilog ```` reply
fell through and the backticks themselves were handed to the parser — a latent
zero for any non-Python task.

## dw-spark0 clean sweep — 2026-09-01

Five models, one load each, both suites fully tiered, 12k-token floor, retry on
by default from model 2's reasoning suite onwards. Live table:
[`results/dw-spark0/LEADERBOARD.md`](results/dw-spark0/LEADERBOARD.md).

| model | work L/E/M/H = total | reasoning L/E/M/H = total | conc 1/2/4/8 |
|---|---|---|---|
| **Fable 5.1 (reference)** | 100/64/154/120 = **438** | 100/56/68/78 = **302** | — |
| `qwen38-flash-next` | 98/64/136/111 = **409** (retry×5) | 78/56/46/32 = **212** (retry×9) | 22/36/48/48 |
| `qwen38-27b-nvfp4` | 84/64/130/92 = **372** (retry×6) | 79/48/51/30 = 208 (retry×9) | 11/20/41/**79** |
| `qwen38-27b-fp8` | 91/64/118/109 = **383** (retry×6) | 75/48/37/**67** = **227** (retry×10) | 8/16/31/59 |
| `deepseek-flash-150b` | 94/64/132/98 = **388** (retry×8) | 69/56/22/27 = **174** (retry×14) | 15/14/34/33 |
| `nemotron-120b` | 96/61/122/117 = **396** (retry×7) | 83/42/31/36 = 192 (retry×12) | see table |

### Nemotron, measured after all

The "silent 40-minute init" was FlashInfer JIT-compiling the sm_120 fused-MoE
kernel — 68 CUTLASS files — one at a time under my `MAX_JOBS=1`. With `MAX_JOBS=4`
it built in five minutes (memory peaked at 109/121 GiB; that is the ceiling) and
is cached for good. Measured 19:18–19:36, the fastest battery of the five at 13
tok/s with terse answers: **work 396/438, hard tier 117/120** — `cpp_hard`,
`cuda_hard`, `ml_hard` all perfect, `verilog_hard` 27/30 — against reasoning
192/302 with three genuine zeros: `sizing_easy` cached K and forgot V (exactly
half the right answer, the trap detector fired), `optimization_medium` chose a
173 GiB set for a 112 GiB budget, `sizing_medium` wrong throughout. It is the
second large MoE, after deepseek, to write flawless hard-tier code and fail
multi-step arithmetic that the dense 27B gets right. It also maxed
`acquisition_timing` 6/6 — the first local model to, on the corrected keys.

### Cold vs retry on the same weights

Both 27B builds were re-run with retry on, giving the only same-model,
same-prompt, same-build comparison in this file (cold files kept under
`results/dw-spark0/cold/`).

| model | suite | cold | retry | tasks that changed |
|---|---|---:|---:|---|
| `qwen38-27b-nvfp4` | work | 370 | 372 | `acquisition_timing` 1→3 (renamed keys, not comparable) |
| `qwen38-27b-nvfp4` | reasoning | 208 | 208 | none |
| `qwen38-27b-fp8` | work | 365 | **383** | **`verilog_hard` 2→19** (retry scored 27, credited ×0.7) |

Forty-one of forty-two NVFP4 task scores were IDENTICAL across two loads two
hours apart — the exact and executed tasks are behaving as instruments — and the
retry earned NVFP4 nothing: given `rdata is not a valid l-value ... declared here
as wire`, it resubmitted a design that still did not compile. The FP8 build of
the SAME weights read the same message and fixed the FIFO to 27/30. One pair, so
it may be a coin flip at temperature 0 rather than a quantisation effect — but
it is the second time NVFP4 and FP8 have diverged sharply on a hard task (the
other being hard reasoning, 30 vs 67), and both times FP8 was the one that
reasoned its way through.

### What the retry measured

Forty-six do-overs across four models. The feedback TYPE decided everything:

- **Compiler and checker output repairs code.** `qwen38-flash-next` took
  `verilog_hard` from 7 to a perfect 30 — the CDC FIFO both 27B builds failed at
  2/30 cold — and `ml_medium` from 0 to 26. Both started from a specific error:
  a compile failure, a named failing test.
- **CORRECTION: the CUDA "repairs" were not repairs.** `cuda_easy` 6 -> 16 and
  `cuda_medium` 10 -> 26 were first reported as retry successes. Regrading with
  the GPU free scored the FIRST attempts at 16/16, 26/26 and 30/30. Those first
  scores — 6, 10, 8 — are exactly the graders' `gpu: unavailable` fallbacks: the
  sweep's own model was saturating the GPU, `cudaMalloc` failed, and correct
  kernels were given partial credit. `deepseek-flash-150b` lost 22 points on
  `cuda_hard` to it. The CUDA graders now retry the binary six times with
  backoff before falling back, and any row still marked `gpu: unavailable` must
  be regraded once the GPU is free. Corrected: deepseek work 388, Flash-Next 409.
- **Field names do not repair arithmetic.** Thirty-three reasoning retries
  across three models produced ONE credited gain (`logic_grid` 3 -> 4). Told
  which numeric field was wrong, every model re-derived the same wrong number.
  "failed checks: kv_bytes_per_token" names the symptom; a compiler error names
  the line.
- **A retry can make things worse.** `deepseek-flash-150b` `ml_medium` went
  14 -> 0: given a gradient-check failure, it rewrote working code into code
  that did not run. The never-lower rule kept the 14. It is not a nicety.

### What the tiers separated

- Every model swept the easy tier or nearly so (59-64/64); the frontier
  reference is flat at 100% through hard. The hard tier is where they part:
  111, 92, 92, 76 on work; 32, 30, 67, 27 on reasoning.
- **Same weights, two quantisations, hard reasoning 30 vs 67** (NVFP4 vs FP8,
  both cold). One pair is not a conclusion, but it is the largest quant effect
  seen anywhere in this repo and it lands on the hardest tier. Worth a deliberate
  re-run.
- `deepseek-flash-150b` writes a correct CDC FIFO (26/26 on `verilog_medium`,
  the only model to do so cold) and scores 0 on a thermal time constant, 0 on a
  two-constraint knapsack and 0 on KV sizing. A 150B MoE with a specific,
  narrow hole in multi-step arithmetic.
- `acquisition_timing`, never passed by any model before the key rename, now
  scores 4/6 on deepseek and 1-4/6 elsewhere. It was measuring the key name.

### Concurrency, now that STREAMS is set fairly

`qwen38-flash-next` at `STREAMS=4` scales 22 -> 48 to four streams and holds
there — it batches, up to its slot count. The earlier "flat at 25" reading was
`STREAMS=1`, a configuration artifact, not the model. The dense 27B under vLLM
still leads at 8 streams (79), because a dense model amortises weight reads
across a batch and a sparse MoE routing to different experts per token cannot.

## Frontier control — 740/740, 2026-09-01

> Live standings for this machine, regenerated as each model completes: [`results/dw-spark0/LEADERBOARD.md`](results/dw-spark0/LEADERBOARD.md) (`python3 evals/leaderboard.py`).


The full extended battery — 22 work tasks and 20 reasoning tasks across three
tiers — was answered offline by a frontier model of the same family (Claude,
Opus 5 then Fable 5.1) and graded with the identical graders the local models
face. The point is the inversion: a local model scoring low is ambiguous, but a
frontier model scoring below full marks is a **harness suspect by default**.

| | control | |
|---|---:|---|
| work (legacy + easy + medium + hard) | **438/438** | every task achievable at 100% |
| reasoning (legacy + easy + medium + hard) | **302/302** | after three rubric fixes below |

The 42 answers are committed under `results/frontier-control/answers/` as
**validated reference solutions**. Every one scores full marks against the
current graders, so any future grader change can be checked against them
offline in seconds, without a model. That is how the bugs below should have
been caught before any local model ran.

### What the control found

Two harness bugs, plus a systematic weakness in the legacy rubric:

- **`acquisition_timing` had never been passed by any model on any machine**
  (ceiling 1/6; the README recommended routing around it with a tool). The
  control scored 4/6, failing exactly `data_bits_per_sample` and
  `payload_bit_rate`. Its wire time was 96.0 ms/s — precisely right, meaning it
  used all 48 bits per transaction in the physics — and it then answered the key
  AS NAMED: 24 data bits. The grader wanted 48, data + status + framing. The
  task was never hard; the key was mis-named, and every model that read it
  literally was marked wrong for being correct. Renamed to
  `bits_per_transaction` / `bus_bit_rate` with the definition in the prompt; the
  control then scored 6/6.
- **`ml_easy` failed with `NameError: name 'np' is not defined`.** The prompt
  said "return ONLY the two functions" and also that `import numpy as np` was
  the only import *permitted*. The control obeyed the first literally and
  omitted the import; the grader's exec environment was bare. Permitted is not
  required — all `ml_*` graders now supply `np` themselves.
- **Three legacy keyword-rubric checks failed a demonstrably correct answer**,
  and the control was then given one chance to defend each. All three verdicts
  were "grader too narrow": `websites_not_independent` wanted "not
  independent"/"copy"/"echo" and got *"one independent accusatory source, not
  four ... counting them separately double-counts a single claim"*;
  `four_not_converse` wanted one of four words and got a correct argument in
  others; `asymmetric_errors` wanted the literal substring "false positive" and
  the answer wrote **"false-positive"** — a hyphen. Hyphens are now normalised
  before matching, and the control's phrasings added to the lists. Re-grading
  every historical result with the new lists moves +3 points across 2 task-runs
  in the whole repo, both legitimate.

That is the third independent failure mode found for the same three rubric tasks
in one day — run-to-run noise of +/-6 with the model held constant, truncation
caps in every recorded run, and now vocabulary. Broadening keyword lists defers
the problem rather than solving it. **Rank models on the exactly-graded and
executed subtotal; report rubric tasks separately as directional.**

### What the control settled

`verilog_hard` — `qwen38-27b-nvfp4` scored 2/30, failing to compile because it
drove `rdata` from an `always` block without declaring it `output reg`. The
control scored 30/30 on the same prompt: Gray pointers via `(x >> 1) ^ x`,
two-flop synchronisers, registered flags, lint clean. The 2 was the model.

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

## Run — the three-part baseline

**Every model gets all three: work quality, deep reasoning, and a concurrency
sweep.** The first two measure whether the model is any good; the third measures
whether it can back an agent rather than answer one question at a time, and it
has decided adoption here as often as quality has. Concurrency numbers were
measured this way from 2026-08-04 onwards but lived only as prose in machine and
model NOTES until `concurrency_sweep.py` was committed on 2026-09-01 — the
sweeps behind "every model peaks at FOUR concurrent" are not reproducible.

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

```bash
python3 evals/concurrency_sweep.py \
  --url http://127.0.0.1:PORT/v1/chat/completions \
  --model SERVED_MODEL_ID \
  --key-file ~/.config/llama.cpp/api-keys \
  --output evals/results/MACHINE/concurrency-MODEL.json
```

The key is read for authentication and is never written to the result file.

### Reading a concurrency sweep

Aggregate tok/s is the number that matters; per-stream decay and TTFT say what
it costs each client. A server can hold aggregate up while making everyone wait
much longer, which is the failure mode that ruins interactive use — DW-ASUS-LINUX
recorded TTFT reaching 64.8s at 8 concurrent on the 122B while aggregate still
looked respectable.

**Whether a model batches at all is a property of its architecture, not the
box.** Measured on dw-spark0 (GB10, ~273 GB/s) 2026-09-01:

| streams | 1 | 2 | 4 | 8 |
|---|---:|---:|---:|---:|
| `qwen38-27b-fp8` dense, vLLM — aggregate | 7.7 | 14.9 | 29.5 | **52.3** |
| — per stream | 7.7 | 7.6 | 7.6 | 6.7 |
| — TTFT | 0.18s | 0.30s | 0.29s | 2.38s |

**6.79x from 1 to 8 streams, with per-stream barely moving.** Against REAP-150B
on the same box, whose aggregate is FLAT at ~15.4 tok/s across 1/2/4 — per-stream
simply divides. The difference is dense versus sparse: batching amortises weight
reads across the batch, so a dense model reads its weights once and serves the
whole batch from them, while a MoE routing each token to different experts has
nothing to amortise. So "this box is bandwidth-bound and will not batch" is
wrong as a general claim — it is true only of sparse MoE decode. A single-stream
figure of 7.7 tok/s becomes 52.3 aggregate under load, which is a different
machine for agent work than the single-stream number suggests.

Note the suites themselves are strictly sequential and always have been, so
their wall-clock times are single-stream figures and must not be read as
throughput.
