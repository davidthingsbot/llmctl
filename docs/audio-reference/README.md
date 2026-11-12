# Audio experiment reference scripts

These are **experimental reference snapshots**, not a production audio service.
Start with [the implementation handoff](../local-audio-implementation-handoff.md).

- Source checkout: `/home/david/work/ace-step-standalone` on Spark0.
- Upstream runtime commit: `ca1e85fe9430179831e6bc6be790c332190a3866`.
- Snapshot date: 2026-11-11.
- Native AI examples must live beside the upstream `checkpoints/` directory, in the pinned native checkout; running them from this documentation folder uses the wrong project root.
- `synthesize_gong_bubbles.py` is standalone CPU synthesis, requiring NumPy and FFmpeg, no Torch/ACE-Step imports.
- Inspect existing files before copying snapshots over them. Use fresh output folders.
- Spark model/metadata paths, batch cardinality and packaging directory assumptions are deliberately retained; see the handoff before adapting to ASUS.
- Per-take requests/manifests are authoritative; the reused wrapper's outer request/result describe the demo/last take rather than the batch.
- Source model weights, environment, audio binaries and credentials are not included.

The AI scripts generated the delivered examples on Spark. The synthesis and packaging scripts were exercised on real audio. ASUS GPU execution remains unvalidated. Documentation publication does not register any new service, alter LLMCTL policy or stop workloads.
