# dw-spark0 leaderboard

Clean sweep, all three tiers, 12k-token floor. Tier columns are legacy / easy / medium / hard. `(cold)` = no retry; `(retry×N)` = N tasks got a do-over, credited at 0.7. Fable 5.1 answered offline and is the harness reference: anything it does not max is a harness suspect.

| model | work L/E/M/H = total | reasoning L/E/M/H = total | concurrency 1/2/4/8 tok/s | tokens | wall |
|---|---|---|---|---:|---:|
| **Fable 5.1 (reference)** | 100 / 64 / 154 / 120 = **438**/438 | 100 / 56 / 68 / 78 = **302**/302 | — | — | — |
| `qwen38-27b-nvfp4` | 84 / 64 / 130 / 92 = **370**/438 (cold) | 79 / 48 / 51 / 30 = **208**/302 (cold) | 11 / 20 / 41 / 79 | 16816 | 25 min |
| `qwen38-27b-fp8` | 91 / 64 / 118 / 92 = **365**/438 (cold) | 75 / 48 / 37 / 67 = **227**/302 (retry×10) | 8 / 16 / 31 / 59 | 21407 | 46 min |

## Retry gaps (score_first → credited)

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
