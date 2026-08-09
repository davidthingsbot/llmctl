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


def extract_json(text: str):
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except Exception:
            return None


def request(
    url: str, key: str, model: str, prompt: str, max_tokens: int,
    template_kwargs: bool = True,
):
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Solve the reasoning problem carefully. State only conclusions supported by the "
                    "given evidence, distinguish assumptions from deductions, and obey the requested format."
                ),
            },
            {"role": "user", "content": prompt},
        ],
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
    with urllib.request.urlopen(req, timeout=900) as response:
        data = json.load(response)
    return data["choices"][0]["message"]["content"], data.get("usage", {}), time.monotonic() - started


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


def tasks():
    return [
        task_logic_grid(), task_causal_inference(), task_bayesian_reasoning(),
        task_hypothesis_discrimination(), task_adversarial_epistemology(),
        task_value_of_information(), task_wason_selection(), task_complex_policy(),
    ]


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
    args = parser.parse_args()
    key = next(line.strip() for line in Path(args.key_file).read_text().splitlines() if line.strip())
    results = []
    for name, prompt, max_tokens, grader in tasks():
        print(f"running {name}...", flush=True)
        _score, maximum, _details = grader("")
        try:
            text, usage, elapsed = request(
                args.url, key, args.model, prompt, max_tokens,
                template_kwargs=not args.no_template_kwargs,
            )
            score, maximum, details = grader(text)
            row = {"task": name, "score": score, "max_score": maximum,
                   "elapsed_s": round(elapsed, 4), "usage": usage,
                   "response": text, "grade_details": details}
        except Exception as exc:
            row = {"task": name, "score": 0, "max_score": maximum,
                   "error": f"{type(exc).__name__}: {exc}", "response": "", "grade_details": {}}
        results.append(row)
        print(json.dumps({k: row[k] for k in row if k in ("task", "score", "max_score", "elapsed_s", "error")}), flush=True)
    output = {"suite": "deep_reasoning_v1", "model": args.model, "endpoint": args.url,
              "score": sum(x["score"] for x in results),
              "max_score": sum(x["max_score"] for x in results), "tasks": results}
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"model": args.model, "score": output["score"],
                      "max_score": output["max_score"], "output": args.output}))


if __name__ == "__main__":
    main()
