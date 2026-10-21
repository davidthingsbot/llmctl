# Mia calibrated checkpoint / TensorFold v1.5 trial

## Final result

All local battery stages ran. Status `complete_with_format_failure`: unique-key retrieval succeeded on all five requests, but the 199357-token request returned extra wording. Strict result remains false. Largest actual tokenized prompt was 897575 (single-needle retrieval, not comprehension or simultaneous full-context qualification).

Candidate checkpoint `Mia-AiLab/GLM-5.3-Flash-EXL3-4bpw-TensorFold`, revision `078455ffe6472f9a52fbc1139f58b9db2881b25c`; recipe `a15282478bd0e58ea80c512c330df3f61af85f74`; runtime patch hash `9f73cca659a1`; both image IDs `sha256:e97db95dd4b3f9a5ebd6ddeafb8d7d422dda729cc01b33d7f5c6ecfcf9cf2aaf`. Actual both-rank checkpoint paths retained in rank-command receipts. Prior comparison is `glm53-tensorfold-high-20261001T115956Z`, TR3 with older runtime. These comparisons change checkpoint AND runtime; they do not isolate quantization as a cause.

## Quality

High reasoning, temperature 0; text ceiling32768, vision ceiling16384; text retries credited at0.7. Same task IDs verified: reasoning20, engineering22, vision25.

- Reasoning:290/302 vs298/302.
- Engineering raw:380/438 vs417/438.
- Vision:67/78 vs70/78.

Engineering diagnostic: the sandbox omitted `isinstance`, `str`, and `memoryview`. Candidate stream-reassembler first and retry answers both pass all retained checks after providing these standard builtins:24/24 rather than original2/24. Old answer stays24/24 under the same diagnostic. Engineering diagnostic total402/438, still below417/438; ORIGINAL380 remains unchanged. See `stream-grading-diagnostic.json`. C++ failures are actual initial compilation defects (undeclared hbuf; vector/method grad name clash), subsequently repaired with discounted retry credit. Vision regressions include connector-view reflection and cube rotation, partly offset by a directed-link field gain. Reasoning regressions concentrate in two optimization cases. Single runs, no statistical superiority claim.

Sum of task elapsed seconds including retries (not overall wall clock): candidate/old reasoning412.39/173.75, engineering365.59/380.51, vision428.01/465.45.

## Operational evidence

Text, thinking trace, tool-call roundtrip and tool_choice:none smokes passed. 1/2/4 concurrency sweeps each had zero failed requests. Thinking-on short harness (1024-token ceiling): aggregate47.7/63.8/114.9tok/s; off(400 ceiling):43.2/62.2/142.2tok/s. These are this local harness, not matched publisher sparkDash measurements. Upstream removed tools/bench.py; publisher benchmark explicitly not run.

Retrieval actual tokenized counts31924/99717/199357/498445/897575; elapsed16.58/52.39/113.95/358.03/822.49s. Four exact-format successes;199357 key retrieved with format failure. This is not a full1M test.

After completion authenticated frontend8005 healthy/idle, candidate transient frontend active, both persistent scoped memory guards active. Open WebUI's configured authenticated backend returned actual READY. Available RAM observed10.27GiB head/13.26GiB worker. Persistent default/config unchanged; old production service deliberately stopped for evaluation; candidate remains loaded and temporarily serves existing browser endpoint. No automatic rollback or promotion. Both old and new weights preserved.

## Recommendation

Do not promote on this evidence. Candidate did not improve local engineering/reasoning/vision quality even after the identified grading diagnostic. A same-runtime old-TR3 comparison could separate runtime/template effects from quantization, but was not performed. User authorization covered download/evaluation and unrestricted downtime, not permanent replacement. Results are local and not committed/pushed.
