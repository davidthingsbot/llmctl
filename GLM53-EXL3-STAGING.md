# GLM EXL3 staging handoff

## Current state
- Source checkout: /home/david/work/glm53-exl3 (MiaAI-Lab recipe).
- Both weight repositories transferred to dw-spark1 over 10.100.100.11; rsync dry-run showed no remaining changes.
- Local model registered as glm53-exl3, port 8005, ID GLM-5.3-Flash-EXL3.
- Adapter: scripts/glm53-exl3-tp2.sh. Mocked launch/wait test and existing cluster-backend test pass; this is NOT a GPU launch test.
- .env prepared for the actual CX7 interfaces, GID 5 (RoCE v2), 500000 context / util 0.84, E3, adaptive-k, provisional FP8 dense, vision enabled, abliteration disabled. Runtime memory headroom still requires measurement.
- Container pulls started on both nodes; verify completion, identical image identity, and recipe stamp before declaring ready.
- The currently running glm53-flash model and Hermes routing have not been changed.

## Important integration constraints
llmctl cluster teardown hardcodes vllm_node on every node. The staged .env uses that name for head and worker, and the adapter waits on it after upstream's detached launch. Never launch this alongside another cluster model. Do NOT call upstream stop/status and mistake the old vllm_node for EXL3; verify the model endpoint and image.

llmctl set/up normally repoints agents and may restart this chat gateway. For the isolated trial use explicit old-model down, then up --no-point for the new model, with a rollback to the old model if the trial fails. Do not run that switch merely to finish staging. No actual switch or eval has happened yet.

## Remaining gates
1. Verify pulled image on both nodes. Compare upstream overlay_recipe_hash against image glm53.recipe.stamp; upstream automatically rebuilds on mismatch. Do not bypass that check and silently run old kernels. A build/GPU self-check may need the current model stopped to free memory.
2. Validate staged adapter error handling and full launch lifecycle on real containers during the approved trial. Keep API auth via llmctl's existing key, never print it.
3. Confirm headroom with desktop/browser left open; monitor both nodes during prefill, not just idle. A 500K configured cap is not proof of 500K request capacity.
4. Check health, coherent responses, actual tool calls, vision if used, and concurrent requests. If unstable roll back, do not repoint agents.
5. User explicitly requested existing llmctl evals AFTER stabilization. Inspect current eval runner interfaces and run work-quality, deep-reasoning, and concurrency suites with raw results saved under evals/results/dw-spark0; compare to glm53-flash-nvfp4 under matching request settings. Do not claim evals ran based on startup tests.
