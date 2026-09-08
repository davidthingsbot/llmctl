# DW-ASUS-LINUX leaderboard

Clean sweep, all three tiers, 12k-token floor. Tier columns are legacy / easy / medium / hard. `(cold)` = no retry; `(retry×N)` = N tasks got a do-over, credited at 0.7. Fable 5.1 answered offline and is the harness reference: anything it does not max is a harness suspect.

| model | work L/E/M/H = total | reasoning L/E/M/H = total | concurrency 1/2/4/8 tok/s | tokens | wall |
|---|---|---|---|---:|---:|
| **Fable 5.1 (reference)** | 100 / 64 / 154 / 120 = **438**/438 | 100 / 56 / 68 / 78 = **302**/302 | — | — | — |
| `qwen3.8-27b-fp8` | 91 / 54 / 100 / 98 = **343**/438 (retry×10) | 73 / 48 / 58 / 67 = **246**/302 (retry×9) | 42 / 80 / 134 / 261 | 27875 | 8 min |

## Retry gaps (score_first → credited)

- `qwen3.8-27b-fp8` bom_consolidation: 9 → retry 10 → credited **9**/10
- `qwen3.8-27b-fp8` embedded_c_review: 10 → retry 10 → credited **10**/12
- `qwen3.8-27b-fp8` protocol_architecture: 16 → retry 18 → credited **16**/18
- `qwen3.8-27b-fp8` acquisition_timing: 0 → retry 3 → credited **2**/6
- `qwen3.8-27b-fp8` verilog_easy: 6 → retry 6 → credited **6**/16
- `qwen3.8-27b-fp8` cobs_codec: 14 → retry 14 → credited **14**/24
- `qwen3.8-27b-fp8` verilog_medium: 10 → retry 10 → credited **10**/26
- `qwen3.8-27b-fp8` cuda_medium: 24 → retry 24 → credited **24**/26
- `qwen3.8-27b-fp8` ml_medium: 0 → retry 0 → credited **0**/26
- `qwen3.8-27b-fp8` verilog_hard: 8 → retry 8 → credited **8**/30
- `qwen3.8-27b-fp8` logic_grid: 0 → retry 0 → credited **0**/12
- `qwen3.8-27b-fp8` causal_inference: 9 → retry 14 → credited **10**/14
- `qwen3.8-27b-fp8` bayesian_reasoning: 4 → retry 4 → credited **4**/12
- `qwen3.8-27b-fp8` wason_selection: 9 → retry 10 → credited **9**/10
- `qwen3.8-27b-fp8` complex_policy_reasoning: 12 → retry 12 → credited **12**/14
- `qwen3.8-27b-fp8` physics_easy: 6 → retry 6 → credited **6**/14
- `qwen3.8-27b-fp8` physics_medium: 8 → retry 8 → credited **8**/16
- `qwen3.8-27b-fp8` causal_medium: 16 → retry 13 → credited **16**/18
- `qwen3.8-27b-fp8` physics_hard: 9 → retry 9 → credited **9**/20
