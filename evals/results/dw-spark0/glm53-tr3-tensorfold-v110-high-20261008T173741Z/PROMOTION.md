# Production promotion, 2026-10-08

User authorized promotion of v1.10 with TR3. Completed: persistent llm-glm53-tensorfold.service active/enabled, Restart=no. Launcher and teardown now use /home/david/work/glm53-tensorfold-tr3-v110 at549fdc562c477d477244d2df0590d6c14bda4889. Authenticated consumer8005, backendloopback18888, same browser configuration/modelID. Stopped temporary glm53-tr3-v110-eval-frontend. Existing healthy ranks adopted without model reload.

Both loaded ranks verified exact TR3 snapshot9eaebb7c4e96d983dcd538e18624622ba5b820a8 and actualimage sha256:a24e8b6fdb176eea051b8508e1109e82cc8d5cd3159f4f1591567bf0fb32c939. Both persistentguardsactive/enabled. Browser-configured authenticated backend answered “Production ready.”

Rollback unchanged priorrecipe /home/david/work/glm53-tensorfold (92bf731) and image tensorfold-glm53:v0.6.0 sha256:0266e5767a4fb7cba90e587c6f69ab59dea24a0cd08ea983d333295717e9bf24. Prepromotionlauncher/teardown/modelconf/service saved ~/.cache/llmctl-rollback/tr3-v110-promotion-20261008T215816Z. Do not run old/newranks together. Restoring oldstack requires restoring launcher/teardown paths as well as stoppingv1.10ranks. Currentguards/auth/context1048576/fourstreams/reserve18/KV8 unchanged; experimentalflags remainoff.

No further tests or promotion queued. Trial scores/status preserved, results/operationalchanges localuncommitted, not pushed. Supersedes ANALYSIS.md trial-serving/promotion-pending state.
