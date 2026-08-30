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
