# ACE-Step in ComfyUI on Spark0: operation and limitations

Operational baseline established 2026-09-30; notes recorded 2026-10-01 (PDT).
See [the session record](../evals/ACE-STEP-SESSION-2026-09-30.md) for experiments,
user feedback, output files, failures and the accompanying video.

## Scope and installed baseline

This is a local music-generation workflow in an existing ComfyUI installation,
not a new llmctl model-server backend. No inference subscription is required.
No llmctl registration, GLM default change or service restart was performed for
this setup. Existing ComfyUI already had native ACE-Step nodes: no third-party
plugin, ComfyUI upgrade or dependency replacement was needed.

- Host: `dw-spark0`, NVIDIA GB10.
- Checkout: `/home/david/ComfyUI`.
- Interpreter: `/home/david/ComfyUI/.venv/bin/python`.
- Observed runtime: PyTorch `2.11.0+cu130`, CUDA available.
- Observed ComfyUI revision: `8d534945ebd53cff61e8def81757c6a6c1b9cf2d`.
- Local API/browser: `http://127.0.0.1:8188`.
- LAN browser address observed: `http://192.168.64.249:8188` (may change).
- Model repository: https://huggingface.co/Comfy-Org/ace_step_1.5_ComfyUI_files
- Repack model-card license checked: Apache-2.0.
- Upstream template: https://github.com/Comfy-Org/workflow_templates/blob/main/templates/audio_ace_step1_5_xl_turbo.json

Files under `ComfyUI/models/`, downloaded and SHA-256-verified against the model
repository's blob metadata:

- `diffusion_models/acestep_v1.5_xl_turbo_bf16.safetensors`
- `text_encoders/qwen_0.6b_ace15.safetensors`
- `text_encoders/qwen_4b_ace15.safetensors`
- `vae/ace_1.5_vae.safetensors`

The model package is approximately 20 GB. The ordinary curl download was slow;
HF Xet was not faster in this trial. Resumable parallel HTTP ranges eventually
completed. An HTTP/2 stream cancellation required a retry using HTTP/1.1.
Partial download success is not sufficient: verify size and SHA-256 before use.

## What the interface actually is

ComfyUI is a node graph, not a synthesizer, drum sequencer or multitrack DAW.
This ACE-Step workflow generates a complete stereo mix: voice, bass, drums and
other instruments together. The graph is conceptually:

```text
DualCLIPLoader -> TextEncodeAceStepAudio1.5 -> positive conditioning
                       |                  -> ConditioningZeroOut -> negative
UNETLoader -> ModelSamplingAuraFlow -> KSampler <- EmptyAceStep1.5LatentAudio
                                             |
                              VAEDecodeAudio + VAELoader -> save audio
```

Native model type for DualCLIPLoader: `ace`. The two text/audio-planning models
are the 0.6B and 4B Qwen files listed above.

### Controls available

- **Tags/style text:** genre, instruments, voice, mood, production, arrangement.
  These are probabilistic instructions, not independent mixer settings.
- **Lyrics:** supplied words with `[Verse]`, `[Chorus]`, `[Bridge]`, etc.
  `[Instrumental]` requests instrumental output. Tags are guidance, not exact
  timeline placement or a guarantee that all words will be sung.
- **BPM, key/scale, time signature, language:** explicit conditioning inputs;
  musical adherence still needs listening.
- **Duration:** set conditioning duration and latent seconds identically. The
  saved UI template connects a shared duration primitive to both.
- **Seed:** controls variation. The same seed with a changed prompt does NOT
  preserve the exact backing, arrangement, melody or singer identity.
- **Generate audio codes:** internal music-planning stage. Keep enabled for the
  proven text-to-vocal workflow. Disabling it was associated with a failed
  reference-conditioned experiment; it is not a reliable quality shortcut.
- **Planning controls:** CFG, temperature, top-p/top-k/min-p affect the internal
  code generator, not instrument levels. Distinguish this CFG from sampler CFG.
- **Sampling controls:** steps, sampler, scheduler, sampler CFG and denoise.
  They are generation parameters, not EQ, mixing or synthesizer controls.
- **Reference audio:** native timbre conditioning exists, but our same-album
  attempt failed. Do not describe it as a proven exact-singer control.

There is no separate bass/drum/vocal fader, editable MIDI, piano roll or precise
percussion sequencer in this workflow. Changing the vocal description can change
the whole song. For precise production, export to a DAW; optional stem separation
estimates parts from the stereo mix and may introduce bleed/artifacts.

## Proven initial settings

- XL Turbo BF16 model and ACE 1.5 VAE.
- 4B planning model; `generate_audio_codes=true` for text-generated vocal songs.
- KSampler: eight steps, CFG 1, Euler, simple scheduler, denoise 1.
- ModelSamplingAuraFlow shift 3.
- Planning defaults used: CFG 2, temperature 0.85, top-p 0.9, top-k 0, min-p 0.
- Batch one. Tested durations: 60 and 180 seconds. One minute was a quick-test
  choice, not a maximum duration. Longer model claims have not been tested here.

Do not assume changing steps/CFG improves Turbo output; start with the established
settings and compare one variable at a time.

## Using the saved workflows

1. Open Spark0 ComfyUI and refresh if new files are not visible.
2. Open a saved workflow from `user/default/workflows/`.
3. Edit the tags and lyrics in `TextEncodeAceStepAudio1.5`.
4. Set BPM/key/language and the connected duration primitive.
5. Set the shared seed, queue one take, then listen before iterating.
6. Play/download from the save node; output files are in `output/audio/`.

Relevant saved workflows include:

- `ACE-Step XL Turbo - Spark0.json`
- `ACE-Step Dark Bass Postpunk.json`
- `ACE-Step Dark Bass Gravel Baritone.json`
- `ACE-Step Postpunk Gravel Retry.json`
- `ACE-Step Dark Dancepunk - 3 minutes.json`
- `ACE-Step Dark Quiet Growl - 3 minutes.json`
- `ACE-Step Dark Grind Narrative Pop.json`
- `ACE-Step Dark Grind Banshees.json`
- `ACE-Step Austere Group Chorus.json`

Latest vocal album-companion API graph:
`/home/david/ComfyUI/tools/ace-step-banshees-rooms-text-vocals-api.json`.
This latest retry was generated through the API, not installed as a new saved
UI workflow. API JSON is not the same format as a draggable UI workflow.

## Verification: file success is not musical success

Before queuing, inspect the live queue and unified memory. ComfyUI may unload
other cached models to make room. Do not restart it or disturb other jobs just
to install music weights. Current telemetry is transient, not a capacity promise.

```sh
curl -fsS http://127.0.0.1:8188/queue
free -h
```

After submission, read `/history/<exact prompt_id>`, require successful execution
and use the exact returned output filename. SaveAudioMP3 returned names ending
in `_00001.mp3`, not `_00001_.mp3`.

Check format/duration and decode the entire file:

```sh
ffprobe -v error -show_entries format=duration:stream=sample_rate,channels \
  -of json /absolute/path/to/song.mp3
ffmpeg -v error -nostdin -i /absolute/path/to/song.mp3 -f null -
```

These checks establish a valid audio artifact, not audible vocals, good bass,
arrangement variety or the requested artistic style. Listen before declaring
musical success. Local transcription can add evidence that lyrics are present:

```sh
ffmpeg -v error -nostdin -y -i /absolute/path/to/song.mp3 \
  -ac 1 -ar 16000 /tmp/ace-vocal-check.wav
curl -fsS --max-time 180 \
  -F file=@/tmp/ace-vocal-check.wav -F response_format=json -F language=en \
  http://127.0.0.1:19450/v1/audio/transcriptions
```

The endpoint was the existing local whisper-server. Check recognizable supplied
lyrics, not merely nonempty text: failed material produced repeated "Thank you"
hallucinations. Whisper can miss sung lines, invent words or repeat phrases; it
cannot establish vocal identity or perceptual quality.

## Reproducing a specific take

MP3 output embeds the exact ComfyUI API prompt, and often its UI workflow, in
metadata. This is preferable to reusing mutable scratch/API files, some of which
were overwritten during iteration.

```sh
ffprobe -v error -show_entries format_tags=prompt,workflow -of json \
  /absolute/path/to/source.mp3
```

Recover that source graph, preserve the original, change only intentional
settings, and save a new graph/output name. Some helper scripts still depend on
`/tmp` files: review and make those dependencies durable before later reuse.

## Important failed path and recovery

`LoadAudio -> TrimAudioDuration -> VAEEncodeAudio -> ReferenceTimbreAudio`
conditioned the same-album attempts on a 30-second source excerpt. The first
attempt disabled planning codes following the native tooltip; the next enabled
them. Neither produced a reliably recognizable vocal song in our checks.
User feedback on the first: no voices/lyrics, harsh short loop, monotonous.
Do not promote this graph as verified merely because ComfyUI returned success.

Recovery used the original Banshees text-to-audio graph and seed, removed all
reference conditioning, enabled planning codes, supplied substantial new lyrics
starting with `[Verse 1]`, and asked for bass/percussion variation by section.
Local Whisper recovered the new chorus and bridge. Same-singer identity and
musical quality remain unverified; the user has not yet reviewed that final retry.

## Performance observations, not a benchmark suite

End-to-end ComfyUI execution, including generation/decoding/saving:

- First 60-second vocal take: 27.672 seconds.
- Three-minute dance-punk take: 45.769 seconds with models cached, approximately
  3.9 times faster than real time.

These are individual receipts, not cold-start timings, matched benchmarks or
promises for all prompts/workloads. Output was 48 kHz stereo MP3.
