# GLM TensorFold dual-Spark operation

## Recipe v1.3.2 update (2026-10-02)

Fast-forwarded the live recipe from `978b2252` (v1.3) to `92bf731c` (the v1.3.2
merge), local `scripts/local.sh` untouched, rollback copy at
`~/.cache/llmctl-rollback/tensorfold-v132-20261002T133539/recipe`. The four
upstream commits after v1.3.2 (Spark-twin PCIe rails, host-name WORKER/FABRIC_PEER,
end-of-turn probe) were deliberately not taken. Image digest and both weight
revisions are unchanged, so no pull or rebuild happened; `prepare.sh` now compares
images by content and follows xet blob links, neither of which engaged here.

What changed at runtime, both ranks: `TF_GLM_MULTI_LONE` 1 -> 0 (v1.3.1, issues
#12/#13) and `TF_GLM_CACHE_ENTRIES` 8 -> 32 (v1.3.2, issue #17). Service restart
to healthy took 153 s. The KV pool shrank from 1939456 to 1867776 tokens, the
~1 GiB the 24 extra kept-prompt states reserve.

Measured with `evals/diagnostics/tensorfold_prompt_cache_probe.py` (three
conversations taking turns, ~4.5k tokens of distinct history each, six warm
rounds, thinking off, `cached_tokens_total` vs `prompt_tokens_total` from the
frontend's `/health`):

| run | warm prompt tokens | served from cache | wall for 18 turns |
|---|---|---|---|
| before (v1.3 defaults) | 108738 | 0 (0.0%) | 66.4 s |
| after (v1.3.2 defaults) | 108738 | 107712 (99.1%) | 8.7 s |

All 18 answers were correct in both runs. The same seven-check battery as the
v1.3 update (`evals/diagnostics/verify_tensorfold_v132.py`, receipts under
`evals/results/dw-spark0/glm53-tensorfold-v132-update/`) passed: default-thinking
text, typed tool call and roundtrip, malformed-history recovery, five-image
vision, four simultaneous short requests, streamed token-limit tool boundary.
Hermes gateway stayed active on the same port and key; Open WebUI's configured
backend answered over the LAN address; both memory guards active. The stale
`llmctl lend` state from 2026-09-28 (which named the parked `glm53-exl3`) was
removed first so llmctl manages the model again. Not repeated: the quality
suites and the 897K retrieval run.

## Recipe v1.3 update (2026-10-01)

Updated the live recipe from `ed026ef` to
`978b2252059069b3b4b84f0f7eeb73bc17f28d3f`, fast-forward only, preserving local
settings. TensorFold is now v0.6.0 with 53 patches (`ae8d1c789b47`). Published
registry manifest pin is
`sha256:22789f0cb3dc308f0b2ce52a33961b88bd624af1725e91e8aba0a74a671bb969`;
the actual running image ID on both nodes is
`sha256:0266e5767a4fb7cba90e587c6f69ab59dea24a0cd08ea983d333295717e9bf24`.
Manifest digests and image configuration IDs are different identifiers.
Checkpoint and draft pins are unchanged; preparation reused existing weights.
Rollback recipe copy is at
`~/.cache/llmctl-rollback/tensorfold-v13-20261001T110449/recipe`.

Retained 18 GiB reserve, 8 GiB KV cap, 1048576 context, four streams, both guards,
Restart=no, authenticated port 8005, loopback backend 18888 and existing browser
URLs/routing. Did not adopt the upstream larger 12.5 GiB KV cap or optional NFS.
The new default reply ceiling is 32768 tokens when clients omit their own limit.
Frontend body cap now matches the recipe's 96 MiB cap; a new regression failed
at the previous 64 MiB cap and passed after the adjustment.

Runtime update improves tool-history recovery, withholds incomplete tool calls,
adds up to 50 images/four videos per request, pins the published image by digest,
and separates kernel caches by image. These limits are upstream capabilities;
the local five-image smoke does not qualify every advertised media limit.
`tools/bench.py` was removed upstream in favour of sparkDash. Earlier repository
benchmark receipts remain historical and should not be rerun via that deleted
path. No speed/quality improvement is claimed by this operational update.

Post-update real smoke checks passed: default-thinking text, typed-array tool
arguments and tool roundtrip, malformed non-object tool history recovery,
five-image color recognition, four simultaneous short requests, and a streamed
token-limit tool request ending with `length` without malformed tool arguments.
Open WebUI's actual configured backend connection returned
`Updated browser connection verified.`. Both service/guard startup enablement
and active state were checked. Observed available memory afterward was
12.73 GiB head / 15.70 GiB worker. Full quality and 897K retrieval suites were not
repeated. Root tests: 35 run, three skipped, no failures.
Raw update receipts and logs: `evals/results/dw-spark0/glm53-tensorfold-v13-update/`.
The verification runner is `evals/diagnostics/verify_tensorfold_v13.py`.
Deployment/update files remain local pending separate commit/push authorization.

## Initial promotion receipt

Promoted on 2026-10-01 after the recorded trial. This is a deployment receipt,
not an additional quality evaluation. Evaluation commit: `9c059c1`.

## Browser and API

- Open WebUI: `http://192.168.64.249:8088` (LAN), or
  `http://100.81.23.81:8088` (Tailscale). Existing login applies.
- Select `GLM-5.3-Flash-EXL3`. The model name is unchanged, but backend ownership
  returned by `/v1/models` is now `tensorfold`.
- Authenticated consumer API: `http://127.0.0.1:8005/v1`; browser container uses
  `http://192.168.64.249:8005/v1`. Existing protected API keyfile is retained.
- Native engine: loopback-only `127.0.0.1:18888`, not an exposed chat UI.
- API frontend authenticates all routes except `/health`, strips credentials
  upstream, forwards SSE, and enables handler cancellation on client disconnect.
- Plain HTTP is intended for these existing private network connections, not
  exposure to the public Internet. No credential values are stored in this note.

## Runtime identity and limits

Recipe `/home/david/work/glm53-tensorfold` at
`ed026ef92d1650120dada1294a112acb6c8f2f48`.
Both ranks use image
`sha256:67e82cade069474645782275e2bec5326e91fa0a886831adab8d490f41bbff3f`.
Target revision `9eaebb7c4e96d983dcd538e18624622ba5b820a8`, draft revision
`bf582e4eacc1810f76656d1811693ff6c6737d2a`.
Thinking and vision enabled; four streams, 1048576-token prompt/reply window,
FP8 KV, q4 dense, 18 GiB memory reserve, 8 GiB KV cap. Reloaded shared pool:
2207744 tokens. This does not guarantee four simultaneous full-window requests.
DFlash2 has a non-commercial-only licence restriction. Quality caveats remain
in the trial analysis, including the vision regression and strict-format failure.

## Lifetime and safety

- Primary: `llm-glm53-tensorfold.service`, active and enabled for user startup,
  `Restart=no`. `glm53-tensorfold-memguard.service` is active and enabled on
  both nodes. User lingering was already enabled on both.
- Hardened guard source is installed at `/home/david/ops/tensorfold_memguard.py`
  on both nodes, with a 5 GiB floor, retry and verified-stop semantics. The old
  transient trial guards were replaced after persistent guards became active.
- Consumer routing stays on port 8005, so existing WebUI and Hermes URLs/keys
  needed no retargeting or gateway restart. Hermes `model.context_length` was set
  through its CLI to 1048576 and read back. This remote conversation's provider
  override was not changed.
- Adapter is `scripts/glm53-tensorfold-tp2.sh`; frontend is
  `scripts/tensorfold_frontend.py`, using dedicated
  `/home/david/.venvs/tensorfold-frontend/bin/python` with aiohttp 3.14.3.
- The persistent `tensorfold.conf` systemd drop-in overrides generic llmctl
  ExecStart and ExecStopPost. It avoids key material in argv and preserves the
  exact TensorFold cleanup/lifetime rules if llmctl regenerates its base unit.
- Normal stop tears down both ranks. Adapter failure preserves running or unknown
  rank state unless a stopped rank is confirmed; an SSH failure is not proof of a
  dead worker. Independent guards remain responsible for memory safety.
- Old EXL3 vLLM service is inactive/disabled. Its registry is parked at
  `~/.config/llmctl/rollback/glm53-exl3.conf` to avoid a duplicate port in the
  registry. The original checkout/service remain available for explicit rollback.
- Rollback snapshot: `~/.cache/llmctl-rollback/tensorfold-promotion-20261001T072342`.
  For rollback, stop/disable TensorFold, park its registry entry, restore the
  original EXL3 registry, verify the original vLLM memory guards, then enable/start
  the original service. Never start both runtimes simultaneously.
- ComfyUI services remain stopped/disabled. GPU Whisper startup was disabled to
  avoid competing for memory on reboot. CPU Kokoro and Hermes gateway remain up.
- Startup enablement was read back; a physical reboot was not performed.

## Verification and recovery receipt

The first service attempt incorrectly used `/usr/bin/python3`, which lacked
`aiohttp`. Its original unconditional stop hook unloaded the otherwise healthy
model. This was not a rollback. A dedicated venv and import-before-loading check
fixed the environment mismatch; the stop hook was changed to preserve healthy
ranks on orchestration failures. Model reload completed in 113.5 seconds.

Independent review additionally found missing production disconnect cancellation,
future llmctl argv-key exposure, and destructive teardown on unknown worker state.
Those were corrected with explicit handler cancellation, fixed keyfile-only
ExecStart drop-in, and confirmed-failure-only teardown. Five targeted connection
regressions passed. Root suite: 34 tests run, three skipped, no failures, using:

```
uv run --no-project --with 'aiohttp==3.14.3' --with pillow --with numpy \
  python -m unittest discover -s tests -p 'test_*.py'
```

A frontend-only handoff applied the fixes without unloading either rank;
container start time stayed `2026-10-01T14:30:44.687651317Z`. The temporary
no-teardown handoff drop-in was removed and normal cleanup restored/read back.

Verified from Open WebUI's container through its actual configured URL/key:
model listing identifies TensorFold; real inference returned
`Browser connection verified.`; default-thinking inference returned `YDAER`
for READY backwards, with 46 reported reasoning tokens. Unauthenticated model
listing on port 8005 returned 401. Both browser URLs returned HTTP 200.
Final observed available memory was approximately 11.8/13.9 GiB head/worker.
This tests the configured browser backend connection, not a logged-in browser
click-through or a fresh full evaluation battery.

Deployment scripts, tests and this note are local changes after evaluation commit
`9c059c1`; no new commit/push was authorized as part of promotion.
