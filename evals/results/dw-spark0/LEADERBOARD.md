# dw-spark0 leaderboard

Clean sweep, all three tiers, 12k-token floor. Tier columns are legacy / easy / medium / hard. `(cold)` = no retry; `(retry×N)` = N tasks got a do-over, credited at 0.7. Fable 5.1 answered offline and is the harness reference: anything it does not max is a harness suspect.

| model | work L/E/M/H = total | reasoning L/E/M/H = total | concurrency 1/2/4/8 tok/s | tokens | wall |
|---|---|---|---|---:|---:|
| **Fable 5.1 (reference)** | 100 / 64 / 154 / 120 = **438**/438 | 100 / 56 / 68 / 78 = **302**/302 | — | — | — |
| `qwen38-flash-next` | 98 / 64 / 136 / 111 = **409**/438 (retry×5) | 78 / 56 / 46 / 32 = **212**/302 (retry×9) | 22 / 36 / 48 / 48 | 19152 | 15 min |
| `nemotron-120b` | 96 / 61 / 122 / 117 = **396**/438 (retry×7) | 83 / 42 / 31 / 36 = **192**/302 (retry×12) | 15 / 24 / 41 / 62 | 14655 | 17 min |
| `deepseek-flash-150b` | 94 / 64 / 132 / 98 = **388**/438 (retry×8) | 69 / 56 / 22 / 27 = **174**/302 (retry×14) | 15 / 14 / 34 / 33 | 30904 | 35 min |
| `qwen38-27b-nvfp4` | 84 / 64 / 130 / 92 = **370**/438 (cold) | 79 / 48 / 51 / 30 = **208**/302 (cold) | 11 / 20 / 41 / 79 | 16816 | 25 min |
| `qwen38-27b-fp8` | 91 / 64 / 118 / 92 = **365**/438 (cold) | 75 / 48 / 37 / 67 = **227**/302 (retry×10) | 8 / 16 / 31 / 59 | 21407 | 46 min |

## Retry gaps (score_first → credited)

- `deepseek-flash-150b` embedded_c_review: 10 → retry 12 → credited **10**/12
- `deepseek-flash-150b` protocol_architecture: 16 → retry 16 → credited **16**/18
- `deepseek-flash-150b` acquisition_timing: 4 → retry 4 → credited **4**/6
- `deepseek-flash-150b` cobs_codec: 14 → retry 14 → credited **14**/24
- `deepseek-flash-150b` cuda_medium: 26 → retry 26 → credited **26**/26
- `deepseek-flash-150b` ml_medium: 14 → retry 0 → credited **14**/26
- `deepseek-flash-150b` verilog_hard: 5 → retry 12 → credited **8**/30
- `deepseek-flash-150b` cuda_hard: 30 → retry 30 → credited **30**/30
- `deepseek-flash-150b` logic_grid: 6 → retry 6 → credited **6**/12
- `deepseek-flash-150b` causal_inference: 4 → retry 4 → credited **4**/14
- `deepseek-flash-150b` bayesian_reasoning: 4 → retry 4 → credited **4**/12
- `deepseek-flash-150b` adversarial_epistemology: 12 → retry 14 → credited **12**/14
- `deepseek-flash-150b` value_of_information: 10 → retry 10 → credited **10**/12
- `deepseek-flash-150b` wason_selection: 9 → retry 9 → credited **9**/10
- `deepseek-flash-150b` complex_policy_reasoning: 12 → retry 12 → credited **12**/14
- `deepseek-flash-150b` physics_medium: 13 → retry 13 → credited **13**/16
- `deepseek-flash-150b` optimization_medium: 0 → retry 0 → credited **0**/16
- `deepseek-flash-150b` causal_medium: 9 → retry 9 → credited **9**/18
- `deepseek-flash-150b` sizing_medium: 0 → retry 0 → credited **0**/18
- `deepseek-flash-150b` physics_hard: 0 → retry 0 → credited **0**/20
- `deepseek-flash-150b` optimization_hard: 4 → retry 4 → credited **4**/22
- `deepseek-flash-150b` sizing_hard: 3 → retry 3 → credited **3**/16
- `nemotron-120b` bom_consolidation: 8 → retry 8 → credited **8**/10
- `nemotron-120b` protocol_architecture: 16 → retry 18 → credited **16**/18
- `nemotron-120b` ml_easy: 13 → retry 13 → credited **13**/16
- `nemotron-120b` cobs_codec: 15 → retry 15 → credited **15**/24
- `nemotron-120b` stream_reassembler: 20 → retry 20 → credited **20**/24
- `nemotron-120b` verilog_medium: 7 → retry 9 → credited **7**/26
- `nemotron-120b` verilog_hard: 27 → retry 12 → credited **27**/30
- `nemotron-120b` logic_grid: 3 → retry 6 → credited **4**/12
- `nemotron-120b` bayesian_reasoning: 8 → retry 8 → credited **8**/12
- `nemotron-120b` value_of_information: 9 → retry 9 → credited **9**/12
- `nemotron-120b` complex_policy_reasoning: 12 → retry 12 → credited **12**/14
- `nemotron-120b` sizing_easy: 0 → retry 0 → credited **0**/14
- `nemotron-120b` physics_medium: 13 → retry 13 → credited **13**/16
- `nemotron-120b` optimization_medium: 0 → retry 0 → credited **0**/16
- `nemotron-120b` sizing_medium: 0 → retry 0 → credited **0**/18
- `nemotron-120b` physics_hard: 12 → retry 12 → credited **12**/20
- `nemotron-120b` optimization_hard: 4 → retry 0 → credited **4**/22
- `nemotron-120b` causal_hard: 17 → retry 20 → credited **17**/20
- `nemotron-120b` sizing_hard: 3 → retry 3 → credited **3**/16
- `qwen38-27b-fp8` logic_grid: 3 → retry 6 → credited **4**/12
- `qwen38-27b-fp8` causal_inference: 10 → retry 11 → credited **10**/14
- `qwen38-27b-fp8` bayesian_reasoning: 4 → retry 4 → credited **4**/12
- `qwen38-27b-fp8` value_of_information: 8 → retry 8 → credited **8**/12
- `qwen38-27b-fp8` wason_selection: 9 → retry 10 → credited **9**/10
- `qwen38-27b-fp8` physics_easy: 6 → retry 6 → credited **6**/14
- `qwen38-27b-fp8` physics_medium: 8 → retry 8 → credited **8**/16
- `qwen38-27b-fp8` causal_medium: 13 → retry 13 → credited **13**/18
- `qwen38-27b-fp8` sizing_medium: 0 → retry 0 → credited **0**/18
- `qwen38-27b-fp8` physics_hard: 9 → retry 9 → credited **9**/20
- `qwen38-flash-next` protocol_architecture: 16 → retry 16 → credited **16**/18
- `qwen38-flash-next` cuda_easy: 16 → retry 16 → credited **16**/16
- `qwen38-flash-next` cobs_codec: 14 → retry 14 → credited **14**/24
- `qwen38-flash-next` ml_medium: 0 → retry 26 → credited **18**/26
- `qwen38-flash-next` verilog_hard: 7 → retry 30 → credited **21**/30
- `qwen38-flash-next` logic_grid: 0 → retry 0 → credited **0**/12
- `qwen38-flash-next` bayesian_reasoning: 8 → retry 8 → credited **8**/12
- `qwen38-flash-next` value_of_information: 10 → retry 10 → credited **10**/12
- `qwen38-flash-next` complex_policy_reasoning: 10 → retry 12 → credited **10**/14
- `qwen38-flash-next` optimization_medium: 12 → retry 12 → credited **12**/16
- `qwen38-flash-next` sizing_medium: 0 → retry 0 → credited **0**/18
- `qwen38-flash-next` physics_hard: 9 → retry 9 → credited **9**/20
- `qwen38-flash-next` optimization_hard: 0 → retry 0 → credited **0**/22
- `qwen38-flash-next` sizing_hard: 3 → retry 3 → credited **3**/16
