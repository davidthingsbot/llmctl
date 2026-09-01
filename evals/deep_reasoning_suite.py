#!/usr/bin/env python3
"""Novel deep-reasoning suite for locally served chat models."""

from __future__ import annotations

import argparse
import json
import math
import re
import time
import urllib.request
from pathlib import Path


# Chatty and thinking models need room. A cap only costs anything when it BINDS —
# a model that answers in 200 tokens uses 200 whether the ceiling is 160 or
# 12000 — but when it binds it produces a ZERO that looks like a model failure
# and is not. Three separate instances of that were found on 2026-09-01:
# thinking tokens consuming the whole budget, protocol_architecture capped at 520
# in every run ever recorded, and cobs_codec truncated at 700. The per-task
# numbers below are kept as documentation of what each task actually needs; this
# floor is what is enforced.
MIN_TOKEN_BUDGET = 12000

# 12000 tokens at ~10 tok/s is 20 minutes; the old 900s timeout would abort it.
REQUEST_TIMEOUT_S = 2400


def extract_json(text: str):
    """Pull the answer object out of a reply that may also contain prose.

    The previous implementation used a greedy \\{.*\\} span, so a single brace
    anywhere in the model's commentary swallowed the real answer and scored a
    CORRECT reply zero — observed 2026-09-01 when qwen38-27b-nvfp4 returned the
    exact optimum for resource_optimization inside a ```json fence, after
    bullet-point prose, and was graded 0/16 with parsed=False.

    Order: fenced json blocks (last first), the whole reply, then each balanced
    object scanning from the END, because models put the final answer last.
    """
    text = text.strip()
    for candidate in reversed(re.findall(r"```(?:json)?\s*(\{.*?\})\s*```",
                                         text, re.S | re.I)):
        try:
            return json.loads(candidate)
        except Exception:
            pass
    try:
        return json.loads(text)
    except Exception:
        pass
    for start in reversed([i for i, ch in enumerate(text) if ch == "{"]):
        depth = 0
        for end in range(start, len(text)):
            if text[end] == "{":
                depth += 1
            elif text[end] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:end + 1])
                    except Exception:
                        break
    return None


def _visible_answer(message, strip_reasoning):
    """The answer to grade, with any chain-of-thought removed.

    A server that splits thinking correctly returns it in `reasoning_content`
    and leaves `content` clean, so nothing is needed. Some do not: the
    DeepSeek-V4 templates put the opening `<think>` in the *prompt*, so the
    model emits only the closing tag and llama.cpp's parser (as of master
    458681e) leaves the whole monologue in `content`. Grading that scores the
    deliberation instead of the answer — exact-match tasks collapse outright.
    --strip-reasoning drops everything through the final `</think>`.
    """
    content = message.get("content") or ""
    if strip_reasoning and "</think>" in content:
        content = content.rsplit("</think>", 1)[1]
        return content.lstrip()
    return content


def failure_report(details):
    """The raw failure signal to hand back on a retry — no analysis, no hints.

    What a CI run would tell you: the compiler said this, these named checks
    failed. Deliberately omits WHY anything failed and never names the trap a
    task is testing for, so the retry measures whether the model can read an
    error and repair its own work, not whether the harness explained the bug.
    """
    lines = []
    for key in ("compile_error", "compile_errors", "parse_error", "run_error",
                "harness_error", "lint_first", "sanitizer_first"):
        value = details.get(key)
        if not value:
            continue
        if isinstance(value, (list, tuple)):
            lines.extend(str(v) for v in value)
        else:
            lines.append(str(value))
    if details.get("parsed") is False:
        lines.append("response did not parse as JSON")
    if details.get("timed_out") or details.get("timeout"):
        lines.append("execution timed out")
    failed = sorted(k for k, v in details.items()
                    if v is False and not k.startswith("expected_")
                    and k not in ("parsed",))
    if failed:
        lines.append("failed checks: " + ", ".join(failed))
    return "\n".join(lines) if lines else "the answer was not accepted"


RETRY_INSTRUCTION = (
    "Your previous answer did not pass. The output below is what the checker "
    "reported. Return a corrected answer in exactly the same format as before, "
    "with no explanation and no commentary.\n\n"
)



def request(
    url: str, key: str, model: str, prompt: str, max_tokens: int,
    template_kwargs: bool = True,
    strip_reasoning: bool = False,
    history=None,
):
    messages = [
            {
                "role": "system",
                "content": (
                    "Solve the reasoning problem carefully. State only conclusions supported by the "
                    "given evidence, distinguish assumptions from deductions, and obey the requested format."
                ),
            },
            {"role": "user", "content": prompt},
        ]
    if history:
        messages.extend(history)
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    # See work_quality_suite.py: Mistral-tokenizer models reject this with HTTP
    # 400. Default stays on so the existing Qwen results remain comparable.
    if template_kwargs:
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
    )
    started = time.monotonic()
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as response:
        data = json.load(response)
    message = data["choices"][0]["message"]
    return (
        _visible_answer(message, strip_reasoning),
        data.get("usage", {}),
        time.monotonic() - started,
    )


def task_logic_grid():
    prompt = '''Four researchers—Ada, Ben, Cara and Dion—each present on a different day Monday through Thursday and on a different topic: Logic, Biology, History or Economics.

Clues:
1. Dion presents Logic.
2. Ada presents exactly one day after the Economics presentation.
3. Ben presents earlier than Cara.
4. History is presented Monday.
5. Cara does not present Biology.
6. Logic is presented exactly one day after Ben presents.

Return ONLY JSON. Keys must be the four names. Each value must contain `day` and `topic`.'''
    expected = {
        "Ada": {"day": "Thursday", "topic": "Biology"},
        "Ben": {"day": "Monday", "topic": "History"},
        "Cara": {"day": "Wednesday", "topic": "Economics"},
        "Dion": {"day": "Tuesday", "topic": "Logic"},
    }

    def grade(text):
        data = extract_json(text)
        checks = {name: bool(isinstance(data, dict) and data.get(name) == value) for name, value in expected.items()}
        return sum(3 for ok in checks.values() if ok), 12, checks

    return "logic_grid", prompt, 260, grade


def task_causal_inference():
    prompt = '''A voluntary job-training program is associated with higher employment, but more motivated people are more likely to enroll. Eligibility is determined by a score cutoff at 70. Participation jumps sharply at 70 but is not universal above the cutoff and some below it still participate. The score cannot be precisely manipulated, potential outcomes vary smoothly through 70 absent treatment, and no other policy changes at that threshold.

Return ONLY JSON with keys `design`, `instrument`, `estimand`, `global_generalization`, and `assumptions`. `assumptions` must be an array. Identify the strongest causal design, what creates exogenous treatment variation, the causal quantity identified, whether it automatically generalizes to everyone, and the key identification assumptions.'''

    def grade(text):
        data = extract_json(text)
        design = str(data.get("design", "")).lower() if isinstance(data, dict) else ""
        instrument = str(data.get("instrument", "")).lower() if isinstance(data, dict) else ""
        estimand = str(data.get("estimand", "")).lower() if isinstance(data, dict) else ""
        general = data.get("global_generalization") if isinstance(data, dict) else None
        assumptions = " ".join(map(str, data.get("assumptions", []))).lower() if isinstance(data, dict) else ""
        checks = {
            "fuzzy_rd": "fuzzy" in design and ("regression discontinu" in design or "rd" in design),
            "cutoff_instrument": ("cutoff" in instrument or "eligib" in instrument) and ("70" in instrument or "threshold" in instrument),
            "late_compliers": ("late" in estimand or "local average" in estimand) and "complier" in estimand and ("cutoff" in estimand or "threshold" in estimand),
            "not_global": general is False or str(general).lower() in ("false", "no", "not automatically"),
            "continuity": "continu" in assumptions,
            "no_manipulation": "manipulat" in assumptions or "sorting" in assumptions,
            "exclusion": "exclusion" in assumptions or "only" in assumptions,
            "monotonicity": "monot" in assumptions or "defier" in assumptions,
        }
        weights = {"fuzzy_rd": 3, "cutoff_instrument": 2, "late_compliers": 3, "not_global": 2,
                   "continuity": 1, "no_manipulation": 1, "exclusion": 1, "monotonicity": 1}
        return sum(weights[k] for k, ok in checks.items() if ok), 14, checks

    return "causal_inference", prompt, 360, grade


def task_bayesian_reasoning():
    prompt = '''A condition has 1% prevalence. A test has 90% sensitivity and 95% specificity. A person tests positive. A second test of the same type is then positive; for the numerical calculation assume the two test errors are conditionally independent given true condition status.

Return ONLY JSON with numeric keys `one_positive_percent` and `two_positive_percent`, plus string key `independence_caveat`. Give percentages to within 0.1 percentage point. The caveat must explain why the second calculation may be overconfident in real life.'''

    def grade(text):
        data = extract_json(text)
        one = data.get("one_positive_percent") if isinstance(data, dict) else None
        two = data.get("two_positive_percent") if isinstance(data, dict) else None
        caveat = str(data.get("independence_caveat", "")).lower() if isinstance(data, dict) else ""
        checks = {
            "one_positive": isinstance(one, (int, float)) and math.isclose(float(one), 15.3846, abs_tol=0.1),
            "two_positive": isinstance(two, (int, float)) and math.isclose(float(two), 76.5957, abs_tol=0.1),
            "conditional_independence": "independ" in caveat,
            "correlated_errors": any(x in caveat for x in ("correl", "shared", "systematic", "same")),
        }
        weights = {"one_positive": 4, "two_positive": 4, "conditional_independence": 2, "correlated_errors": 2}
        return sum(weights[k] for k, ok in checks.items() if ok), 12, checks

    return "bayesian_reasoning", prompt, 280, grade


def task_hypothesis_discrimination():
    prompt = '''Three hypotheses might explain why compound X reduces signaling through receptor R:
H1: X directly binds and blocks R.
H2: X causes R protein to be degraded through the proteasome.
H3: The original signaling assay is an artifact.

New observations:
- X has the same effect in an orthogonal signaling assay.
- A validated occupancy assay detects no binding of X to R.
- R protein falls after X treatment, but R mRNA is unchanged.
- A proteasome inhibitor prevents both the R-protein decline and the signaling effect.

Return ONLY JSON with keys `best_hypothesis`, `evidence_chain`, and `decisive_falsifier`. Use one of `direct_block`, `proteasomal_degradation`, or `assay_artifact` for `best_hypothesis`. `evidence_chain` must be an array. State a future result that would decisively undermine the selected mechanism.'''

    def grade(text):
        data = extract_json(text)
        best = data.get("best_hypothesis") if isinstance(data, dict) else None
        evidence = " ".join(map(str, data.get("evidence_chain", []))).lower() if isinstance(data, dict) else ""
        falsifier = str(data.get("decisive_falsifier", "")).lower() if isinstance(data, dict) else ""
        checks = {
            "selects_degradation": best == "proteasomal_degradation",
            "orthogonal_against_artifact": "orthogonal" in evidence and "artifact" in evidence,
            "occupancy_against_direct": ("occupancy" in evidence or "binding" in evidence) and ("direct" in evidence or "h1" in evidence),
            "protein_not_mrna": "protein" in evidence and "mrna" in evidence,
            "inhibitor_rescue": "proteasome" in evidence and any(x in evidence for x in ("prevent", "abolish", "rescue")),
            "valid_falsifier": "proteasome" in falsifier and any(x in falsifier for x in ("despite", "still", "persist", "unchanged", "fails")),
        }
        weights = {"selects_degradation": 4, "orthogonal_against_artifact": 1, "occupancy_against_direct": 2,
                   "protein_not_mrna": 2, "inhibitor_rescue": 2, "valid_falsifier": 1}
        return sum(weights[k] for k, ok in checks.items() if ok), 12, checks

    return "hypothesis_discrimination", prompt, 360, grade


def task_adversarial_epistemology():
    prompt = '''A historian assesses the claim that a mayor secretly diverted famine relief in 1892.

Evidence:
- S1 is an authenticated contemporaneous diary by the mayor's political rival; it makes the accusation but gives no transaction details.
- S2 is a 1920 newspaper article that cites only S1.
- S3 is an independently preserved treasury ledger whose totals reconcile and show the disputed funds paid to named grain suppliers.
- S4 consists of five modern websites that cite S2 or one another, not primary material.
- One supplier named in S3 was the mayor's cousin, but the listed price matches other suppliers that month.

In at most 300 words, assess how belief in the claim should change. Explicitly reason about source dependence, incentives, what S3 does and does not establish, the cousin evidence, and the highest-value next evidence to seek. Avoid a binary certainty claim.'''

    def grade(text):
        s = re.sub(r"[*_`]", "", text.lower())
        checks = {
            "dependency_graph": ("s2" in s and "s1" in s and any(x in s for x in ("depend", "deriv", "cites only"))),
            "websites_not_independent": "s4" in s and any(x in s for x in ("not independent", "copy", "echo", "derivative", "relies", "multiple sources")),
            "rival_incentive": "rival" in s and any(x in s for x in ("motive", "bias", "incentive", "hostil")),
            "ledger_updates_down": "s3" in s and any(x in s for x in ("weaken", "against", "downward", "reduce", "decrease", "diminish", "undercut")),
            "ledger_not_complete_exoneration": "s3" in s and any(x in s for x in ("does not", "cannot", "not prove", "not rule", "still")),
            "cousin_weak_not_zero": "cousin" in s and "price" in s and any(x in s for x in ("weak", "suspici", "not sufficient", "limited")),
            "next_primary_evidence": any(x in s for x in ("bank", "receipt", "invoice", "shipment", "grain", "supplier record", "correspondence")),
        }
        return sum(2 for ok in checks.values() if ok), 14, checks

    return "adversarial_epistemology", prompt, 460, grade


def task_value_of_information():
    prompt = '''A decision maker may launch a project or decline it. The state is Good with probability 0.4 and Bad with probability 0.6. Launch pays +120 in Good and -60 in Bad; declining pays 0.

Before deciding, an optional test costs 10. It returns positive with probability 0.8 in Good and 0.2 in Bad. If purchased, the decision maker may condition the launch decision on the result.

Return ONLY JSON with numeric keys `launch_now_ev`, `positive_probability`, `good_given_positive`, `launch_ev_given_positive`, `launch_ev_given_negative`, `test_policy_ev_after_cost`; string keys `positive_action`, `negative_action`, and `best_initial_policy`. Give probabilities as decimals and expected values to within 0.1.'''

    expected = {
        "launch_now_ev": 12.0,
        "positive_probability": 0.44,
        "good_given_positive": 0.7272727,
        "launch_ev_given_positive": 70.9091,
        "launch_ev_given_negative": -34.2857,
        "test_policy_ev_after_cost": 21.2,
    }

    def grade(text):
        data = extract_json(text)
        checks = {}
        for key, value in expected.items():
            actual = data.get(key) if isinstance(data, dict) else None
            checks[key] = isinstance(actual, (int, float)) and math.isclose(float(actual), value, abs_tol=0.1)
        checks["positive_action"] = isinstance(data, dict) and str(data.get("positive_action", "")).lower() == "launch"
        checks["negative_action"] = isinstance(data, dict) and str(data.get("negative_action", "")).lower() in ("decline", "do not launch", "don't launch")
        checks["best_policy"] = isinstance(data, dict) and "test" in str(data.get("best_initial_policy", "")).lower()
        weights = {k: 1 for k in expected}
        weights.update({"positive_action": 2, "negative_action": 2, "best_policy": 2})
        return sum(weights[k] for k, ok in checks.items() if ok), 12, checks

    return "value_of_information", prompt, 340, grade


def task_wason_selection():
    prompt = '''Four cards show A, D, 4 and 7. Every card has a letter on one side and a number on the other. Test the rule: "If a card has a vowel on one side, then it has an even number on the other side."

Return ONLY JSON with keys `turn_cards` and `reason`. `turn_cards` must be an array containing exactly the cards that must be turned to test the rule. Explain why the other cards are not logically required.'''

    def grade(text):
        data = extract_json(text)
        cards = data.get("turn_cards") if isinstance(data, dict) else None
        if isinstance(cards, list):
            normalized = {str(x).upper() for x in cards}
            exact_card_count = len(cards) == 2
            reason = str(data.get("reason", "") if isinstance(data, dict) else "").lower()
        else:
            # Reasoning models sometimes select the right cards, then exhaust the
            # output budget while explaining them and leave malformed JSON. Recover
            # only the explicit array; do not infer a selection from prose mentions.
            match = re.search(r'"turn_cards"\s*:\s*\[([^\]]+)\]', text, re.I | re.S)
            recovered = re.findall(r'"([^"\\]+)"', match.group(1)) if match else []
            normalized = {x.upper() for x in recovered}
            exact_card_count = len(recovered) == 2
            reason = text.lower()
        checks = {
            "exact_cards": normalized == {"A", "7"} and exact_card_count,
            "a_can_falsify": "a" in reason and any(x in reason for x in ("odd", "fals", "violate")),
            "seven_contrapositive": "7" in reason and any(x in reason for x in ("vowel", "fals", "violate")),
            "four_not_converse": "4" in reason and any(x in reason for x in ("converse", "not require", "may", "irrelevant")),
            "d_irrelevant": "d" in reason and any(x in reason for x in ("consonant", "not constrain", "irrelevant", "no requirement")),
        }
        weights = {"exact_cards": 4, "a_can_falsify": 2, "seven_contrapositive": 2, "four_not_converse": 1, "d_irrelevant": 1}
        return sum(weights[k] for k, ok in checks.items() if ok), 10, checks

    return "wason_selection", prompt, 260, grade


def task_complex_policy():
    prompt = '''A city has a machine-learning system that predicts which released defendants are at high risk of committing a severe violent offense within six months. On historical data it is calibrated within demographic groups, but severe offenses are rare. Police deployment changes who is observed and arrested; defendants can adapt when features become known; the city expects economic and social conditions to shift. Officials propose automatically imposing restrictive supervision whenever predicted risk exceeds a fixed threshold.

In at most 400 words, recommend a policy. Analyze what calibration does and does not justify, base rates and asymmetric errors, causation versus prediction, rights and due process, selective labels/feedback loops, distribution shift and strategic adaptation. Give a concrete deployment/evaluation design with safeguards and conditions for stopping or revising it. A nuanced rejection or constrained use is acceptable; unsupported certainty is not.'''

    def grade(text):
        s = text.lower()
        checks = {
            "prediction_not_causation": "caus" in s and "predict" in s,
            "calibration_limits_base_rates": "calibrat" in s and "base rate" in s,
            "asymmetric_errors": any(x in s for x in ("false positive", "false negative")) and any(x in s for x in ("asym", "cost", "harm", "trade")),
            "rights_due_process": any(x in s for x in ("due process", "appeal", "contest")) and any(x in s for x in ("right", "liberty", "punitive", "automatic")),
            "selective_labels_feedback": ("selective" in s or "feedback" in s) and any(x in s for x in ("observ", "arrest", "polic")),
            "shift_and_adaptation": ("shift" in s or "drift" in s) and any(x in s for x in ("adapt", "gaming", "strateg")),
            "reversible_evaluation": any(x in s for x in ("pilot", "random", "phased")) and any(x in s for x in ("audit", "monitor", "sunset", "stop", "revis")),
        }
        return sum(2 for ok in checks.values() if ok), 14, checks

    return "complex_policy_reasoning", prompt, 620, grade



def task_sizing_hard():
    prompt = '''A hybrid-attention model. Work out its KV cache cost. Return ONLY JSON.

Architecture:
- 48 decoder layers in total.
- 12 of those 48 layers use full attention and cache both K and V.
- The other 36 layers use a linear-attention mechanism whose recurrent state is a
  fixed size that does not grow with sequence length. It contributes nothing to
  the KV cache.
- Each full-attention layer has 8 key/value heads with a head dimension of 128.
  K and V are cached separately.
- The KV cache is quantised to q8_0, which costs 1.0625 bytes per element.
- 1 GiB is 2**30 bytes.

Return exactly these keys:
  "kv_bytes_per_token"        integer, bytes of KV cache per token of context
  "kv_gib_at_262144"          number, GiB of KV cache at 262144 tokens of context
  "max_context_tokens_in_25gib"  integer, the largest context that fits in 25 GiB
                                 of KV cache (round down)
  "weights_87gib_and_262144_fits_in_112gib"  true or false, whether 87 GiB of
                                 weights plus the KV at 262144 tokens fits in 112 GiB
'''

    per_token = 12 * 8 * 128 * 2 * 1.0625
    gib_262144 = per_token * 262144 / (2 ** 30)
    max_ctx = int(25 * (2 ** 30) // per_token)
    fits = (87 + gib_262144) <= 112

    def grade(text):
        data = extract_json(text)
        details = {"expected_bytes_per_token": int(per_token),
                   "expected_gib": round(gib_262144, 3),
                   "expected_max_ctx": max_ctx, "expected_fits": fits}
        if not isinstance(data, dict):
            details["parsed"] = False
            return 0, 16, details
        details["parsed"] = True

        def num(key):
            v = data.get(key)
            return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None

        bpt = num("kv_bytes_per_token")
        details["bytes_per_token"] = bpt is not None and abs(bpt - per_token) <= 1
        gib = num("kv_gib_at_262144")
        details["gib_at_262144"] = gib is not None and abs(gib - gib_262144) <= 0.05
        mc = num("max_context_tokens_in_25gib")
        details["max_context"] = mc is not None and abs(mc - max_ctx) <= max_ctx * 0.01
        details["fits"] = data.get("weights_87gib_and_262144_fits_in_112gib") is fits
        # The trap: charging KV to all 48 layers instead of the 12 that cache it.
        details["counted_all_48_layers"] = bpt is not None and abs(bpt - per_token * 4) <= 4
        score = (6 if details["bytes_per_token"] else 0) + (4 if details["gib_at_262144"] else 0) \
            + (3 if details["max_context"] else 0) + (3 if details["fits"] else 0)
        return score, 16, details

    return "sizing_hard", prompt, 420, grade


def task_causal_medium():
    prompt = '''A causal DAG over observed variables. Arrows are direct causes.

  C -> T      C -> Y
  I -> T
  T -> Y      T -> M      M -> Y
  T -> Z      Y -> Z

You want to estimate the TOTAL causal effect of T on Y from observational data.
Return ONLY JSON with exactly these keys:

  "adjustment_set"        array of variable names, the minimal sufficient set to
                          condition on to identify the total effect; [] if none
                          is needed. Use only C, I, M, Z.
  "conditioning_on_M"     one of "total", "direct", "unchanged" — which effect of
                          T on Y you are left estimating if you also condition on M
  "z_is_collider"         true or false
  "conditioning_on_Z"     one of "removes_bias", "introduces_bias", "no_effect"
  "i_is_instrument"       true or false, whether I is a valid instrument for T
'''

    def grade(text):
        data = extract_json(text)
        details = {}
        if not isinstance(data, dict):
            details["parsed"] = False
            return 0, 18, details
        details["parsed"] = True
        adj = data.get("adjustment_set")
        # C is the only confounder; M is a mediator and Z a collider, so both
        # belong OUT of the set, and I is unnecessary.
        details["adjustment_set"] = (isinstance(adj, list)
                                     and [str(x).strip().upper() for x in adj] == ["C"])
        details["included_mediator_or_collider"] = (
            isinstance(adj, list)
            and bool({str(x).strip().upper() for x in adj} & {"M", "Z"}))
        details["conditioning_on_M"] = str(data.get("conditioning_on_M", "")).strip().lower() == "direct"
        details["z_is_collider"] = data.get("z_is_collider") is True
        details["conditioning_on_Z"] = str(data.get("conditioning_on_Z", "")).strip().lower() == "introduces_bias"
        details["i_is_instrument"] = data.get("i_is_instrument") is True
        score = (5 if details["adjustment_set"] else 0) \
            + (4 if details["conditioning_on_M"] else 0) \
            + (3 if details["z_is_collider"] else 0) \
            + (4 if details["conditioning_on_Z"] else 0) \
            + (2 if details["i_is_instrument"] else 0)
        return score, 18, details

    return "causal_medium", prompt, 460, grade



def task_optimization_medium():
    prompt = '''You have 112 GiB of unified memory and must choose which models stay resident.
Each is all-or-nothing: you cannot load part of one. Maximise total value.

  name       size_gib   value
  atlas         61        67
  borealis      56        60
  cinder        56        60
  dunlin        27        28
  ember         19        19
  fennec        13        12

Return ONLY JSON with exactly these keys:
  "selection"      array of names, the value-maximising set that fits in 112 GiB
  "total_value"    integer, its total value
  "total_size_gib" integer, its total size
  "greedy_by_value_density_total"  integer, the total value you would get by
                   repeatedly taking the model with the highest value-per-GiB
                   that still fits
'''

    # Chosen so greedy-by-value-density is STRICTLY suboptimal (114 against 120):
    # taking atlas first blocks the borealis+cinder pair that exactly fills 112.
    items = {"atlas": (61, 67), "borealis": (56, 60), "cinder": (56, 60),
             "dunlin": (27, 28), "ember": (19, 19), "fennec": (13, 12)}
    names = sorted(items)
    best_value, best_set = -1, None
    for mask in range(1 << len(names)):
        chosen = [names[i] for i in range(len(names)) if mask >> i & 1]
        size = sum(items[c][0] for c in chosen)
        if size <= 112:
            value = sum(items[c][1] for c in chosen)
            if value > best_value:
                best_value, best_set, best_size = value, set(chosen), size
    remaining, greedy_value = 112, 0
    for name in sorted(names, key=lambda n: -items[n][1] / items[n][0]):
        if items[name][0] <= remaining:
            remaining -= items[name][0]
            greedy_value += items[name][1]

    def grade(text):
        data = extract_json(text)
        details = {"expected_value": best_value, "expected_set": sorted(best_set),
                   "expected_greedy": greedy_value}
        if not isinstance(data, dict):
            details["parsed"] = False
            return 0, 16, details
        details["parsed"] = True
        sel = data.get("selection")
        details["selection"] = (isinstance(sel, list)
                                and {str(x).strip().lower() for x in sel} == best_set)
        details["total_value"] = data.get("total_value") == best_value
        details["total_size_gib"] = data.get("total_size_gib") == best_size
        details["greedy_total"] = data.get("greedy_by_value_density_total") == greedy_value
        # The trap: greedy by density is NOT optimal here.
        details["reported_greedy_as_optimal"] = data.get("total_value") == greedy_value
        return ((6 if details["selection"] else 0) + (4 if details["total_value"] else 0)
                + (2 if details["total_size_gib"] else 0)
                + (4 if details["greedy_total"] else 0)), 16, details

    return "optimization_medium", prompt, 460, grade


def task_physics_medium():
    prompt = '''A compute module dissipates heat through a heatsink to still air.

Given:
- Steady-state power draw: 240 W.
- Junction-to-ambient thermal resistance: 0.28 K/W.
- Ambient air: 22 C.
- The module's thermal mass (heat capacity) is 900 J/K.
- Treat the module as a single lumped thermal mass: one temperature, exponential
  approach to steady state, time constant tau = thermal_resistance * heat_capacity.

Return ONLY JSON with exactly these keys:
  "steady_state_junction_c"   number, steady-state junction temperature in C
  "tau_seconds"               number, the thermal time constant in seconds
  "power_for_85c_limit_w"     number, the highest steady power that keeps the
                              junction at or below 85 C in the same ambient
  "junction_after_one_tau_c"  number, junction temperature one time constant after
                              switching on from ambient at the full 240 W
'''

    R, P, AMBIENT, C = 0.28, 240.0, 22.0, 900.0
    steady = AMBIENT + P * R
    tau = R * C
    p_limit = (85.0 - AMBIENT) / R
    after_tau = AMBIENT + (steady - AMBIENT) * (1 - 2.718281828459045 ** -1)

    def grade(text):
        data = extract_json(text)
        details = {"expected_steady_c": round(steady, 2), "expected_tau_s": round(tau, 1),
                   "expected_power_w": round(p_limit, 1),
                   "expected_after_tau_c": round(after_tau, 2)}
        if not isinstance(data, dict):
            details["parsed"] = False
            return 0, 16, details
        details["parsed"] = True

        def close(key, want, tol):
            v = data.get(key)
            ok = isinstance(v, (int, float)) and not isinstance(v, bool) and abs(v - want) <= tol
            details[key] = ok
            return ok

        got = [close("steady_state_junction_c", steady, 0.5),
               close("tau_seconds", tau, 2.0),
               close("power_for_85c_limit_w", p_limit, 2.0),
               close("junction_after_one_tau_c", after_tau, 1.0)]
        # The trap: reporting the RISE above ambient rather than the temperature.
        v = data.get("junction_after_one_tau_c")
        details["gave_rise_not_temperature"] = (
            isinstance(v, (int, float)) and abs(v - (after_tau - AMBIENT)) <= 1.0)
        weights = [5, 4, 4, 3]
        return sum(w for w, ok in zip(weights, got) if ok), 16, details

    return "physics_medium", prompt, 420, grade



def _numeric_grader(expected, tolerances, weights, max_score, traps=None):
    """Shared grader for exact-numeric reasoning tasks."""
    def grade(text):
        data = extract_json(text)
        details = {f"expected_{k}": (round(v, 4) if isinstance(v, float) else v)
                   for k, v in expected.items()}
        if not isinstance(data, dict):
            details["parsed"] = False
            return 0, max_score, details
        details["parsed"] = True
        score = 0
        for key, want in expected.items():
            got = data.get(key)
            if isinstance(want, bool):
                ok = got is want
            elif isinstance(want, (int, float)):
                ok = (isinstance(got, (int, float)) and not isinstance(got, bool)
                      and abs(got - want) <= tolerances[key])
            else:
                ok = str(got).strip().lower() == str(want).strip().lower()
            details[key] = ok
            if ok:
                score += weights[key]
        for name, (key, value, tol) in (traps or {}).items():
            got = data.get(key)
            details[name] = (isinstance(got, (int, float)) and not isinstance(got, bool)
                             and abs(got - value) <= tol)
        return score, max_score, details
    return grade


def task_physics_easy():
    prompt = '''A compute module draws 240 W continuously for 3 hours 30 minutes.

Return ONLY JSON with exactly these keys:
  "energy_kwh"        number, energy consumed in kilowatt-hours
  "cost_usd"          number, cost at 0.28 USD per kWh
  "heat_watts"        number, steady heat dumped into the room, in watts
  "amps_at_240v"      number, current drawn from a 240 V supply
'''
    energy = 240 * 3.5 / 1000
    expected = {"energy_kwh": energy, "cost_usd": energy * 0.28,
                "heat_watts": 240.0, "amps_at_240v": 1.0}
    return ("physics_easy", prompt, 400,
            _numeric_grader(expected,
                            {"energy_kwh": 0.01, "cost_usd": 0.01,
                             "heat_watts": 1.0, "amps_at_240v": 0.02},
                            {"energy_kwh": 4, "cost_usd": 4, "heat_watts": 3,
                             "amps_at_240v": 3}, 14))


def task_physics_hard():
    prompt = '''A compute module sits at thermal equilibrium in a 22 C room drawing 120 W.
Its junction-to-ambient thermal resistance is 0.28 K/W and its lumped heat
capacity is 900 J/K, so the time constant is resistance times capacity.

At t = 0 the load steps to 300 W. The junction temperature rises exponentially
towards the new steady state with that same time constant. Firmware throttles
the moment the junction reaches 95 C.

Return ONLY JSON with exactly these keys:
  "initial_junction_c"     number, junction temperature just before the step
  "target_junction_c"      number, the steady state it is heading towards at 300 W
  "throttles"              true or false, whether it reaches 95 C at all
  "seconds_to_95c"         number, seconds after the step until it hits 95 C;
                           use -1 if it never does
  "sustainable_power_w"    number, the highest constant power that holds the
                           junction at or below 95 C in this ambient
'''
    R, C, AMB = 0.28, 900.0, 22.0
    t0 = AMB + 120 * R
    target = AMB + 300 * R
    tau = R * C
    import math as _math
    throttles = target > 95.0
    t95 = -1.0 if not throttles else tau * _math.log((target - t0) / (target - 95.0))
    expected = {"initial_junction_c": t0, "target_junction_c": target,
                "throttles": throttles, "seconds_to_95c": t95,
                "sustainable_power_w": (95.0 - AMB) / R}
    return ("physics_hard", prompt, 700,
            _numeric_grader(expected,
                            {"initial_junction_c": 0.5, "target_junction_c": 0.5,
                             "throttles": 0, "seconds_to_95c": 8.0,
                             "sustainable_power_w": 2.0},
                            {"initial_junction_c": 3, "target_junction_c": 3,
                             "throttles": 3, "seconds_to_95c": 8,
                             "sustainable_power_w": 3}, 20,
                            # the trap: using the whole tau, or ignoring the
                            # starting temperature and measuring from ambient
                            traps={"used_tau_from_ambient":
                                   ("seconds_to_95c",
                                    tau * _math.log((target - AMB) / (target - 95.0)), 5.0)}))


def task_optimization_easy():
    prompt = '''You must serve one model and have 96 GiB of memory. Pick the highest-quality
option that fits.

  name      size_gib   quality
  alpha        112        95
  bravo         88        91
  charlie       64        86
  delta         32        70

Return ONLY JSON with exactly these keys:
  "choice"           string, the name you pick
  "quality"          integer, its quality score
  "memory_left_gib"  integer, memory remaining after loading it
  "alpha_fits"       true or false
'''
    expected = {"choice": "bravo", "quality": 91, "memory_left_gib": 8,
                "alpha_fits": False}
    return ("optimization_easy", prompt, 400,
            _numeric_grader(expected,
                            {"quality": 0, "memory_left_gib": 0},
                            {"choice": 5, "quality": 3, "memory_left_gib": 3,
                             "alpha_fits": 3}, 14))


def task_optimization_hard():
    prompt = '''Choose which models stay resident. TWO limits bind at once: 112 GiB of
memory AND 260 GB/s of memory bandwidth, shared by everything loaded.

  name      size_gib   bandwidth_gbs   value
  atlas        61            120         67
  borealis     56            140         60
  cinder       56            130         60
  dunlin       27             80         28
  ember        19             70         19
  fennec       13             55         12

A set is feasible only if total size <= 112 AND total bandwidth <= 260.

Return ONLY JSON with exactly these keys:
  "selection"         array of names, the value-maximising feasible set
  "total_value"       integer
  "total_size_gib"    integer
  "total_bandwidth"   integer
  "bandwidth_binds"   true or false, whether the bandwidth limit rules out the
                      set you would have picked on memory alone
'''
    # Tuned so the memory-only optimum (borealis+cinder, 120) is bandwidth
    # INFEASIBLE at 270 GB/s, and the true answer is a different set worth 107.
    # Without that the second constraint never binds and the task is inert.
    items = {"atlas": (61, 120, 67), "borealis": (56, 140, 60), "cinder": (56, 130, 60),
             "dunlin": (27, 80, 28), "ember": (19, 70, 19), "fennec": (13, 55, 12)}
    names = sorted(items)
    best = (-1, None)
    mem_only = (-1, None)
    for mask in range(1 << len(names)):
        chosen = [names[i] for i in range(len(names)) if mask >> i & 1]
        size = sum(items[c][0] for c in chosen)
        band = sum(items[c][1] for c in chosen)
        value = sum(items[c][2] for c in chosen)
        if size <= 112:
            if value > mem_only[0]:
                mem_only = (value, set(chosen))
            if band <= 260 and value > best[0]:
                best = (value, set(chosen), size, band)
    expected = {"total_value": best[0], "total_size_gib": best[2],
                "total_bandwidth": best[3], "bandwidth_binds": mem_only[1] != best[1]}

    def grade(text):
        data = extract_json(text)
        details = {"expected_set": sorted(best[1]), "expected_value": best[0],
                   "expected_bandwidth": best[3],
                   "memory_only_optimum": sorted(mem_only[1])}
        if not isinstance(data, dict):
            details["parsed"] = False
            return 0, 22, details
        details["parsed"] = True
        sel = data.get("selection")
        details["selection"] = (isinstance(sel, list)
                                and {str(x).strip().lower() for x in sel} == best[1])
        details["total_value"] = data.get("total_value") == best[0]
        details["total_size_gib"] = data.get("total_size_gib") == best[2]
        details["total_bandwidth"] = data.get("total_bandwidth") == best[3]
        details["bandwidth_binds"] = data.get("bandwidth_binds") is expected["bandwidth_binds"]
        # the trap: optimising on memory alone and ignoring bandwidth
        details["ignored_bandwidth"] = (isinstance(sel, list)
                                        and {str(x).strip().lower() for x in sel} == mem_only[1])
        return ((8 if details["selection"] else 0) + (4 if details["total_value"] else 0)
                + (3 if details["total_size_gib"] else 0)
                + (3 if details["total_bandwidth"] else 0)
                + (4 if details["bandwidth_binds"] else 0)), 22, details

    return "optimization_hard", prompt, 800, grade


def task_causal_easy():
    prompt = '''Ice cream sales and drowning deaths rise and fall together across the year.
Temperature causes both: hot weather drives ice cream sales, and hot weather
drives swimming, which causes drownings. Ice cream does not cause drowning.

Return ONLY JSON with exactly these keys:
  "relationship"        one of "causal", "confounded", "collider" — how ice cream
                        sales and drownings are related
  "confounder"          string, the variable responsible; "none" if there is none
  "adjust_for"          array of variable names to condition on to remove the
                        spurious association; [] if none is needed
  "ice_cream_causes_drowning"   true or false
  "banning_ice_cream_helps"     true or false, whether banning ice cream would
                                reduce drownings
'''

    def grade(text):
        data = extract_json(text)
        details = {}
        if not isinstance(data, dict):
            details["parsed"] = False
            return 0, 14, details
        details["parsed"] = True
        details["relationship"] = str(data.get("relationship", "")).strip().lower() == "confounded"
        details["confounder"] = "temp" in str(data.get("confounder", "")).strip().lower()
        adj = data.get("adjust_for")
        details["adjust_for"] = (isinstance(adj, list) and len(adj) == 1
                                 and "temp" in str(adj[0]).lower())
        details["ice_cream_causes_drowning"] = data.get("ice_cream_causes_drowning") is False
        details["banning_ice_cream_helps"] = data.get("banning_ice_cream_helps") is False
        return ((4 if details["relationship"] else 0) + (3 if details["confounder"] else 0)
                + (3 if details["adjust_for"] else 0)
                + (2 if details["ice_cream_causes_drowning"] else 0)
                + (2 if details["banning_ice_cream_helps"] else 0)), 14, details

    return "causal_easy", prompt, 400, grade


def task_causal_hard():
    prompt = '''Smoking (T) causes tar deposits in the lungs (M), and tar causes cancer (Y).
An unobserved genetic factor (U) causes both smoking and cancer directly. U is
NOT measured and never will be. The only arrows are:

  U -> T      U -> Y
  T -> M      M -> Y

There is no direct T -> Y arrow: smoking affects cancer only through tar.

You want the causal effect of T on Y from observational data on T, M and Y only.

Return ONLY JSON with exactly these keys:
  "backdoor_identifiable"   true or false, whether a backdoor adjustment set
                            exists among the OBSERVED variables
  "frontdoor_identifiable"  true or false
  "frontdoor_mediator"      string, the variable playing the mediator role;
                            "none" if the front-door criterion does not apply
  "adjust_for_m_directly"   one of "correct", "biased" — what you get if you
                            simply condition on M and read off the T-Y association
  "effect_identifiable"     true or false, whether the causal effect of T on Y
                            can be identified at all from T, M, Y
'''

    def grade(text):
        data = extract_json(text)
        details = {}
        if not isinstance(data, dict):
            details["parsed"] = False
            return 0, 20, details
        details["parsed"] = True
        # U is unobserved, so no backdoor set exists among T, M, Y; but the
        # front-door criterion applies through M, so the effect IS identifiable.
        details["backdoor_identifiable"] = data.get("backdoor_identifiable") is False
        details["frontdoor_identifiable"] = data.get("frontdoor_identifiable") is True
        details["frontdoor_mediator"] = str(data.get("frontdoor_mediator", "")).strip().upper() == "M"
        details["adjust_for_m_directly"] = str(data.get("adjust_for_m_directly", "")).strip().lower() == "biased"
        details["effect_identifiable"] = data.get("effect_identifiable") is True
        # the trap: concluding that unobserved confounding makes it hopeless
        details["said_unidentifiable"] = data.get("effect_identifiable") is False
        return ((4 if details["backdoor_identifiable"] else 0)
                + (5 if details["frontdoor_identifiable"] else 0)
                + (4 if details["frontdoor_mediator"] else 0)
                + (3 if details["adjust_for_m_directly"] else 0)
                + (4 if details["effect_identifiable"] else 0)), 20, details

    return "causal_hard", prompt, 700, grade


def task_sizing_easy():
    prompt = '''A transformer with standard grouped-query attention. Work out its KV cache.

  - 32 layers, every layer caches both K and V.
  - 8 key/value heads per layer, head dimension 128.
  - KV stored in fp16: 2 bytes per element.
  - 1 GiB = 2**30 bytes.

Return ONLY JSON with exactly these keys:
  "kv_bytes_per_token"   integer
  "kv_gib_at_8192"       number, GiB of KV cache at 8192 tokens
  "kv_gib_at_131072"     number, GiB at 131072 tokens
'''
    per = 32 * 8 * 128 * 2 * 2
    expected = {"kv_bytes_per_token": per,
                "kv_gib_at_8192": per * 8192 / 2 ** 30,
                "kv_gib_at_131072": per * 131072 / 2 ** 30}
    return ("sizing_easy", prompt, 400,
            _numeric_grader(expected,
                            {"kv_bytes_per_token": 1, "kv_gib_at_8192": 0.02,
                             "kv_gib_at_131072": 0.05},
                            {"kv_bytes_per_token": 6, "kv_gib_at_8192": 4,
                             "kv_gib_at_131072": 4}, 14,
                            # the trap: forgetting that BOTH K and V are cached
                            traps={"cached_k_only": ("kv_bytes_per_token", per / 2, 1)}))


def task_sizing_medium():
    prompt = '''Size this model against a 48 GiB budget.

  - Weights: 24.5 GiB.
  - 40 layers, every layer caches K and V.
  - 8 key/value heads per layer, head dimension 128.
  - The KV cache is quantised to q8_0, which costs 1.0625 bytes per element.
  - Four concurrent sequences are served, EACH needing its own full-length cache.
  - 1 GiB = 2**30 bytes.

Return ONLY JSON with exactly these keys:
  "kv_bytes_per_token"      integer, per token for ONE sequence
  "gib_per_sequence_at_32768"  number, GiB for one sequence at 32768 tokens
  "total_gib_at_32768"      number, weights plus all four sequences at 32768
  "max_context_per_sequence"  integer, the largest per-sequence context where
                            weights plus four sequences still fits in 48 GiB
                            (round down)
'''
    per = 40 * 8 * 128 * 2 * 1.0625
    one = per * 32768 / 2 ** 30
    total = 24.5 + 4 * one
    max_ctx = int((48 - 24.5) * 2 ** 30 / (4 * per))
    expected = {"kv_bytes_per_token": int(per),
                "gib_per_sequence_at_32768": one,
                "total_gib_at_32768": total,
                "max_context_per_sequence": max_ctx}
    return ("sizing_medium", prompt, 600,
            _numeric_grader(expected,
                            {"kv_bytes_per_token": 1, "gib_per_sequence_at_32768": 0.05,
                             "total_gib_at_32768": 0.2,
                             "max_context_per_sequence": max_ctx * 0.01},
                            {"kv_bytes_per_token": 5, "gib_per_sequence_at_32768": 4,
                             "total_gib_at_32768": 4, "max_context_per_sequence": 5}, 18,
                            # the trap: sizing one sequence and forgetting the four
                            traps={"forgot_four_sequences":
                                   ("total_gib_at_32768", 24.5 + one, 0.2)}))


def tasks(extended=False):
    return [
        task_logic_grid(), task_causal_inference(), task_bayesian_reasoning(),
        task_hypothesis_discrimination(), task_adversarial_epistemology(),
        task_value_of_information(), task_wason_selection(), task_complex_policy(),
    ] + ([
        # easy: can the model do the everyday version at all
        task_physics_easy(), task_optimization_easy(),
        task_causal_easy(), task_sizing_easy(),
        # medium: the original extended set, repositioned by measured difficulty
        task_physics_medium(), task_optimization_medium(),
        task_causal_medium(), task_sizing_medium(),
        # hard: multi-step derivations with a trap that punishes the obvious route
        task_physics_hard(), task_optimization_hard(),
        task_causal_hard(), task_sizing_hard(),
    ] if extended else [])




def _cost_summary(results, wall_s):
    """Token and time totals for the run.

    Score alone does not say what a model costs to reach it. A model that scores
    two points higher while generating four times the tokens at a third the
    speed is not obviously the better choice, and on a bandwidth-bound box that
    difference is minutes per task. Recorded per suite so it can be compared
    across models and machines.
    """
    prompt = completion = 0
    task_seconds = 0.0
    truncated = []
    retries = 0
    retry_completion = 0
    for row in results:
        usage = row.get("usage") or {}
        prompt += usage.get("prompt_tokens") or 0
        completion += usage.get("completion_tokens") or 0
        task_seconds += row.get("elapsed_s") or 0.0
        if "score_retry" in row:
            retries += 1
            retry_usage = row.get("retry_usage") or {}
            prompt += retry_usage.get("prompt_tokens") or 0
            completion += retry_usage.get("completion_tokens") or 0
            retry_completion += retry_usage.get("completion_tokens") or 0
            task_seconds += row.get("retry_elapsed_s") or 0.0
        if usage.get("completion_tokens") and row.get("max_tokens") \
                and usage["completion_tokens"] >= row["max_tokens"]:
            truncated.append(row["task"])
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
        "task_seconds": round(task_seconds, 2),
        "wall_seconds": round(wall_s, 2),
        "generation_tok_s": round(completion / task_seconds, 2) if task_seconds else None,
        # A task that hit its ceiling did not finish its answer, so its score is a
        # measurement of the budget rather than of the model.
        "truncated_tasks": truncated,
        # what the do-overs cost, so the repair capability can be weighed
        # against the tokens and seconds it takes
        "retries": retries,
        "retry_completion_tokens": retry_completion,
    }


def _json_safe(value):
    """Coerce grader details into JSON-serialisable types.

    numpy_backprop's grader compares numpy scalars, so a detail can end up as
    np.bool_ or np.float64. Neither is JSON-serialisable, and because the results
    are written only after every task has run, one such value discards the whole
    suite at the final step — 14 tasks of work lost to the last line.
    """
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return _json_safe(item())
        except Exception:
            pass
    return str(value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--key-file", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument(
        "--no-template-kwargs", action="store_true",
        help="omit chat_template_kwargs; required for Mistral-tokenizer models, "
             "which reject it with HTTP 400",
    )
    parser.add_argument(
        "--strip-reasoning", action="store_true",
        help="drop everything through the final </think> before grading; for "
             "servers that leave chain-of-thought in message.content instead of "
             "message.reasoning_content. Off by default so recorded results stay "
             "comparable",
    )
    parser.add_argument(
        "--extended", action="store_true",
        help="append the harder tasks. The eight default tasks are saturating — "
             "strict_protocol_json has scored full marks in every run ever "
             "recorded — so the suite increasingly discriminates only by the "
             "occasional zero. Extended tasks are exactly or executably graded, "
             "never keyword-rubric. Changes the denominator, so extended results "
             "are comparable only with other extended results",
    )
    parser.add_argument(
        "--retry", action="store_true",
        help="give every imperfect task ONE do-over with the raw checker output",
    )
    parser.add_argument(
        "--retry-credit", type=float, default=0.7, metavar="F",
        help="fraction of full marks a successful retry earns (default 0.7)",
    )
    parser.add_argument(
        "--min-tokens", type=int, default=MIN_TOKEN_BUDGET, metavar="N",
        help=f"floor on every task's max_tokens (default {MIN_TOKEN_BUDGET}). The "
             "per-task budgets are sized for a direct answer and truncate chatty "
             "or thinking models, turning a good answer into a zero. Lower it only "
             "to reproduce an older run",
    )
    parser.add_argument(
        "--token-budget-scale", type=float, default=1.0, metavar="N",
        help="multiply every task's max_tokens by N. The budgets are sized for a "
             "direct answer; a model that thinks first spends them on the thinking "
             "and is cut off before answering, scoring 0 for a mechanical reason. "
             "Raising them makes results incomparable with those recorded at 1.0, "
             "so a thinking-on run must be paired with a thinking-off run at the "
             "same scale",
    )
    args = parser.parse_args()
    key = next(line.strip() for line in Path(args.key_file).read_text().splitlines() if line.strip())
    results = []
    suite_started = time.monotonic()
    for name, prompt, max_tokens, grader in tasks(args.extended):
        print(f"running {name}...", flush=True)
        _score, maximum, _details = grader("")
        budget = max(args.min_tokens, round(max_tokens * args.token_budget_scale))
        try:
            text, usage, elapsed = request(
                args.url, key, args.model, prompt, budget,
                template_kwargs=not args.no_template_kwargs,
                strip_reasoning=args.strip_reasoning,
            )
            score, maximum, details = grader(text)
            row = {"task": name, "score": score, "max_score": maximum,
                   "elapsed_s": round(elapsed, 4), "max_tokens": budget,
                   "usage": usage,
                   "response": text, "grade_details": details}
            if args.retry and score < maximum:
                row["score_first"] = score
                row["retry_feedback"] = failure_report(details)
                try:
                    rt, ru, re_s = request(
                        args.url, key, args.model, prompt, budget,
                        template_kwargs=not args.no_template_kwargs,
                        strip_reasoning=args.strip_reasoning,
                        history=[{"role": "assistant", "content": text},
                                 {"role": "user",
                                  "content": RETRY_INSTRUCTION + row["retry_feedback"]}])
                    rs, _, rd = grader(rt)
                    row["score_retry"] = rs
                    row["retry_usage"] = ru
                    row["retry_elapsed_s"] = round(re_s, 4)
                    row["retry_response"] = rt
                    row["retry_grade_details"] = rd
                    credited = int(round(rs * args.retry_credit))
                    if credited > score:
                        row["score"] = credited
                        row["grade_details"] = rd
                except Exception as exc:
                    row["retry_error"] = f"{type(exc).__name__}: {exc}"
        except Exception as exc:
            row = {"task": name, "score": 0, "max_score": maximum,
                   "error": f"{type(exc).__name__}: {exc}", "response": "", "grade_details": {}}
        results.append(row)
        print(json.dumps({k: row[k] for k in row if k in ("task", "score", "max_score", "elapsed_s", "error")}), flush=True)
    output = {"suite": ("deep_reasoning_v1+hard" if args.extended else "deep_reasoning_v1")
              + ("+retry" if args.retry else ""), "model": args.model, "endpoint": args.url,
              "score": sum(x["score"] for x in results),
              "max_score": sum(x["max_score"] for x in results),
              "cost": _cost_summary(results, time.monotonic() - suite_started),
              "tasks": results}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(_json_safe(output), indent=2) + "\n")
    print(json.dumps({"model": args.model, "score": output["score"],
                      "max_score": output["max_score"], "output": args.output}))


if __name__ == "__main__":
    main()
