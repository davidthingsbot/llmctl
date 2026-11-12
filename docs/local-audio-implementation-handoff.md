# Local music, chapter bumpers and sound design — implementation handoff

Recorded 2026-11-11. Audience: the agent implementing a local audio-generation feature.

## Decision and evidence boundary

Use two complementary engines behind one job interface:

1. **Native standalone ACE-Step 1.5 XL Turbo** for songs, musical fragments, stings, and exploratory combined sound textures. Run locally on a CUDA GPU; ComfyUI is optional, not a requirement.
2. **Procedural synthesis plus a timeline mixer** for individually controlled tones, impacts, bubble-like plops, fades and exact timing. The demonstrated synthesizer runs on CPU; do not reserve a GPU for this route.

Both routes have produced real audio on Spark0. David responded positively to the bumper experiments and the gong/bubbles comparison and requested this handoff. That is useful listener feedback, not a blind quality benchmark or proof of realistic water acoustics. No ACE-Step generation has been validated on ASUS in this work; ASUS guidance below is an implementation/test plan, not a completed port.

The scripts in [audio-reference](audio-reference/) are snapshots of working experiment scripts, **not a production service or generic safe API**. They retain their local assumptions, fixed seeds and some hardcoded paths. Copy them into the native checkout before use as described below. Do not execute arbitrary submitted Python or expose script paths as public API arguments.

## What sounds we can make, and by which method

### Demonstrated with ACE-Step

- **Full vocal music:** an original 60-second dark post-punk song, requested female lead, lyrics, melodic bass, guitars and tom/snare percussion. Earlier ComfyUI work also produced longer songs. Transcription can help check recognizable lyrics, but cannot establish the same singer or musical quality.
- **Dark post-punk chapter sting:** a requested low-tom attack, descending three-note bass motif and metallic chorus-treated guitar chord.
- **Soft chapter divider:** requested felt-piano notes and a soft bell overtone.
- **Dramatic reveal:** requested reverse-cymbal swell, deep impact and dissonant string accent.
- **Gothic transition:** requested floor-tom accent, wiry bass phrase and angular shimmering guitar.
- **Combined soft gong and bubbles:** a single sound-design prompt describing the gong first and gentle bubbling beneath its decay, generated twice with different seeds.

These are the requested sound identities of successful generation jobs, not separately verified acoustic inventories. We generated, decoded and delivered them for listening. There was no automated perceptual verification that every requested instrument/event appeared.

### Demonstrated with procedural synthesis

- **Soft gong-like hit:** eight inharmonic resonances, a short softened excitation, slight beating and stereo delayed reflections, with a decaying tail.
- **Bubble-like plops:** short damped upward-bending chirps at different frequencies, amplitudes and stereo positions. These are modeled approximations, not recordings of real water.
- **Layered gong plus bubbles:** separate editable gong and bubble WAV/MP3 stems plus a mix. First bubble at 0.65 seconds; subsequent events at 0.94, 1.32, 1.76, 2.03, 2.57 and 3.02 seconds. Final render is 6 seconds. Stem addition was verified against the mixed WAV within PCM rounding tolerance.

### Extensions, not yet demonstrated here

The same synthesis/mixing approach can implement simple sine tones, chimes, noise sweeps, clicks, soft thumps and combinations. Treat each new voice as unvalidated until rendered and auditioned. For a specific real door, engine, animal or fluid sound, prefer a suitably licensed recording or evaluate a dedicated sound-effects model. Do not sell ACE-Step as an exact physical-event generator. No cloud audio service is needed for either demonstrated route.

## Prompting: sound event, not full song

Useful dimensions:

- **Source/material:** bronze gong, felt piano, glass bell, floor tom, electric bass.
- **Attack:** softly struck, muted, brushed, sharp, swelling, reversed.
- **Pitch/texture:** warm low resonance, hollow plops, tiny bright pops, metallic shimmer.
- **Sequence:** attack first, a short motif next, bubbles underneath the decay.
- **Space:** close/dry, stereo width, modest room reflections, long reverberation.
- **Ending:** one isolated event, decisive final chord, natural decay to silence.
- **Exclusions:** no vocals, no continuous groove, no loop, no full-song arrangement.

The sequence is a prompt suggestion; it is NOT a sample-accurate timeline. An instruction such as “start bubbles exactly 0.65 seconds later” should be implemented by the mixer. Negative instructions and instrumental mode reduce unwanted material but are not guarantees.

### Exact combined gong/bubbles prompt used

> A sparse peaceful audio transition, isolated sound-design sting. One softly struck small bronze gong, warm and rounded, with a gentle shimmering decay. As the gong fades, a few distinct water bubbles rise and pop softly underneath it. Close delicate hollow bubbling, not running water or ocean waves. Gong begins immediately, bubbles follow, then everything decays into silence. No melody, no drums, no vocals, no continuous accompaniment, no repeating rhythmic loop. One brief event.

See `generate_bumpers.py` for the exact four chapter-sting prompts and `generate_gong_bubbles.py` for this prompt. Set `instrumental=True`, `lyrics='[Instrumental]'`; use seeds and retain the full serialized parameters. The examples use eight diffusion steps, CFG 1, shift 3 and the existing BF16 XL Turbo model, with music-code planning enabled.

### Duration and editorial honesty

The installed upstream constants specify `DURATION_MIN=10`. We generated 10-second sources, then made four-second bumper edits and six-second gong/bubble edits. This does not establish that every API enforces that limit, nor that shorter native outputs cannot be researched later.

`edit_bumpers.py` detects an early energy onset and takes four seconds, applies short entry/exit fades and peak adjustment. `package_gong_comparison.py` takes the first six seconds and fades the ending. These are automated auditions, not selections made by ear. **A smooth editorial fade is not proof that the model composed a naturally resolved short cue.** Keep original sources and allow users to move the edit region.

For a related chapter-cue family, preserve the instruments/motif/key in the brief and vary intensity or ending. Seeds alone do not guarantee the same musical identity. Generate multiple takes and let a listener choose.

## Native installation and model layout

Verified checkout on Spark0:

- `/home/david/work/ace-step-standalone`
- Upstream: https://github.com/ace-step/ACE-Step-1.5
- Tested commit: `ca1e85fe9430179831e6bc6be790c332190a3866`
- Isolated Python 3.12 environment; install with `uv sync --frozen --python 3.12 --no-dev`.
- Tested Torch `2.10.0+cu130`; native CUDA BF16 matrix multiplication and actual end-to-end generation passed.
- ACE-Step handler: `config_path='acestep-v15-xl-turbo'`, CUDA, no compilation, no FlashAttention requirement, no quantization, no CPU offload on Spark.
- Planner: `acestep-5Hz-lm-4B`, `backend='pt'`, CUDA, BF16, no CPU offload.
- Text encoder: `Qwen3-Embedding-0.6B`; native Oobleck VAE.

Do not upgrade or replace ComfyUI's dependencies. Standalone has its own venv. No ComfyUI server, graph, node imports or API calls are involved in the standalone run.

### Existing weights and the VAE compatibility trap

The local staging script reuses these source files by symlink without modifying them:

- `ComfyUI/models/diffusion_models/acestep_v1.5_xl_turbo_bf16.safetensors`
- `ComfyUI/models/text_encoders/qwen_0.6b_ace15.safetensors`
- `ComfyUI/models/text_encoders/qwen_4b_ace15.safetensors`

Standalone metadata/tokenizer sources are `ACE-Step/Ace-Step1.5`, `ACE-Step/acestep-v15-xl-turbo` and `ACE-Step/acestep-5Hz-lm-4B` on Hugging Face. The reuse script checks DiT/planner key coverage against official shard indices; key coverage is not a complete numerical equivalence check.

**Do not directly reuse the ComfyUI VAE file.** It has different tensor key namespaces; the first run failed on this mismatch. Download native `ACE-Step/Ace-Step1.5` file `vae/diffusion_pytorch_model.safetensors` instead. The existing source VAE was untouched; the failed output was retained.

`stage_existing_weights.py` is a local one-time recipe: absolute paths, moving upstream `main` metadata, direct writes, no general download-resume support. Do not run it unmodified on ASUS. For a durable installer, parameterize roots, resolve and record HF revisions, download atomically, verify checksums and key/shape compatibility, and preserve shared caches. Check upstream/model licensing at the exact revisions being distributed; do not silently bundle model weights in this repository.

The demo overrides `model_downloader.MAIN_MODEL_COMPONENTS` to the four actually selected components, avoiding unnecessary default 2B/1.7B downloads. This is pinned-version glue, not a permanent upstream API contract. Generation sets `HF_HUB_OFFLINE=1`, so finish staging before launching.

Torch logs a GB10 capability warning and a Torchao extension mismatch. Real CUDA execution succeeded without quantization/Torchao kernels; warnings were not fixed or hidden. Do not infer another CUDA wheel is compatible solely because import succeeds.

## Running on Spark GPU — tested route

Spark's CPU/GPU share unified memory. Run the heavy model on **one Spark**, not distributed across two: this setup does not require tensor parallelism or the GLM cluster. Stop competing large-model workloads using LLMCTL.

1. Record currently active models, companion services, boot enablement and any existing lend state.
2. Use `llmctl lend 'local audio generation'` and then read `llmctl list`, service state and memory availability.
3. **Known trap:** a stale LENT record existed while GLM was actually active. In this state `lend` says already lent and does not stop GLM. We explicitly used `llmctl down glm53-tensorfold` and confirmed memory was released. Do not delete somebody else's lend record or infer memory is free from a label.
4. ComfyUI lending auto-starts have already been disabled locally (`LEND=0`, empty `LEND_UNITS`). Preserve that policy; don't start unused GPU borrowers.
5. Start the generation job, wait for a terminal result, then confirm the worker exited so models are released.
6. Restore only the model/services that were running before the job. Prefer `STATS=0 llmctl reclaim` when the saved lend record correctly describes this job. It may repoint agents/restart gateways; treat that as an operational side effect, not an invisible cleanup.

The demo's host-memory guard requires more than 40 GiB available before loading and aborts if sampled available memory falls below 8 GiB. These are conservative local policy values, not ACE-Step hardware minima. A production worker must have device-specific guards as well.

`llmctl down` removes model boot enablement. During these experiments we restored the previously enabled GLM unit with `systemctl --user enable llm-glm53-tensorfold.service` and started it without repointing chat agents; readback showed enabled/active/running. This does **not** clear the pre-existing stale lend state and does not prove inference readiness. A production lease implementation must reconcile state and require an actual completion before reporting full restoration, not merely service state or `/health`.

### Measured Spark memory and time (not general benchmarks)

- Eight 10-second cues, two fixed seeds per style, loaded once: Torch peak allocated about 27.52 GiB, reserved 27.63 GiB; sampled system-available memory dropped about 31.69 GiB; total handler/generation job about 312.32 seconds.
- Two combined gong/bubble takes, same loading strategy: allocated 27.52 GiB, reserved 27.64 GiB; available-memory drop about 31.73 GiB; total about 291.24 seconds.
- Original 60-second vocal demo: generation about 36.37 seconds, total about 297.09 seconds including cold initialization.

These are single observed workloads with retained receipts, not warmed repeated throughput tests. All use one-at-a-time generation, eight diffusion steps, and the 4B planner; they are not directly comparable to another model or host. CUDA allocation/RSS/system-available counters overlap or include unrelated activity: **do not add them together**. Earlier approximately 19 GB of loaded weights was not peak execution memory.

## Using ASUS GPU — supported plan, not yet generation-tested

“ASUS” here means **DW-ASUS-LINUX**, not the separate ASUS-ROG-LINUX laptop. Inventory records dual RTX 3090 cards (24 GiB each), about 62 GiB host RAM. A read-only SSH probe during this handoff confirmed two RTX 3090s, each with 24576 MiB total and only about 1 GiB free at that moment. **Both GPUs were busy; no model was stopped and no audio environment was installed on ASUS.**

Two 24 GiB cards are **not automatically one 48 GiB CUDA device**. The unoffloaded Spark run allocated over 27 GiB, so do not copy the all-resident script to a single 3090 and promise it fits. `CUDA_VISIBLE_DEVICES=0,1` alone does not distribute the native handlers. This work has not tested cross-GPU sharding of ACE-Step.

### ASUS implementation sequence

1. Probe `nvidia-smi` for free memory and active processes; inspect that host's `llmctl list/services`. Obtain scope for interrupting its workloads; only a read-only probe was authorized by this documentation task.
2. Use the **ASUS host's** LLMCTL to lend/release its GPUs when a generation job is actually requested. Stop foreign GPU workloads only through their owner/lifecycle mechanism. Do not touch the Spark's GLM to free an ASUS GPU.
3. Install an isolated pinned native checkout and compatible Python3.12/CUDA PyTorch environment on ASUS. Use native checkpoints or parameterized copies; Spark-local symlinks are not portable. Do not copy the ARM64 venv to x86_64: rebuild from the lock and validate platform dependencies.
4. Choose one free card explicitly, e.g. `CUDA_VISIBLE_DEVICES=1`. Inside that process it is `cuda:0`. Test a real BF16 matmul and report physical/logical mapping.
5. Start with **serial stages/CPU offload** rather than the all-resident Spark configuration. At the tested upstream revision, `AceStepHandler.initialize_service` exposes `offload_to_cpu=True` and `offload_dit_to_cpu=True`. Planner initialization has its own `offload_to_cpu` option; validate actual live allocations during planning and diffusion, rather than assume toggling it guarantees sufficient free VRAM.
6. For short instrumental sound experiments, a lower-memory candidate is skipping the planner: do not initialize its 4B weights, pass an uninitialized `LLMHandler`, and set `thinking=False`, `use_cot_metas=False`, `use_cot_caption=False`, `use_cot_language=False`. The inspected inference gate only uses the planner when requested **and** initialized. This changes the generation path/quality and is **not yet tested here**. Merely disabling thinking after loading the planner wastes its residency.
7. Batch size 1, duration 10 seconds, eight steps; monitor per-device allocated/reserved peaks and host RAM. Add a real discrete-VRAM admission check: the current Spark demo's `MemAvailable` check alone cannot prevent an ASUS CUDA OOM.
8. If it still does not fit, reduce model size via a separately staged supported checkpoint or evaluate upstream quantization/offload options. Do not install arbitrary quantization packages into an existing environment or claim quality equivalence. Preserve failed runs and any successful alternate configurations separately.
9. Verify actual output and record settings, durations, memory, GPU/driver/Torch versions and wall time. Restore ASUS workloads and boot enablement exactly as recorded before declaring success.

CPU synthesis needs no LLMCTL interruption and can already run on ASUS using Python, NumPy and FFmpeg. It does not benefit from reserving both 3090s. The synthesis script has no hardcoded Spark root, unlike some AI experiment scripts.

## Reference scripts and reproduction

Repo directory: `docs/audio-reference/`. Copy these scripts into a pinned native checkout; `generate_demo.py` deliberately treats its own parent as the ACE-Step project root, so running it directly in this documentation directory would look for checkpoints in the wrong place.

```sh
# On the existing Spark installation; no downloads or dependency upgrades implied:
cp /home/david/work/llmctl/docs/audio-reference/*.py /home/david/work/ace-step-standalone/
cd /home/david/work/ace-step-standalone
.venv/bin/python generate_bumpers.py
# Then pass the exact printed output directory:
.venv/bin/python edit_bumpers.py output/chapter-bumpers-YYYYMMDDTHHMMSS

.venv/bin/python generate_gong_bubbles.py
# CPU-only; choose a NEW directory; no ACE model imports:
.venv/bin/python synthesize_gong_bubbles.py output/gong-bubbles-layered-01
# This packager currently expects that exact sibling synthesis directory:
.venv/bin/python package_gong_comparison.py output/gong-bubbles-YYYYMMDDTHHMMSS
```

Do not rerun the examples into existing directories. Copying is for deliberate reinstatement from this snapshot; inspect local modifications before overwriting any script. The current synthesizer/packager have a fixed 6-second comparison, and the bumper editor expects eight successful inputs. Parameterize these constraints before turning them into a service. The batch runner's root `request.json` comes from the original vocal demo wrapper; **per-take request.json files are authoritative**, not that outer request. Its root result similarly describes the last take; `manifest.json` covers every take.

Reference files:

- `generate_demo.py`: native loading, offline environment, original vocal example, memory monitoring.
- `stage_existing_weights.py`: local metadata/weight reuse recipe; VAE exception.
- `generate_bumpers.py`: four briefs, two seeds each, one initialization.
- `edit_bumpers.py`: source validation, onset alignment, 4s edits, montage and ZIP.
- `generate_gong_bubbles.py`: combined-prompt two-take experiment.
- `synthesize_gong_bubbles.py`: deterministic modal gong, bubble events, stems and mix.
- `package_gong_comparison.py`: 6s A1/A2/B comparison and archive verification.

### Existing local deliverables

All paths below are on Spark0 under `/home/david/work/ace-step-standalone/output/`:

- `signal-in-the-stairwell/Signal-in-the-Stairwell.mp3` — original vocal demo.
- `chapter-bumpers-20261111T171057/Chapter-Bumpers-8-Takes.mp3` — eight four-second edits.
- `chapter-bumpers-20261111T171057/Chapter-Bumpers-Sources-and-Edits.zip`.
- `gong-bubbles-20261111T172258/comparison/Gong-and-Bubbles-A1-A2-B-Comparison.mp3`.
- `gong-bubbles-20261111T172258/comparison/Gong-and-Bubbles-Sources-Stems-Prompts.zip`.
- `gong-bubbles-layered-01/` — separate synthesized stems, mix and exact event receipt.

Original requests/results/memory receipts stay beside the audio. The initial VAE failure remains under `signal-in-the-stairwell-failed-vae/`. Audio/model binaries are deliberately not checked into this source repository. Do not assume these absolute paths exist on another host; use the scripts/receipts or explicitly transfer the files.

## Implementation contract (proposed, not built)

Expose one job model with `engine=ace_step|synthesis|hybrid`, `kind=song|sting|effect`, caption, optional lyrics, instrumental flag, generation duration, final edit duration, seed(s), sound layers and a timeline. Distinguish generated duration from delivered duration. Timeline layer parameters should include start, gain, pan, attack/decay, source provenance and optional trim range. Never imply these structured fields are all native ACE-Step controls.

- Queue GPU jobs per physical device; acquire a bounded exclusive lease before model loading. Keep synthesis CPU-only unless measurement justifies otherwise.
- Separate job states: queued, waiting-for-memory, loading, generating, editing, verifying, complete, failed, cancelled. Persist errors and partial artifacts; no silent fallback from AI to synthesized audio.
- Load once for a batch, unload on idle/lease expiry. Avoid paying cold initialization for every tiny sting, but do not monopolize a GPU indefinitely.
- Preserve originals; edits are new artifacts. Return WAV/FLAC for editing plus MP3 previews, individual stems when available, and request/result metadata.
- For loudness, the examples only do simple peak adjustment/fades. A production renderer should implement a documented loudness/true-peak policy and retain gain metadata; do not call these examples loudness-matched mastering.
- Validate output paths and durations, bound event counts, reject nonfinite parameters, use argument arrays rather than shell interpolation, and do not trust user filenames or archive paths.
- Keep credentials out of audio metadata, logs and payloads. Store source/model revisions, license/provenance and content hashes separately from secrets.

### Acceptance checklist for the implementation agent

1. Reproduce a vocal song and an instrumental sting on Spark; save exact requests, seeds, model/runtime identity and actual audio.
2. Reproduce combined gong/bubbles with ACE-Step and a separately layered synthesis; let a listener judge source identity.
3. Demonstrate timeline control and show that stems reconstruct the mix. Verify no unexpected clipping/NaN/empty audio, declared duration, sample rate/channels and full decode.
4. Distinguish AI planning, diffusion, synthesis and editorial processing in metadata; preserve full sources and failures.
5. Validate admission/cancellation/worker exit, memory guards and workload restoration without unnecessary gateway changes.
6. Execute the ASUS offload or no-planner configuration before advertising ASUS generation support. Record the actual card, peak VRAM, host RAM, failures and quality limitations; no speed extrapolation from Spark.
7. Provide playable previews and editable exports. A successful process exit or non-silent waveform alone is not perceptual acceptance.

Related historical workflow: [ACE-Step ComfyUI operation](ace-step-comfyui-operation.md). Native standalone orchestration replaces ComfyUI's graph runner here, not the model's memory requirements.
