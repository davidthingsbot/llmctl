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

## What to measure next

1. Devstral-24B-FP8 on vLLM at 128K: does `--kv-cache-dtype fp8` load on sm_86?
   Actual KV pool size in tokens vs 27b-fp8's ~401K. Single-stream and 8-concurrent
   throughput, TTFT.
2. Run both new models through `evals/work_quality_suite.py` and
   `evals/deep_reasoning_suite.py` for a like-for-like comparison against the
   existing results.
3. Small 4 on llama.cpp: confirm the **predicted 11.25 KiB/token empirically** from
   the KV allocation printed at load. That single number is the finding; the
   quality score is secondary.
4. If Small 4 loads with room to spare, retest at UD-IQ3_XXS (39.86 GiB), which
   the arithmetic says fits single-slot at 41.3 GiB.
