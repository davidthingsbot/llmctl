# Authorized next experiments

David authorized:
1. Complete the full text-capable battery on DeepSeek V4.1 EXL3 across both Sparks: serving/tool smoke, work quality, deep reasoning, concurrency, progressively longer context. Selected recipe is text-only; mark vision unsupported, not failed. No repointing or automatic rollback; preserve guards and results.
2. AFTER that is done, develop and try a dual-Spark Mistral Medium 3.5 NVFP4 setup with vision. The single-Spark32K run was diagnostic only, not the target. User prefers both Sparks and context useful beyond32K.

Known Mistral prerequisites and evidence: /home/david/work/mistral-vision/TRIAL.md and probe_flashinfer.py. Image-token mismatch resolved using an isolated HF tokenizer directory; service PATH must include CUDA nvcc plus venv ninja. The current single-Spark setup successfully answered both image smoke tests. TP2 needs compatible runtimes and weights on worker and actual distributed validation; do not assume changing TENSOR_PARALLEL alone creates multi-node execution.

DeepSeek staging: resumable rsync of model and Engram directories to worker /home/david/work/deepseek41-exl3 is underway. Local worktree source b9c49e9 at last inspection. Both images previously downloaded; confirm identity and recipe compatibility before launch. Worker container guard was found absent on latest inspection and must be restored/verified before a model launch.
