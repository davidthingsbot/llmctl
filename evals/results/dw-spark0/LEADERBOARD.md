# dw-spark0 leaderboard

Clean sweep, all three tiers, 12k-token floor. Tier columns are legacy / easy / medium / hard. `(cold)` = no retry; `(retry×N)` = N tasks got a do-over, credited at 0.7. Fable 5.1 answered offline and is the harness reference: anything it does not max is a harness suspect.

| model | work L/E/M/H = total | reasoning L/E/M/H = total | concurrency 1/2/4/8 tok/s | tokens | wall |
|---|---|---|---|---:|---:|
| **Fable 5.1 (reference)** | 100 / 64 / 154 / 120 = **438**/438 | 100 / 56 / 68 / 78 = **302**/302 | — | — | — |
| `qwen38-27b-nvfp4` | 84 / 64 / 130 / 92 = **370**/438 (cold) | 79 / 48 / 51 / 30 = **208**/302 (cold) | 11 / 20 / 41 / 79 | 16816 | 25 min |
| `qwen38-27b-fp8` | 91 / 64 / 118 / 92 = **365**/438 (cold) | — | — | 9576 | 21 min |

## Retry gaps (score_first → credited)

_No retry-era results yet._
