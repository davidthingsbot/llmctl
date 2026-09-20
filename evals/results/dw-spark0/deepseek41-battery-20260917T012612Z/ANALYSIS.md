# DeepSeek V4.1 Flash EXL3 dual-Spark battery

Completed all planned text-capable checks in the 262144-token context, 1.5GiB explicit KV-cache, DSpark3 configuration. Vision is unsupported by the selected recipe/kernel; it was not scored as a failure.

- Work quality:411/438 (93.8%), no request errors/truncation.
- Deep reasoning:232/302 (76.8%), no request errors/truncation.
- Thinking disabled for these evals; not a maximum-reasoning-mode measurement.
- Tool smoke emitted get_weather(city=Seattle), then completed the protocol with synthetic weather output. This was not a real weather lookup.
- Concurrency aggregate tokens/s at1/2/4/8 requests:21.9/36.9/34.3/35.2; two configured active sequences limit scaling.
- Exact-key retrieval succeeded at31917,99696,and199319 tokenized prompt tokens. The200K test completed in254.7seconds.
- Lowest five-second sampled available memory during test phases:7.58GiB head,9.76GiB worker. No claim about sub-sample transient minima.
- Final live health check HTTP200.

Setup blockers resolved before this successful run:
1. Native Engram config.json was required in addition to the two shards and index listed in the original staging instructions. Downloaded original config and copied it to worker.
2. Upstream launcher forwarded VLLM_SPARSE_INDEXER_MAX_LOGITS_MB as an empty string, overriding its earlier default. Explicitly setting256 resolved the int-parsing failure; verified vLLM environment cache initialization in the container before retry.

Both weights and Engram tables are local on each Spark; no NFS changes. Failed attempts are separate sibling result directories. No chat repointing or automatic rollback occurred. Next authorized experiment: dual-Spark Mistral Medium3.5 NVFP4 with vision.
