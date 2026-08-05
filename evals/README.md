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

## Caveats

- This is one deterministic run per model, not a statistical quality estimate.
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
```

The key is read for authentication and is never written to the result file.
