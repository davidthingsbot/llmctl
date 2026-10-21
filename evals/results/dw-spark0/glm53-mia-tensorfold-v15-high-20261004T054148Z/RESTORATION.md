# Authorized restoration

User requested: “Okay, return to the previous one.”

Stopped transient glm53-mia-eval-frontend, stopped candidate ranks via candidate stop.sh (saved logs), then started existing enabled llm-glm53-tensorfold.service. No recipe/default/config changes required.

Verified both loaded ranks serve TR3 revision9eaebb7c4e96d983dcd538e18624622ba5b820a8 from Mia-AiLab/GLM-5.3-Flash-EXL3-TR3-4bpw. Both actual image IDs sha256:0266e5767a4fb7cba90e587c6f69ab59dea24a0cd08ea983d333295717e9bf24 (previous ae8d1c789b47 runtime), not candidate image. Production service active/enabled; both persistent guardsactive/enabled; candidate transientfrontendinactive. Authenticated8005healthok; real request through open-webui configured backend returned “Previous model restored.” Context1048576/fourstreams preserved. New candidate weights and raw evaluation results retained; no automatic reevaluation or promotion queued.

This receipt supersedes ANALYSIS.md's post-evaluation observation that the candidate remains loaded. Evaluation scores and original status remain unchanged.
