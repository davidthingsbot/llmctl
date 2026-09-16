# Same-grader saved-answer comparison

Both models' saved first and retry answers were re-executed using the current hardened graders in one NumPy 2.4.6 environment. No model requests were made; original result files were preserved. Regraded JSON files are adjacent to this report.

## Scores
- NVFP4 work: 403/438 (92.0%), previously recorded 415/438.
- EXL3 work: 409/438 (93.4%), previously recorded 347/438.
- NVFP4 reasoning: 279/302 (92.4%), unchanged.
- EXL3 reasoning: 282/302 (93.4%), unchanged.

## Confounders corrected
EXL3's original eval Python environment lacked NumPy. ml_easy/medium/hard had been assigned partial credit for source structure without executing numerical tests. With NumPy, their saved original answers pass all checks: 3->16, 3->26, 4->30, restoring 62 points. This was evaluator setup failure, not model failure.
The hardened Verilog grader awards zero when simulation never completes. The old NVFP4 hard FIFO timed out in both saved attempts, previously earning 12 structural/initial-check points. Now it earns zero under the same rule applied to EXL3.

## Remaining work differences
19 of 22 credited task scores match.
- COBS: NVFP4 23, EXL3 15. EXL3 first answer 8; saved retry 22, discounted at 0.7 -> 15. Retry decoder incorrectly rejects any encoding ending in 0xff, including valid payload data. Executed counterexample: input ff encodes as 02ff, then raises ValueError. Old NVFP4 first answer missed embedded-zero validation, fixed on retry; 23 first-attempt credit remains higher than discounted perfect retry.
- C++ MLP: NVFP4 28, EXL3 21. EXL3 calculates sigmoid/loss separately inside the hidden-unit loop instead of summing hidden contributions into one output logit. Its numeric gradients are consistent with its incorrect forward function, but XOR training fails in both attempts (reported final loss 1.910097).
- Async FIFO: NVFP4 0, EXL3 21. EXL3 first answer has combinational feedback and is rejected; saved retry passes 30/30, discounted to 21. NVFP4 uses old binary pointers for Gray updates while binary pointers advance, introducing a lag; its original and retry simulations fail to finish.

Shared losses: BOM 8/10 and architecture 16/18; both saved retries score full marks but retry discount leaves original credited score unchanged. Architecture is keyword-graded: missing exact physical-frame naming does not establish conceptual failure, especially where immutable frame identity is discussed.

## Interpretation limits
Same grader and dependencies remove major scoring confounders, not all serving differences. These are one set of saved answers per model, with existing retries generated under their historical checker feedback. The small corrected advantage does not prove EXL3 superiority. Do not blame quantization or recommend numerics changes on the earlier invalid aggregate.
