# Publication validation — 2026-11-11

Performed on Spark0, without stopping or reserving GPUs for this documentation task:

- Read-only ASUS probe confirmed two RTX3090 GPUs with24576MiB each, only approximately1GiB free on either device at probe time. No ASUS audio install or generation was performed.
- All seven `.py` snapshots were byte-compared with the scripts in the working native checkout and compiled for syntax.
- Relative links in the handoff and reference README resolved.
- The published `synthesize_gong_bubbles.py` snapshot was imported and executed into a fresh temporary directory using the native environment's Python/NumPy and system FFmpeg.
- Its six-second stereo WAV render was finite, non-silent and below full scale.
- Independent gong/bubble WAV stems summed to the mixed WAV within1e-6 floating-point amplitude tolerance after PCM decode.
- The bubble stem remained silent before the programmed0.65-second onset.
- All synthesized MP3 outputs decoded successfully.
- Reusing the synthesis output directory raised `FileExistsError` as intended.
- Existing generation manifests contained eight successful chapter-bumper takes and two successful combined gong/bubble takes, with source files present.
- Existing ZIP archives passed CRC validation.
- `git diff --check` passed before commit.

Original GPU generation was already exercised in the experiments described in the handoff; this publication did not repeat inference. No claims of new ASUS generation, listening-based source classification, warmed benchmarking or full application test-suite coverage are made.
