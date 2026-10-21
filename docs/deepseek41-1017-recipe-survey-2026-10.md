# DeepSeek-V4.1-Flash-1017 on TensorFold: Mia's recipe surveyed, not adopted

**Date:** 2026-10-21
**Machines:** dw-spark0 (head) + dw-spark1 (worker), the 200G CX7 pair
**Question:** is Mia's new DeepSeek recipe worth a launch on the pair?
**Recipe:** [MiaAI-Lab/DeepSeek-v4.1-Flash-1017-2x-DGX-Sparks](https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-1017-2x-DGX-Sparks),
read at `5b865fe` (2026-10-21; repository created 2026-10-18)
**Incumbent:** `glm53-tensorfold` (see [glm-tensorfold-operation.md](glm-tensorfold-operation.md))
**Verdict:** hold. Nothing was downloaded, installed or started.

## Summary

The recipe is real and widely run: 27 different people opened its 39 issues and
pull requests in its first three days. On the publisher's numbers it decodes faster
than our GLM at one stream and matches it at four. But on these Sparks it is a
**512K model with about 6 GiB of headroom on the head**, not a 1M model. That
fails the >1M part of the adoption bar (several independent dual-Spark
verifications, multiple streams, more than 1M context). It is also three days old,
with engine patches landing daily and three open crash/stall reports.

## What the recipe is

- Model: DeepSeek's new `deepseek-ai/DeepSeek-V4.1-Flash-1017` (published 2026-10-17).
- Weights: `Mia-AiLab/DeepSeek-V4.1-Flash-1017-EXL3-EAQ-v1-2.9-bpw` @ `45ee5d0f`, 196 GiB,
  plus Engram's two tables (~203 GB) from the official repository @ `1bae0e10`. The
  model card has no perplexity or KL measurement against the unquantized model.
- Engine: TensorFold's native Zig engine with BertholomusAI's `dsv41` port (`TF_REF`
  `629c524`) plus Mia's patches. TP=2, one rank per Spark, RDMA over the CX7 link.
  This is the same engine family as our GLM.
- Features: 1,048,576-token window configured, 4 streams (`PARALLEL=4`), thinking,
  tools, image input, speculative decoding (DSpark) from the checkpoint's own draft blocks.
- Memory: ~98-99 GiB of weights per Spark; rank 0 holds ~104 GiB. `start.sh` refuses to
  start below 112 GiB available (`MIN_AVAIL_GIB`).

## Measured numbers against the incumbent

DeepSeek figures are the publisher's (README, sparkDash at `CONTEXT=524288`, and
`tools/bench.py`). GLM figures are ours. The tools differ, so the speed comparison
is rough, not a controlled A/B.

| | DeepSeek 1017 (Mia) | `glm53-tensorfold` (ours) |
|---|---|---|
| Decode, 1 stream | 74.9 prose / 109.9 code tok/s; 55-61 on random-word prompts | 60.4 code greedy, 65.8 chat sampled |
| Decode, 4 streams total | 130.0 prose / 155.5 code; 113-117 random words | 147.5 (high thinking, short replies) |
| Prefill | ~2,000-2,180 tok/s, 8K-256K | 1,910 tok/s at 50K |
| Longest tested prompt | needle 3/3 at 479,012 tokens | needle at 897,097 tokens |
| Head `MemAvailable` after load | ~6.5-7 GiB | ~11.5-12 GiB (worker ~13.7-13.9) |
| Vision | in the recipe; README: "image input ... not checked" on the pair | 70/78 evaluated |
| Quality on our suites | not run | reasoning 298/302, engineering 417/438 |

GLM sources: `evals/results/dw-spark0/glm53-tensorfold-high-20261001T115956Z/` and
`evals/results/dw-spark0/glm53-tr3-tensorfold-v110-high-20261008T173741Z/`.

For reference, the pre-1017 DeepSeek V4.1 EXL3 (Mia's older
`DeepSeek-v4.1-Flash-EXL3-2x-DGX-Sparks`, our `deepseek41-exl3`, text-only, 256K)
scored reasoning 299/302 and work 397/438 at high thinking on 2026-09-17.

## Against the adoption bar

**Independent dual-Spark runs: yes.** 27 distinct issue/PR authors in three days,
and NVIDIA forum thread
[/t/386125](https://forums.developer.nvidia.com/t/deepseek-v4-1-flash-1017-exl3-2-9bpw-on-2x-dgx-spark-with-tensorfold-57-tok-s-text-92-tok-s-code-2-1-2-3x-the-vllm-kit/386125)
(107 posts, 24 posters). That thread is mostly about sibling 1017 recipes on the
same engine lineage (Elevatormusic's Python-engine recipe, 0rand's fork, jayleaton's
Zig recipe with a 2.8 bpw quant), not Mia's. Its heaviest user rates the model "a
similar level of intelligence to GLM at nearly double the speed". Tool-eval-bench
results posted there are 90-94/100.

**Multiple streams: yes.** Four streams are the default. One user (issue #36) runs
four coding-agent streams for a team. `PARALLEL=8` with a larger `ROUND_ROWS` failed
(#23; the recipe now refuses that setting).

**More than 1M context: no.** The window is configured for 1M but tested only to
~480K, and memory sets the real limit:

- The engine has no run-time memory limit of its own; `memguard` (kill below 2.5 GiB
  for 4 s, or below 1 GiB at once) is the only brake. The 12.2 GiB reserve only shapes
  what is allocated at load (#4).
- The head's free memory falls as a conversation grows. Mia's measurements: 6.5 GiB
  after the load, 4.9 at a 159K history, 4.2 at 261K, 3.3 during a 120K cold prompt
  beside a decoding stream.
- Mia's README: "a 512K window is the practical limit for a head that carries ~6 GiB
  of other software". Rank 0 was killed at a 464K history with `CONTEXT=655360`
  (#17) and at a 265K cache-hit turn under the old 4 GiB floor (#4).
- Two users of sibling recipes report ~600K sessions; one of them runs a build that
  moves the KV cache to display memory and restarts itself after crashes. Nobody
  reports a 1M prompt.

**Our head would land in the same regime.** spark0 had 116.0 GiB available before
GLM's load on 2026-10-01 (worker 117.8; `memory.jsonl` in the 2026-10-01 GLM results).
Mia's head showed ~117 GiB before the load and ~6.5-7 GiB after.

## Open problems at survey time

| Issue | State | What |
|---|---|---|
| [#36](https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-1017-2x-DGX-Sparks/issues/36) | open | rank 0 segfault in cuBLASLt, 4 agent streams, 100-130K prompts, once in an hour of team use; cause unproven |
| [#34](https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-1017-2x-DGX-Sparks/issues/34) | open | multi-agent harness: one sub-agent's tool call stalls every other stream; harness vs engine not yet separated |
| [#18](https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-1017-2x-DGX-Sparks/issues/18) | open | with `PREFILL_INTERLEAVE_MS=250` and several long prompts queued, no request gets a first token |
| [#16](https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-1017-2x-DGX-Sparks/issues/16), [#27](https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-1017-2x-DGX-Sparks/issues/27) | open | prompt-cache placement drops prefixes an agent still needs |
| [#21](https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-1017-2x-DGX-Sparks/issues/21) | open | control-token spellings in request text become control tokens |
| [#33](https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-1017-2x-DGX-Sparks/issues/33), [#37](https://github.com/MiaAI-Lab/DeepSeek-v4.1-Flash-1017-2x-DGX-Sparks/issues/37) | closed (documented) | `reasoning_effort: max` loops for 40K+ tokens with no tool call; README advises `high` |

Across the forum thread, out-of-memory kills and CUDA-graph-capture failures with
four sessions are the common complaint for the whole recipe family.

## What a trial would cost

- **Downloads:** ~400 GB on spark0 (checkpoint 196 GiB + Engram ~203 GB). spark0 holds
  no 1017 files (only pre-1017 DeepSeek checkpoints), and the README says the older
  release's Engram tables must not be used.
- **Disk:** head ~505 GB plus ~25 GB image; worker ~310 GB plus image (both include
  a ~106 GB rank weight file). Free at survey time: 1.1 TB on spark0,
  1.4 TB on spark1.
- **NFS:** the worker reads the checkpoint from the head over NFS. spark0 does not have
  `nfs-kernel-server` (installing it needs sudo); `nfs-common` is on both boxes. The
  README also documents a local-copy mode (`PREPARE=0`, more manual).
- **Downtime:** it cannot run beside GLM (~104 GiB a box each). At survey time the
  GPUs were also on loan to ComfyUI (since 2026-10-17 18:58).
- **Settings, if tried:** `CONTEXT=524288`, leave `MIN_AVAIL_GIB` and the 12.2 GiB
  reserve alone, `reasoning_effort` at most `high`, and register it in llmctl the way
  the GLM recipe is.

## When to look again

Worth a 512K trial (GLM as the fallback) once **all three** hold:

1. someone reports a clean 1M-token prompt on a two-Spark head with other services running;
2. #36 and #34 are closed with a cause;
3. the engine pin stops moving daily, or gains a run-time memory floor (the
   recipe's slower `ENGINE=jl` option already has admission floors).

## Other Mia DeepSeek recipes

- `DeepSeek-v4-Flash-DSpark-2x-DGX-Spark`: DeepSeek V4 Flash 0731, the older popular
  recipe (1,476 stars).
- `DeepSeek-v4.1-Flash-EXL3-2x-DGX-Sparks`: pre-1017 V4.1, our `deepseek41-exl3`
  trial of 2026-09-17.
- `DeepSeek-v4.1-Flash-DGX-Sparks`: V4.1 on 3-4 Sparks (needs more hardware than we have).
