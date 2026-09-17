"""Load a LeRobot VLA checkpoint on the GPU, feed a synthetic observation, report VRAM and per-chunk latency.

Usage: ~/.venvs/lerobot/bin/python evals/diagnostics/vla_bench.py <policy_type> <checkpoint_dir> [dtype]
  e.g.  ... smolvla ~/models/vla/smolvla_base
        ... pi05 ~/models/vla/pi05_base bfloat16   (needs hf auth login + access to google/paligemma-3b-pt-224 for the tokenizer)
Measured 2026-09-17 on the RTX 5080: smolvla 0.9 GiB, 79 ms per 50-step chunk; pi05 fp32 OOMs at 13.5 GiB of weights, bf16 loads.
"""
import sys, time, json, torch
from lerobot.policies import get_policy_class, make_pre_post_processors
from lerobot.configs.policies import PreTrainedConfig

ptype, path = sys.argv[1], sys.argv[2]
dtype = sys.argv[3] if len(sys.argv) > 3 else None
torch.cuda.reset_peak_memory_stats()
cfg = PreTrainedConfig.from_pretrained(path)
if dtype and hasattr(cfg, "dtype"): cfg.dtype = dtype
t0 = time.perf_counter()
policy = get_policy_class(ptype).from_pretrained(path, config=cfg)
policy.to("cuda").eval()
load_s = time.perf_counter() - t0
pre, post = make_pre_post_processors(policy.config, pretrained_path=path,
    preprocessor_overrides={"device_processor": {"device": "cuda"}},
    postprocessor_overrides={"device_processor": {"device": "cuda"}})
obs = {"task": "pick up the red cup and place it in the bin"}
for k, f in policy.config.input_features.items():
    shape = list(f.shape)
    if "image" in k: obs[k] = torch.rand(1, *shape, dtype=torch.float32)
    else: obs[k] = torch.zeros(1, *shape, dtype=torch.float32)
lat = []
with torch.inference_mode():
    for i in range(12):
        o = pre(dict(obs))
        torch.cuda.synchronize(); t = time.perf_counter()
        chunk = policy.predict_action_chunk(o)
        torch.cuda.synchronize(); dt = time.perf_counter() - t
        if i >= 2: lat.append(dt)
        policy.reset()
act = post(chunk)
print(json.dumps({"policy": ptype, "dtype": dtype or str(cfg.dtype if hasattr(cfg,'dtype') else None),
    "load_s": round(load_s, 1), "peak_vram_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2),
    "chunk_shape": list(chunk.shape), "latency_ms_median": round(1000 * sorted(lat)[len(lat)//2], 1),
    "latency_ms_min": round(1000 * min(lat), 1), "hz_if_chunk_50_at_30fps": "chunk covers 1.67 s"}))
