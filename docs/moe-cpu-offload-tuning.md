# Tuning large MoE models with CPU expert offload

How to fit a Mixture-of-Experts model that is larger than available VRAM, using
llama.cpp's `--n-cpu-moe`, and what the trade-offs actually cost. Measured on
DW-ASUS-LINUX (2x RTX 3090 = 48 GiB VRAM, 62 GiB DDR3, i7-4930K) on 2026-08-03
with llama.cpp b8189.

The worked example is Qwen3.5-122B-A10B at UD-IQ4_XS (56.09 GiB), but the
mechanics generalise to any sparse MoE that overflows VRAM.

## Why CPU offload works at all for MoE

Decode is memory-bandwidth-bound: each token requires streaming the weights it
touches. A dense model touches everything, so offloading any of it to system RAM
is fatal. A sparse MoE touches only the experts the router selects — Qwen3.5-122B
fires 8 of 256 experts per layer, ~3% — so most expert weights sit idle on any
given token. Parking some of them in RAM costs far less than the parameter count
suggests.

`--n-cpu-moe N` places the **expert FFN tensors of the first N layers** in system
RAM and computes them on the CPU. Attention, norms and routers stay on GPU for
every layer. Only small activation vectors cross PCIe.

This is why llama.cpp beats vLLM for this job on older hardware. vLLM's weight
offload streams *weights* GPU-ward over PCIe; on a PCIe 3.0 x16 board that is
~15.75 GB/s, less than half the ~35-40 GB/s of quad-channel DDR3 that llama.cpp
gets by computing in place. On modern hosts (NVLink-C2C, PCIe 5.0) the
comparison inverts. Check the link before assuming:

```sh
nvidia-smi --query-gpu=pcie.link.gen.max,pcie.link.width.max --format=csv
```

Note that idle GPUs report `pcie.link.gen.current=1`; that is power saving, not
the negotiated speed under load.

## The two traps

### 1. `--tensor-split 1,1` is catastrophically wrong

`--n-cpu-moe N` makes layers `0..N-1` *light* (experts in RAM) and `N..end`
*heavy*. Splitting layers evenly therefore hands every heavy layer to the second
GPU. Measured with `--n-cpu-moe 20 --tensor-split 1,1`:

```
CUDA0:  24122 total,   8856 used,  14606 free
CUDA1:  24124 total,  28407 used,  -4634 free   <- 4.6 GB over capacity
projected to use 37263 MiB of device memory vs. 47235 MiB of free device memory
```

The model fits comfortably in aggregate (37.3 of 47.2 GiB) and still fails. The
first GPU must take **more layers** than the second, because its layers are
lighter. For this model at `--n-cpu-moe 15`, `0.62,0.38` balanced to within
~250 MiB.

The correct ratio depends on `N` and cannot be derived reliably — an analytical
estimate (`0.5 + N/120`, from a measured heavy:light ratio of ~5:1) predicted
0.658 at N=19 where the true value was 0.635, overshooting enough to overflow
CUDA0 by 8 MiB while CUDA1 sat on 3 GB spare. **Bisect it empirically per
configuration.** Two or three loads is enough.

### 2. `--n-cpu-moe` disables llama.cpp's automatic fitter

`--n-cpu-moe` sets `tensor_buft_overrides`, and `llama_params_fit` refuses to
adjust anything once the user has set it:

```
llama_params_fit: failed to fit params to free device memory:
model_params::tensor_buft_overrides already set by user, abort
```

So the split cannot be left automatic — omitting `--tensor-split` does not help.
Both must be supplied. A related abort appears if `-ngl` is pinned and the params
do not fit (`n_gpu_layers already set by user to 99, abort`); that one is benign
once the split is right, since the fitter only intervenes when something
overflows.

Both aborts report the *projected* per-GPU usage before failing, which is the
most useful tuning signal available — read it rather than guessing.

## Tuning procedure

1. Start with a deliberately high `--n-cpu-moe` (about a third of layers) so the
   first load is guaranteed to succeed.
2. Read `CUDA0/CUDA1 model buffer size` from the load log. Adjust
   `--tensor-split` until both GPUs land within a few hundred MiB of each other.
3. Lower `--n-cpu-moe` to move experts back onto the GPU — this is the throughput
   lever — until free VRAM approaches your safety margin.
4. Rebalance the split after each change to `--n-cpu-moe`; the correct ratio
   moves with it.
5. Leave headroom. On a machine whose primary GPU also drives a desktop, 1-2 GiB
   can vanish when a browser starts.

Benchmark with a prompt of at least a few thousand tokens. Short prompts make
prefill look absurdly slow — a 15-token prompt reported ~20 tok/s where a
3530-token prompt on the same server measured 273 tok/s.

## Measured: Qwen3.5-122B-A10B UD-IQ4_XS

48 layers, 256 experts, 8 active per token, 56.09 GiB of weights.

Offload level at 32K context:

| `--n-cpu-moe` | split | VRAM used | free | generation |
|---|---|---|---|---|
| 20 | 0.68,0.32 | 38.3 GB | 3945/— | 12.53 tok/s |
| 15 | 0.62,0.38 | 43.6 GB | 2179/2478 | ~15.0 tok/s |

Moving 5 expert layers from RAM to VRAM bought ~20%. At `--n-cpu-moe 15` the
split is 39.7 GiB on GPU / 17.8 GiB in RAM — **69/31**, confirmed by the
`CPU_Mapped model buffer size = 18269.76 MiB` line and the server's 18.7 GiB RSS.

Context cost. KV is cheap here because only 12 of 48 layers carry it (hybrid
attention), at 24 KiB/token:

| context | KV | `--n-cpu-moe` | split | free VRAM | generation |
|---|---|---|---|---|---|
| 32K | 768 MiB | 15 | 0.62,0.38 | 2179/2478 | 15.0 tok/s |
| 64K | 1536 MiB | 15 | 0.62,0.38 | 1673/2152 | 16.2 tok/s |
| 128K | 3072 MiB | 17 | 0.62,0.38 | 2785/1512 | 14.4 tok/s |
| 256K | 6144 MiB | 19 | 0.635,0.365 | 1199/1904 | 12.4 tok/s |

The model's full native 256K context is reachable, costing ~24% throughput
versus 64K. The mechanism is indirect but consistent: each doubling of context
adds ~1.5 GiB of KV, which forces roughly two more expert layers back to RAM, and
each of those costs about 1 tok/s.

Do not assume KV is expensive on hybrid models. An earlier estimate here assumed
a dense attention stack and overstated 256K KV by roughly 5x.

## Reading the logs

Useful lines, all from `llmctl logs <model>`:

```
load_tensors:        CUDA0 model buffer size = 20192.44 MiB   per-GPU weights
load_tensors:   CPU_Mapped model buffer size = 18269.76 MiB   weights in RAM
llama_kv_cache: size = 768.00 MiB (32768 cells, 12 layers)    KV, and how many
                                                              layers carry it
llama_params_fit_impl: - CUDA0 ... 23447 used, -8 free        why a fit failed
```

`offloaded 49/49 layers to GPU` is misleading: it counts layers, and a layer
counts as offloaded even when its experts are in RAM. Trust
`CPU_Mapped model buffer size` for the real split.

## Recording results

`llmctl machine record` captures model definitions and benchmark history into
`inventory/machines/<name>/`, but it **strips comments** — configuration is
preserved, reasoning is not. Keep the rationale for a tuned model in its
`models.d/*.conf` comments for local use, and durable findings here.
