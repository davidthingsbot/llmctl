# Mistral lineup survey — which, if any, is worth serving on DW-ASUS-LINUX

**Date:** 2026-08-08/09
**Machine:** DW-ASUS-LINUX (dual RTX 3090, 47.1 GiB usable, ~0.7 GiB held by the desktop)
**Constraint:** the 128K context floor, at a usable quantisation
**Prior:** `Mistral-Medium-3.5-128B` was fetched and rejected on 2026-08-05 (see machine.conf NOTES)

## Summary

Ran the mandatory pre-download KV check across every current-generation Mistral
before fetching anything. Three results matter:

1. **`Devstral-Small-2-24B-2512` is the only candidate the recorded evidence gives
   a real chance.** 24B dense, so its ACTIVE parameter count is in the same class
   as the incumbent Qwen3.6-27B dense that won the 2026-08-05 quality suite. Fits
   at 128K with margin. **Fetched.**
2. **`Mistral-Small-4-119B-2603` uses MLA, not GQA — and that overturns a
   conclusion already recorded in machine.conf.** Its KV is 11.25 KiB/token
   against Medium 3.5's 176. A 119B model reaching the 128K floor on 48 GiB was
   recorded as impossible; that reasoning assumed dense attention. **Fetched, to
   settle the hardware question, not because it is expected to win.**
3. **`Devstral-2-123B-2512` is the same trap as Medium 3.5 and must not be
   downloaded.** It shares Medium 3.5's geometry exactly — 88 layers, 8 KV heads,
   head_dim 128 — hence the same 176 KiB/token and the same 22 GiB of KV at 128K.
   It misses the floor at *every* quantisation that exists, including UD-IQ1_S.

## Method, and its validation

Per the rule added on 2026-08-05, KV/token was computed from each model's
`config.json` on HF *before* any download:

```
KV/token = n_layer x (key_length + value_length) x n_head_kv x bytes_per_elem
```

**The formula was validated against the known case first.** Medium 3.5:
`88 x (128+128) x 8 x 1 byte = 180,224 B = 176 KiB/token`, reproducing the
recorded figure exactly. The Small 4 parameter reconstruction was likewise
checked against the published total: 128 routed + 1 shared expert at
`3 x 4096 x 2048` each, plus MLA attention, plus untied embeddings, totals
**119.0B against the repo's stated 119B**, so the architecture read is sound.

## KV cost per token

| Model | Attention | Layers | KV/token (q8_0) | @128K | @256K |
|---|---|---|---|---|---|
| Mistral-Medium-3.5-128B *(rejected 08-05)* | dense GQA | 88 | 176 KiB | 22.0 GiB | 44.0 GiB |
| Devstral-2-123B-2512 | dense GQA | 88 | 176 KiB | 22.0 GiB | 44.0 GiB |
| Devstral-Small-2-24B-2512 | dense GQA | 40 | 80 KiB | 10.0 GiB | 20.0 GiB |
| Ministral-3-14B-2512 | dense GQA | 40 | 80 KiB | 10.0 GiB | 20.0 GiB |
| Ministral-3-8B-2512 | dense GQA | 34 | 68 KiB | 8.5 GiB | 17.0 GiB |
| Ministral-3-3B-2512 | dense GQA | 26 | 52 KiB | 6.5 GiB | 13.0 GiB |
| **Mistral-Small-4-119B-2603** | **MLA (K-only)** | 36 | **11.25 KiB** | **1.4 GiB** | **2.8 GiB** |

For reference from earlier work: hybrid Qwen ~24 KiB/token, GLM-4.7-Flash 53 KiB/token.

## Fit check (weights + KV, budget ~44 GiB to leave a safe margin)

| Candidate | Weights | @128K | @4x128K |
|---|---|---|---|
| Devstral-Small-2-24B FP8 | 24.02 | **34.0 OK** | 64.0 no |
| Devstral-Small-2-24B Q8_0 | 23.33 | **33.3 OK** | 63.3 no |
| Devstral-Small-2-24B UD-Q6_K_XL | 19.36 | **29.4 OK** | 59.4 no |
| Ministral-3-14B Q8_0 | 13.37 | **23.4 OK** | 53.4 no |
| Mistral-Small-4-119B UD-IQ2_M | 34.99 | **36.4 OK** | **40.6 OK** |
| Mistral-Small-4-119B UD-IQ3_XXS | 39.86 | **41.3 OK** | 45.5 no |
| Mistral-Small-4-119B UD-IQ3_S | 41.36 | **42.8 OK** | 47.0 no |
| Devstral-2-123B UD-IQ1_S | 26.49 | 48.5 no | 114.5 no |
| Devstral-2-123B UD-IQ2_M | 40.55 | 62.5 no | 128.6 no |
| Mistral-Medium-3.5 UD-IQ2_M *(measured 08-05)* | 41.08 | 63.1 no | 129.1 no |

Multi-slot figures are llama.cpp fixed slots. On vLLM the pool is shared, so
Devstral-24B-FP8's leftover is a single pool of roughly 18-22 GiB, i.e. very
approximately 230-280K tokens at 80 KiB/token — to be MEASURED, not trusted,
and compared against 27b-fp8's tuned ~401K.

## MLA: why Small 4 is not another Medium 3.5

`Mistral-Small-4-119B-2603/config.json` carries `kv_lora_rank: 256`,
`q_lora_rank: 1024`, `qk_nope_head_dim: 64`, `qk_rope_head_dim: 64` — DeepSeek-style
Multi-head Latent Attention. The naive GQA reading of that config
(`num_key_value_heads: 32`, no GQA reduction) gives 288 KiB/token and would
disqualify it instantly. That reading is wrong.

Verified in the llama.cpp source at the installed build (b10270, commit 0713275):

* `src/llama-model.cpp` groups `LLM_ARCH_MISTRAL4` with
  `DEEPSEEK2 / DEEPSEEK2OCR / DEEPSEEK32 / GLM_DSA` — the MLA path, logging
  `n_lora_kv`, `n_embd_head_k_mla`, `n_embd_head_v_mla`.
* `src/llama-kv-cache.cpp` sets `has_v = !is_mla`: **MLA models allocate no V
  cache at all.** The cache is the compressed latent only,
  `kv_lora_rank + qk_rope_head_dim = 320` wide, over 36 layers.

Hence `36 x 320 x 1 byte = 11,520 B = 11.25 KiB/token` — less than half the
hybrid Qwen models, on a 119B model. **This is the generalisable finding: the
dense/hybrid split recorded on 2026-08-05 is really a three-way split, and MLA
is the cheap corner.** Attention family must be read off `config.json` before
KV is estimated; `num_key_value_heads` alone is misleading for MLA models.

## Engine support (checked, not assumed)

| | llama.cpp b10270 | vLLM 0.23.0 |
|---|---|---|
| `mistral3` / `ministral3` (dense Mistrals) | `LLM_ARCH_MISTRAL3` present | `Mistral3ForConditionalGeneration`, `Ministral3ForCausalLM`, `MistralForCausalLM` present |
| `mistral4` (Small 4) | `LLM_ARCH_MISTRAL4` present, on the MLA path | **absent — no source references at all** |

So **Small 4 is llama.cpp-only on this box.** It is MoE (128 routed experts,
top-4 + 1 shared), so `--n-cpu-moe` is available if a higher quant is wanted,
subject to the AVX-only CPU penalty.

## Verdicts

**Devstral-Small-2-24B-Instruct-2512 — fetched, test first.**
40 layers / 8 KV heads / head_dim 128; `max_position_embeddings` 393,216, so the
128K floor has large headroom. FP8 at 24.02 GiB
(`gdubicki/Devstral-Small-2-24B-Instruct-2512-FP8`, `Mistral3ForConditionalGeneration`,
fp8 static) serves on vLLM, where the ~4.8x multi-stream advantage is. Q8_0 23.33
and UD-Q6_K_XL 19.36 exist for a llama.cpp comparison.
*Open risk:* fp8 KV on sm_86 is unproven for this arch. The Ampere E4M3 limit is
MODEL-SPECIFIC (27b-fp8 and coder-30b work, GLM-4.7-Flash does not); if it fails,
drop `--kv-cache-dtype fp8` first. f16 KV doubles to 160 KiB/token = 20 GiB at
128K, which still fits but leaves little room.
*Fallback:* `levara/Devstral-Small-2-24B-TextOnly-FP8` (23.20 GiB,
`Ministral3ForCausalLM`) if the vision tower complicates startup.

**Mistral-Small-4-119B-2603 — fetched at UD-IQ2_M, expect it to lose on quality.**
Reconstructed at **~6.6B ACTIVE of 119B** (a 119B-A6B). The quality suite found
score tracks ACTIVE parameters: 122B-A10B and 284B-A13B both lost to the 27B
dense, and this has fewer active than either, at 2-bit. It is being fetched to
answer the *hardware* question — whether MLA lets a 119B model hold the 128K
floor on 48 GiB — which is worth knowing either way.

**Devstral-2-123B-2512 — do not download.** Identical geometry to Medium 3.5.
Fails at every existing quantisation. Recorded here specifically so it is not
re-attempted: it looks like a fresh December 2025 coding model and is the same wall.

**Ministral-3 family (3B / 8B / 14B, Instruct + Reasoning) — fit trivially, not
expected to win.** 14B at Q8_0 is 23.4 GiB at 128K, with official mistralai GGUFs
and a RedHatAI FP8-dynamic (16.60 GiB). But at 14B dense they carry roughly half
the incumbent's active parameters. Worth revisiting only as fast-draft or
specialist models, not as a replacement for 27b-fp8.

**Superseded / out of scope.** `Magistral-Small-2509` and
`Mistral-Small-3.2-24B-2506` are older generations and their
`max_position_embeddings` is 131,072 — exactly the floor, zero headroom.
`Mistral-Large-3-675B` is far out of range. Mixtral and Mistral-7B are legacy.

## RESULT — Devstral-Small-2-24B tested 2026-08-09: REJECTED

**Verdict: faster than the incumbent on every speed axis, decisively worse on
quality. Do not adopt as a replacement for 27b-fp8.**

Both models measured on THIS box with the same harness, thinking disabled on
both, so this is a true paired comparison — unlike the dw-x1pro table in
`evals/README.md`, which is different hardware at different quantisations.

| Suite | Devstral-24B FP8 | 27b-fp8 |
|---|---:|---:|
| work_quality_suite | **73/100** | **83/100** |
| deep_reasoning_suite | **51/100** | **70/100** |

| Work task | Devstral | 27b-fp8 |
|---|---:|---:|
| Strict protocol JSON | 12/12 | 12/12 |
| BOM consolidation | 6/10 | **10/10** |
| Executable code repair | 17/20 | **20/20** |
| Embedded C review | **10/12** | 8/12 |
| Protocol architecture | 6/18 | **10/18** |
| 35K-token retrieval | 16/16 | 16/16 |
| Scope control | 6/6 | 6/6 |
| Acquisition timing | 0/6 | 1/6 |

It won exactly one work task. The damning one is **executable code repair, 17/20
against 20/20** — graded by running the code against a hidden harness, and the
task a coding-specialised model should own. On reasoning it lost seven of eight,
including wason_selection 4/10 vs 9/10 and bayesian_reasoning 4/12 vs 8/12.

### Speed, where it genuinely wins

| Concurrency | Devstral aggregate / per-stream | 27b-fp8 aggregate / per-stream |
|---|---|---|
| 1 | 57.0 / 57.8 | 46.6 / 47.9 |
| 2 | 113.9 / 57.3 | 85.8 / 44.3 |
| 4 | 221.5 / 55.9 | 161.3 / 42.2 |
| 8 | **419.1** / 52.9 | 295.1 / 38.8 |

21-42% faster at every level, scaling 7.35x vs 6.3x, per-stream decaying only 8%
vs 19%, TTFT at 8 concurrent 0.10 s vs 0.64 s, and load 117 s vs 282 s. If a
future task is throughput-bound rather than judgement-bound, this is the profile
to come back to — but nothing measured here is judgement-bound in its favour.

### The pre-download arithmetic was exactly right

Predicted 80 KiB/token; vLLM allocated 9.07 GiB/card, reporting **GPU KV cache
size: 237,728 tokens**, which is **80.0 KiB/token**. That is 1.81x the 128K
floor, though still below 27b-fp8's tuned ~401K pool. **fp8 KV works on sm_86 for
this architecture** — the Ampere E4M3 risk did not materialise, so Mistral3
behaves like 27b-fp8, not like GLM-4.7-Flash. Headroom remains: vLLM reports that
`--gpu-memory-utilization 0.94` is effectively 0.9175 once CUDA-graph profiling
is counted, and 0.9625 would restore the difference.

### Three toolchain incompatibilities, none about the model

Worth weighing as real adoption cost — a Qwen model hits none of these:

1. **Tokenizer.** Load dies in seconds with `AttributeError:
   CachedMistralCommonBackend has no attribute is_fast`. vLLM decides "is this a
   Mistral repo?" by looking for `consolidated*.safetensors`; this FP8 build
   ships `model-0000N-of-00006.safetensors`, so it falls back to the HF path —
   but transformers 5.12.1 picks `MistralCommonBackend` anyway off `tekken.json`,
   and that class lacks `is_fast`. Fix: `--tokenizer-mode mistral`, which uses
   vLLM's own MistralTokenizer that implements it.
2. **Multimodal profiling.** `ValueError: Mismatch in image token count between
   text and input_ids` — vLLM's Mistral tokenizer and the HF PixtralProcessor
   disagree about `[IMG]`, so the dummy-image profile can never match. Fix:
   `--limit-mm-per-prompt '{"image":0}'`, correct here anyway.
3. **Eval harness.** Both suites hardcoded `chat_template_kwargs`, which vLLM
   rejects with HTTP 400 for Mistral tokenizers. Added a `--no-template-kwargs`
   opt-out rather than changing the default, since dropping it is a no-op for
   Mistral but NOT for the Qwen models.

**A trap recorded so it is not repeated:** deleting `tekken.json` makes both
auto-detectors agree and clears problems 1 and 2 at once. Do not do it —
transformers then warns this repo's `tokenizer.json` has an incorrect regex
pattern that "will lead to incorrect tokenization" unless loaded with
`fix_mistral_regex=True`. That would not crash anything; it would just make every
quality number quietly wrong.

### Two measurement traps

- **`llmctl bench` is wrong for terse models.** It reported 24-33 tok/s for
  Devstral because the model stops after ~11 tokens on the bench prompt, so fixed
  overhead dominates the average. Forced-length generation measures 57.9 tok/s —
  more than double. Any model that answers briefly will be understated this way.
- **27b-fp8 streams into `reasoning_content`, not `content`,** because of
  `--reasoning-parser qwen3`. A benchmark counting only `content` records zero
  tokens for it and silently reports nothing generated.

## What to measure next

Items 1 and 2 are DONE — see the RESULT section above.

> **HOLD — DO NOT RUN ITEMS 1 AND 2 BELOW UNPROMPTED.** David asked on 2026-08-09
> that Mistral-Small-4-119B **not** be loaded or tested when its download
> completes; he wants to direct that himself. The weights may finish arriving at
> `models/gguf/mistral-small-4-119b/` — leave them alone. Loading it requires
> taking `27b-fp8` off the GPUs, which is the model in daily use by the `hermes`
> and `mr-c` agents. Verifying the downloaded byte counts is fine; loading is not.

Remaining, when asked:

1. **Small 4 on llama.cpp: confirm the predicted 11.25 KiB/token empirically**
   from the KV allocation printed at load. That single number is the finding;
   the quality score is secondary and is expected to lose at ~6.6B active.
   Devstral's prediction landed exactly (80.0 vs 80.0), which raises confidence
   but does not substitute for the measurement — MLA is a different code path.
2. If Small 4 loads with room to spare, retest at UD-IQ3_XXS (39.86 GiB), which
   the arithmetic says fits single-slot at 41.3 GiB.
3. OPTIONAL, only if Devstral is ever wanted for a throughput-bound job: raise
   `--gpu-memory-utilization` from 0.94 to 0.9625 to recover the KV the
   CUDA-graph profiler reserves, and re-measure the pool. Recorded finding is
   that a bigger pool measured FASTER, so there is no tradeoff to balance.
4. Consider making `llmctl bench` force a minimum generation length, or flag
   runs where the model stopped early. As it stands it understated Devstral by
   more than 2x, and any terse model will be misreported the same way.
