# DW-AMD-LINUX leaderboard

Clean sweep, all three tiers, 12k-token floor. Tier columns are legacy / easy / medium / hard. `(cold)` = no retry; `(retry×N)` = N tasks got a do-over, credited at 0.7. Fable 5.1 answered offline and is the harness reference: anything it does not max is a harness suspect.

| model | work L/E/M/H = total | reasoning L/E/M/H = total | concurrency 1/2/4/8 tok/s | tokens | wall |
|---|---|---|---|---:|---:|
| **Fable 5.1 (reference)** | 100 / 64 / 154 / 120 = **438**/438 | 100 / 56 / 68 / 78 = **302**/302 | — | — | — |
| `qwen3.5-9b-vl` | 87 / 61 / 45 / 25 = **218**/438 (retry×15) | 62 / 34 / 29 / 32 = **157**/302 (retry×15) | 119 / 216 / 360 / 355 | 32449 | 5 min |
| `qwen3.5-4b-spec` | 87 / 56 / 44 / 0 = **187**/438 (retry×15) | 60 / 34 / 24 / 24 = **142**/302 (retry×17) | 27 / 30 / 30 / 47 | 53883 | 9 min |
| `qwen3.5-4b-vl` | 87 / 46 / 31 / 8 = **172**/438 (retry×16) | 67 / 34 / 24 / 27 = **152**/302 (retry×15) | 132 / 251 / 414 / 400 | 20764 | 5 min |

## Retry gaps (score_first → credited)

- `qwen3.5-4b-spec` bom_consolidation: 8 → retry 8 → credited **8**/10
- `qwen3.5-4b-spec` code_repair: 17 → retry 17 → credited **17**/20
- `qwen3.5-4b-spec` protocol_architecture: 14 → retry 14 → credited **14**/18
- `qwen3.5-4b-spec` acquisition_timing: 2 → retry 2 → credited **2**/6
- `qwen3.5-4b-spec` verilog_easy: 0 → retry 12 → credited **8**/16
- `qwen3.5-4b-spec` cobs_codec: 8 → retry 0 → credited **8**/24
- `qwen3.5-4b-spec` stream_reassembler: 19 → retry 19 → credited **19**/24
- `qwen3.5-4b-spec` verilog_medium: 0 → retry 16 → credited **11**/26
- `qwen3.5-4b-spec` cuda_medium: 6 → retry 6 → credited **6**/26
- `qwen3.5-4b-spec` cpp_medium: 0 → retry 0 → credited **0**/28
- `qwen3.5-4b-spec` ml_medium: 0 → retry 0 → credited **0**/26
- `qwen3.5-4b-spec` cpp_hard: 0 → retry 0 → credited **0**/30
- `qwen3.5-4b-spec` verilog_hard: 0 → retry 0 → credited **0**/30
- `qwen3.5-4b-spec` cuda_hard: 0 → retry 0 → credited **0**/30
- `qwen3.5-4b-spec` ml_hard: 0 → retry 0 → credited **0**/30
- `qwen3.5-4b-spec` logic_grid: 3 → retry 3 → credited **3**/12
- `qwen3.5-4b-spec` causal_inference: 6 → retry 12 → credited **8**/14
- `qwen3.5-4b-spec` bayesian_reasoning: 4 → retry 4 → credited **4**/12
- `qwen3.5-4b-spec` hypothesis_discrimination: 11 → retry 11 → credited **11**/12
- `qwen3.5-4b-spec` adversarial_epistemology: 8 → retry 12 → credited **8**/14
- `qwen3.5-4b-spec` value_of_information: 7 → retry 7 → credited **7**/12
- `qwen3.5-4b-spec` wason_selection: 9 → retry 9 → credited **9**/10
- `qwen3.5-4b-spec` complex_policy_reasoning: 10 → retry 10 → credited **10**/14
- `qwen3.5-4b-spec` physics_easy: 6 → retry 6 → credited **6**/14
- `qwen3.5-4b-spec` sizing_easy: 0 → retry 0 → credited **0**/14
- `qwen3.5-4b-spec` physics_medium: 9 → retry 9 → credited **9**/16
- `qwen3.5-4b-spec` optimization_medium: 2 → retry 2 → credited **2**/16
- `qwen3.5-4b-spec` causal_medium: 13 → retry 13 → credited **13**/18
- `qwen3.5-4b-spec` sizing_medium: 0 → retry 0 → credited **0**/18
- `qwen3.5-4b-spec` physics_hard: 0 → retry 0 → credited **0**/20
- `qwen3.5-4b-spec` optimization_hard: 4 → retry 4 → credited **4**/22
- `qwen3.5-4b-spec` sizing_hard: 0 → retry 0 → credited **0**/16
- `qwen3.5-4b-vl` bom_consolidation: 8 → retry 2 → credited **8**/10
- `qwen3.5-4b-vl` code_repair: 17 → retry 17 → credited **17**/20
- `qwen3.5-4b-vl` protocol_architecture: 14 → retry 16 → credited **14**/18
- `qwen3.5-4b-vl` acquisition_timing: 2 → retry 2 → credited **2**/6
- `qwen3.5-4b-vl` verilog_easy: 0 → retry 12 → credited **8**/16
- `qwen3.5-4b-vl` cuda_easy: 6 → retry 6 → credited **6**/16
- `qwen3.5-4b-vl` cobs_codec: 5 → retry 5 → credited **5**/24
- `qwen3.5-4b-vl` stream_reassembler: 20 → retry 20 → credited **20**/24
- `qwen3.5-4b-vl` verilog_medium: 0 → retry 0 → credited **0**/26
- `qwen3.5-4b-vl` cuda_medium: 6 → retry 6 → credited **6**/26
- `qwen3.5-4b-vl` cpp_medium: 0 → retry 0 → credited **0**/28
- `qwen3.5-4b-vl` ml_medium: 0 → retry 0 → credited **0**/26
- `qwen3.5-4b-vl` cpp_hard: 0 → retry 0 → credited **0**/30
- `qwen3.5-4b-vl` verilog_hard: 0 → retry 0 → credited **0**/30
- `qwen3.5-4b-vl` cuda_hard: 8 → retry 8 → credited **8**/30
- `qwen3.5-4b-vl` ml_hard: 0 → retry 0 → credited **0**/30
- `qwen3.5-4b-vl` logic_grid: 3 → retry 3 → credited **3**/12
- `qwen3.5-4b-vl` causal_inference: 4 → retry 11 → credited **8**/14
- `qwen3.5-4b-vl` bayesian_reasoning: 4 → retry 4 → credited **4**/12
- `qwen3.5-4b-vl` hypothesis_discrimination: 9 → retry 11 → credited **9**/12
- `qwen3.5-4b-vl` value_of_information: 7 → retry 7 → credited **7**/12
- `qwen3.5-4b-vl` complex_policy_reasoning: 12 → retry 12 → credited **12**/14
- `qwen3.5-4b-vl` physics_easy: 6 → retry 6 → credited **6**/14
- `qwen3.5-4b-vl` sizing_easy: 0 → retry 0 → credited **0**/14
- `qwen3.5-4b-vl` physics_medium: 9 → retry 9 → credited **9**/16
- `qwen3.5-4b-vl` optimization_medium: 2 → retry 2 → credited **2**/16
- `qwen3.5-4b-vl` causal_medium: 13 → retry 13 → credited **13**/18
- `qwen3.5-4b-vl` sizing_medium: 0 → retry 0 → credited **0**/18
- `qwen3.5-4b-vl` physics_hard: 0 → retry 0 → credited **0**/20
- `qwen3.5-4b-vl` optimization_hard: 4 → retry 4 → credited **4**/22
- `qwen3.5-4b-vl` sizing_hard: 3 → retry 3 → credited **3**/16
- `qwen3.5-9b-vl` bom_consolidation: 9 → retry 9 → credited **9**/10
- `qwen3.5-9b-vl` code_repair: 17 → retry 17 → credited **17**/20
- `qwen3.5-9b-vl` embedded_c_review: 10 → retry 8 → credited **10**/12
- `qwen3.5-9b-vl` protocol_architecture: 16 → retry 16 → credited **16**/18
- `qwen3.5-9b-vl` acquisition_timing: 1 → retry 1 → credited **1**/6
- `qwen3.5-9b-vl` ml_easy: 13 → retry 13 → credited **13**/16
- `qwen3.5-9b-vl` cobs_codec: 5 → retry 5 → credited **5**/24
- `qwen3.5-9b-vl` stream_reassembler: 0 → retry 4 → credited **3**/24
- `qwen3.5-9b-vl` verilog_medium: 0 → retry 11 → credited **8**/26
- `qwen3.5-9b-vl` cpp_medium: 3 → retry 3 → credited **3**/28
- `qwen3.5-9b-vl` ml_medium: 0 → retry 0 → credited **0**/26
- `qwen3.5-9b-vl` cpp_hard: 0 → retry 6 → credited **4**/30
- `qwen3.5-9b-vl` verilog_hard: 0 → retry 0 → credited **0**/30
- `qwen3.5-9b-vl` cuda_hard: 0 → retry 0 → credited **0**/30
- `qwen3.5-9b-vl` ml_hard: 13 → retry 30 → credited **21**/30
- `qwen3.5-9b-vl` logic_grid: 3 → retry 3 → credited **3**/12
- `qwen3.5-9b-vl` causal_inference: 4 → retry 12 → credited **8**/14
- `qwen3.5-9b-vl` bayesian_reasoning: 4 → retry 4 → credited **4**/12
- `qwen3.5-9b-vl` hypothesis_discrimination: 9 → retry 11 → credited **9**/12
- `qwen3.5-9b-vl` adversarial_epistemology: 10 → retry 8 → credited **10**/14
- `qwen3.5-9b-vl` value_of_information: 5 → retry 5 → credited **5**/12
- `qwen3.5-9b-vl` wason_selection: 9 → retry 9 → credited **9**/10
- `qwen3.5-9b-vl` physics_easy: 6 → retry 6 → credited **6**/14
- `qwen3.5-9b-vl` sizing_easy: 0 → retry 0 → credited **0**/14
- `qwen3.5-9b-vl` physics_medium: 9 → retry 9 → credited **9**/16
- `qwen3.5-9b-vl` optimization_medium: 2 → retry 2 → credited **2**/16
- `qwen3.5-9b-vl` sizing_medium: 0 → retry 0 → credited **0**/18
- `qwen3.5-9b-vl` physics_hard: 6 → retry 6 → credited **6**/20
- `qwen3.5-9b-vl` optimization_hard: 4 → retry 4 → credited **4**/22
- `qwen3.5-9b-vl` sizing_hard: 0 → retry 3 → credited **2**/16
