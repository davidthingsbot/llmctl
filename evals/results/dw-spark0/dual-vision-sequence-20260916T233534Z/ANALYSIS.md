# Dual-Spark sequence results

Both authorized candidates completed vision, work-quality, deep-reasoning and concurrency suites. Fresh endpoint health after the sequence: Qwen port8004 HTTP200. Qwen is left running; GLM EXL3 was stopped to load it. No consumer repointing or prior-model rollback.

## Measured scores
- GLM EXL3: vision68/78 (87.2%),18/25 perfect tasks; work371/438 (84.7%); reasoning295/302 (97.7%).
- Qwen Flash-Next NVFP4 TP2: vision40/78 (51.3%),8/25 perfect tasks; work409/438 (93.4%); reasoning214/302 (70.9%).
- Vision budget4096 on all25 tasks. GLM none truncated; Qwen extra03_closed_road_route truncated. No recorded request errors; all concurrency requests succeeded.
- GLM generation settings: reasoning_effort=low. Qwen: enable_thinking=false. These are configured-route results, not equal reasoning-compute comparisons or proof of model-family ceilings.

## Concurrency
Aggregate tokens/s for1/2/4/8 streams:
- GLM25.1 /36.4 /56.4 /53.7; eight-stream TTFT7.70s.
- Qwen34.2 /44.7 /99.3 /139.5; eight-stream TTFT1.07s.

## Memory
Five-second samples during test phases (excluding loading/transitions): minima GLM5.63/8.94 GiB head/worker; Qwen20.68/23.93 GiB. Not instantaneous-minimum guarantees.

## Interpretation and open checks
GLM performed much better on this vision/reasoning set; Qwen offered stronger measured concurrency and this run's work score. GLM work371 differs from the previous saved-answer regrade409: these are newly generated answers, not a regrade of the same outputs. Major losses include C++ MLP and hard async FIFO, plus COBS retry discount. No absent-NumPy issue in this run. Investigate CUDA medium's barrier_divergence_clean=false despite sanitizer_first showing ERROR SUMMARY:0 errors before treating its two-point loss as a model defect. A task's best retry details can be fully passing while credited score remains discounted; do not infer inconsistency from that alone.

All raw results, per-phase logs, settings and memory samples are in this directory. No final default switch decision was executed.
