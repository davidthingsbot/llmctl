# Final runtime-only TR3 / TensorFold v1.10 trial

## Verdict
Recommend v1.10 runtime with existing TR3 weights, not Mia's recalibrated or Ablit checkpoints. Quality scores and every task's score matched the previous TensorFold/TR3 run. Tool/caching checks passed. New runtime is serving the browser temporarily; persistent default has NOT been changed and promotion requires user decision. Prior runtime remains intact for rollback.

## Identity / controlled settings
Recipe549fdc562c477d477244d2df0590d6c14bda4889; both imageIDs sha256:a24e8b6fdb176eea051b8508e1109e82cc8d5cd3159f4f1591567bf0fb32c939; patcha1897d591f70. CheckpointTR3 pinned9eaebb7c4e96d983dcd538e18624622ba5b820a8; drafterbf582e4e. Both loadedcheckpoint paths/imagepatchlabels checked. Same hardware2Sparks, context1048576/fourstreams/reserve18GiB/KV8GiB; experimental efforttail/spill/display/cacheshare/loopguard/decodeorder off. Grading unchanged from historical baseline glm53-tensorfold-high-20261001T115956Z. High reasoning/temp0/text32768/vision16384; textretrycredit0.7.

## Quality and timing
All20reasoning/22engineering/25vision cases completed. MatchedtaskIDsets verified, no pertaskscorechanges:
- Reasoning298/302 vs298/302.
- Engineering417/438 vs417/438.
- Vision70/78 vs70/78.
Sum of per-task elapsed including retries, new/old seconds:174.02/173.75,387.02/380.51,464.08/465.45. No broad task-speed improvement claimed. Known prior streamgrader builtin omission remains in unchangedgrader; no regression seen for this TR3answer, no scores altered.

## Operational tests
Text/reasoningtrace/toolnone/toolroundtrip passed. Upstreamtoolcheck typedarray passed. Agentpromptreusecheck: cold33036tokens20.4s; nextthreeafterotherconversation99%cached,1.9/1.1/1.0s. This verifies cache reuse, not a locally matched old-vs-new cachedialog benchmark.

1/2/4concurrency zero failures. Thinkinghigh short harness max1024 aggregate45.0/83.2/147.5tok/s vs44.8/77.0/143.7 old. Thinkingoffmax400:42.0/60.3/108.6 vs42.4/60.0/106.6. Single-run localharness, end-to-endtokenusage/wall measurements; not publishermatchedsparkDash, no universal throughputclaim. Deletedpublisherbench explicitlyomitted.

## Context
All5unique-keyretrievals successful. Actualcounts31934/99736/199409/498402/897097; elapsed16.60/50.20/106.46/313.25/675.90s. Strictformatfailed at32K/100K/500K because extra wording; passed200K/900K. Originalcorrectfalse preserved. Finalcomplete_with_format_failure, not unqualifiedpass. Previousrun hadone strictformatfailure at100K: formatcompliance worse in thissample. Randomneedles/promptcounts differ; cannot attributeformatvariance causally fromsingle trials. Largestretrieval675.90s vs historical795.08s at897103tokens is directional, not identicalpromptcontrolledtiming. Retrieval not deepcomprehension/full1M/foursimultaneous1Mqualification.

## Post-run state
Authenticated8005healthok/idle afterevaluation; actualWebUIconfiguredbackend replyREADY. Bothguardsactive; availableRAM11.53/13.89GiB afterprobe. Transientglm53-tr3-v110-eval-frontendactive; oldpersistentserviceinactive but unchanged/enabled. Existingbrowserendpoint temporarilyv1.10/TR3. No permanentpromotion/autorollback/deletion. Results/docs localuncommitted.
