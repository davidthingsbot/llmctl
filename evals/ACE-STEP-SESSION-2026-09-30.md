# ACE-Step / ComfyUI session: 2026-09-30

Recorded 2026-10-01 PDT. Audio output modification times place the generation
experiments on September 30; this note was requested after midnight.
See [the operation guide](../docs/ace-step-comfyui-operation.md) for controls,
workflow settings, verification and limitations.

## Intent and scope

David wanted local open-source music generation, integrated into existing
ComfyUI on Spark0. Suno was excluded because it is a proprietary hosted service.
ACE-Step was chosen over the other discussed candidate, HeartMuLa.

ACE-Step XL Turbo plus the 4B music-planning model was installed using native
ComfyUI support. All four downloaded model files passed SHA-256 checks. Existing
ComfyUI, dependencies and llmctl model defaults were not replaced. This session
also produced a full video for one track; it did not install ACE as a new llmctl
inference server.

A separate TensorFold future experiment was recorded earlier at
[TENSORFOLD-FUTURE-EXPERIMENT.md](TENSORFOLD-FUTURE-EXPERIMENT.md). It remains a
future consideration, not a deployed change.

## Musical direction and user feedback

The first request was an original song with a Joy Division-style sound.
The first output was judged closer to New Order. David specified:

- References: "Isolation" and "She's Lost Control".
- Very heavy, prominent melodic bass; Peter Hook was the reference.
- Dark synth washes and strong percussion.
- Avoid bright guitars and a glossy/bright production aesthetic.
- A low, restrained gravelly voice: "A low, resonant baritone delivered like a
  solemn recitation—emotionally restrained on the surface, but with enormous
  pressure underneath."
- Later clarified: Ian Curtis quietly growled; avoid open-resonance shouting.
- Avoid 1990s vocal mannerisms throughout.

The second dark bass-led take received "Much better." The more elaborate
recitation rewrite was judged worse than its predecessor. Subsequent iterations
explored LCD Soundsystem-style pop/dance-punk craft, then intimate female narrative
pop, then Siouxsie and the Banshees gothic art-punk. The final instruction in that
sequence was less pop, multi-voice chorus, and emphatically no 1990s vibe.

These are creative references used in prompts, not assertions that the model
replicated an artist's identity or that each requested trait was actually achieved.
User listening feedback is the quality evidence; successful decoding alone is not.

## Audio artifact inventory

Base directory: `/home/david/ComfyUI/output/audio/`.
These are actual generated files, in creation order. The first four are approximately
one minute; subsequent tracks are approximately three minutes (MP3 metadata
includes a small padding allowance).

1. `ACE_Step_XL_Turbo_smoke_00001.mp3`
   - First Joy Division-directed take; user judged it more New Order.
   - Successful model/tool installation smoke test, not a stylistic success.
2. `ACE_Step_Dark_Bass_Postpunk_00001.mp3`
   - Stronger bass, dark synths and mechanical percussion.
   - User: "Much better." This was the preferred early reference.
3. `ACE_Step_Dark_Bass_Gravel_Baritone_00001.mp3`
   - Added gravel, chest resonance and solemn recitation wording.
   - User preferred the previous take.
4. `ACE_Step_Postpunk_Gravel_Retry_00001.mp3`
   - Returned to the preferred prompt/seed, modified vocal texture and excluded
     1990s grunge mannerisms/flourishes.
5. `ACE_Step_Dark_Dancepunk_3min_00001.mp3`
   - Added LCD Soundsystem-style dance-punk rhythm and pop hook; longer structure.
   - User disliked loud/open vocal resonance and requested quiet growling.
6. `ACE_Step_Dark_Quiet_Growl_3min_00001.mp3`
   - Prioritized quiet close-miked low vocal, narrow range and restrained refrains.
7. `ACE_Step_Dark_Grind_Narrative_Pop_00001.mp3`
   - Female narrative-pop vocal/songwriting over dark early-post-punk grind.
8. `ACE_Step_Dark_Grind_Banshees_00001.mp3`
   - Added gothic art-punk, commanding female delivery, rolling toms and eerie
     guitar textures. Later explicitly selected as the same-album source.
9. `ACE_Step_Austere_Group_Chorus_00001.mp3`
   - Removed pop-hook direction; requested female lead with low male group chants,
     mostly unison/octaves, with early-period dark bass/percussion.
   - Used as the soundtrack for the completed video.
10. `ACE_Step_Banshees_Album_Rooms_Without_Windows_00001.mp3`
    - New original lyrics/title, 116 BPM, D minor, source timbre conditioning.
    - Failed artistically: user reported no lyrics/voices, harsh quick loop,
      monotony. The initially reported "same-album companion" was not validated
      by listening and should not be treated as successful.
11. `ACE_Step_Banshees_Rooms_Vocal_Retry_00001.mp3`
    - Restored planning-code generation but retained timbre reference.
    - Local transcription did not recover supplied lyrics; not sent as the fix.
12. `ACE_Step_Banshees_Rooms_Text_Vocals_00001.mp3`
    - Removed experimental reference path, returned to original successful vocal
      graph/seed with new lyrics, explicit female singing and section-specific
      bass/percussion instructions.
    - Local Whisper recovered the "Rooms without windows, doors without names"
      chorus and bridge beginning "I thought the silence would get smaller."
    - File duration/decoding verified. Not yet reviewed by the user; exact singer
      matching, bass prominence and arrangement quality remain unverified.

### Compilation

`Post-Punk-Experiments-Compilation.mp3` concatenates tracks 1–9, in creation order.
It was created before the Rooms Without Windows attempts and does not contain
tracks 10–12. Runtime verified: 1140.216 seconds (about 19 minutes); file size
33,662,988 bytes. Existing MP3 audio was concatenated without additional audio
recompression, and full playback decoding was verified. Sent in Telegram.

### Lyrics / API records

Local durable records include:

- `output/audio/Rooms-Without-Windows-Lyrics.txt`
- `output/audio/Rooms-Without-Windows-Retry-Lyrics.txt`
- `tools/ace-step-banshees-album-rooms-api.json` (failed reference-conditioned take)
- `tools/ace-step-banshees-rooms-vocal-retry-api.json` (failed reference retry)
- `tools/ace-step-banshees-rooms-text-vocals-api.json` (latest vocal retry)
- `tools/ace_step_album_rooms.py`, `ace_step_rooms_retry.py`,
  `ace_step_rooms_text_vocals.py`

Paths above are relative to `/home/david/ComfyUI`. Some scripts use `/tmp` source
files; they require review before reuse. Generated MP3s embed exact API prompt
metadata, which is the more dependable source record when a helper file was
subsequently overwritten.

## Same-album failure: evidence and correction

The reference-conditioned graph added:

```text
LoadAudio(original Banshees) -> 30-second excerpt at 25 seconds
  -> VAEEncodeAudio -> ReferenceTimbreAudio -> positive conditioning
```

The first attempt disabled audio-code planning per the native encoder tooltip.
ComfyUI returned success and the MP3 decoded, but David reported it had no singing
and a harsh monotonous loop. Enabling planning while keeping the reference did
not recover recognizable supplied lyrics in the check: local Whisper returned
repeated "Thank you", which is not evidence of vocals.

The eventual recovery removed reference conditioning entirely, used the original
Banshees text graph and seed 731, kept planning enabled, and supplied a longer
lyric structure starting immediately at `[Verse 1]`. Both 90-second and full-song
transcription checks were performed. Full transcription recovered multiple exact
chorus/bridge lines but also included questionable phrases and repetition; ASR is
a sanity check, not proof of lyric-perfect singing or composition quality.

Procedural lesson: do not say "verified same singer" or "successful album track"
on the basis of ComfyUI success, non-silent audio, metadata or a timbre node.
A reference-conditioned path remains experimental on this installation.

## Full music video

David authorized stark black-and-white early-post-punk industrial imagery and
requested a consistent/persistent female lead singer where appropriate. Interim
singer and industrial-street frames were shared; user response: "Nice."

### Generation and identity approach

- Generated one fictional adult woman using Krea2 Turbo, its Qwen3VL encoder and
  Qwen-image VAE; no unrelated LoRA chain.
- Reference: angular face, short black bob with blunt fringe, dark eyeliner,
  plain black high-neck shirt, wired microphone, bare concrete rehearsal room.
- Reference image reused for every performance shot with LTX-2.5 image-to-video;
  quiet gestures and small camera motions helped avoid drift.
- Nine performance shots plus nine atmospheric industrial shots, ten seconds
  each. Environment shots used LTX-2.5 text-to-video.
- LTX distilled int8-convrot, single-stage full-resolution generation, 960×544
  at 24 fps. No model installation was required for this video phase.
- Generated audio was discarded/replaced with the actual song.
- Contact sheets checked singer continuity at 1/5/9 seconds and all-scene midpoints.
  This is inspected visual consistency, not a guarantee at every frame.
- Exact lip-sync was not implemented or claimed.

### Output and verification

Final file:
`/home/david/ComfyUI/output/austere_video/Austere-Group-Chorus-Full-Music-Video.mp4`

Verified final format: H.264, 1280×720, 24 fps; AAC 48 kHz stereo; 180 seconds;
26,448,359 bytes. 720p delivery was cropped/upscaled from 960×544 generated shots,
not native 720p generation. Each 241-frame generated clip was trimmed to ten
seconds before assembly. Opening and closing fades were applied.

Full-file decode passed. Correlation between the source song and decoded final
soundtrack was 0.999879 after AAC encoding: the intended source audio was preserved
apart from normal encoding effects. The final video was delivered in Telegram.

Local project records, all under `output/austere_video/`:

- `manifest.json`: shot descriptions, exact outputs, prompt IDs, edit order,
  final path and completion status.
- `shot01_00001_.mp4` through `shot18_00001_.mp4`: generated source clips.
- `shotNN-api.json` for later shots; first-shot graph remains `/tmp/austere-shot01-api.json`.
- `lead_reference_00001_.png`: singer reference output.
- `all-shots.jpg`, `singer-continuity.jpg`: visual QA sheets.
- `singer-interim.jpg`, `street-interim.jpg`: shared previews.
- `final-verification.json`, `render.log`, `edit/`: output checks and edit files.

Reference input: `/home/david/ComfyUI/input/austere_lead_reference.png`.
Helper scripts in `ComfyUI/tools/`: `austere_video_api.py`,
`austere_video_render.py`, `austere_video_qa.py`, `austere_video_assemble.py`.
The rendering manifest allowed progress checks and resumption. These scripts are
project-specific and some still depend on temporary files; review before starting
another project, use a new output directory and do not overwrite this completed one.

## Timing receipts

- First 60-second audio take: 27.672 seconds end-to-end ComfyUI execution.
- Three-minute dance-punk take: 45.769 seconds with models cached, about 3.9×
  faster than real time.
- First ten-second singer video shot: 147.159 seconds.

These are individual run receipts, not a controlled comparative benchmark suite.
Do not conflate cached runs with model-loading times or transfer the rates to
other resolutions, durations, conditioning graphs or concurrent workloads.

## Current conclusions / next experiments

- Native local ACE-Step XL Turbo generation works; meaningful musical adherence
  remains probabilistic and user-listening-dependent.
- Text-to-audio with planning enabled is the established vocal baseline.
- No reliable singer-identity lock or isolated-vocal replacement was established.
- Heavy bass / precise percussion are prompt intentions, not mixer/sequencer
  controls. Consider a DAW and optional imperfect stem separation for precision.
- Same-album experiments should first establish a repeatable vocal baseline,
  then vary one parameter at a time and listen to short candidates before making
  a full song. Avoid another unchecked three-minute reference-conditioned loop.
- Persistent visual singer via a fixed image reference worked well enough for
  this inspected montage; audio identity is a separate unresolved problem.

No commit or push is included in this documentation task. Large model/audio/video
artifacts remain in the local ComfyUI tree; only these notes belong in this repo.
