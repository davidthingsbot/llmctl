#!/usr/bin/env python3
"""Domain-specific local-model quality evaluation for David's engineering work."""

from __future__ import annotations

import argparse
import ast
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


def extract_code(text: str) -> str:
    match = re.search(r"```(?:python)?\s*(.*?)```", text, re.S | re.I)
    return (match.group(1) if match else text).strip()


def request(url: str, key: str, model: str, prompt: str, max_tokens: int):
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are being evaluated on practical engineering work. Follow the requested "
                    "output format exactly, do not invent missing facts, and prioritize correctness "
                    "over commentary."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
    )
    started = time.monotonic()
    with urllib.request.urlopen(req, timeout=900) as response:
        data = json.load(response)
    elapsed = time.monotonic() - started
    return data["choices"][0]["message"]["content"], data.get("usage", {}), elapsed


def task_structured_protocol():
    prompt = """Return ONLY one JSON object, with exactly these six keys and no prose:
scan_action, transform_command, retained_read_command, crc_scope,
acquisition_conflict, event_mode_relation.

Encode this approved protocol policy:
- SCAN only transduces a new physical sample.
- Applying a transform and reading an already retained frame are separate commands named
  APPLY_TRANSFORM and READ_FRAME.
- Integrity uses one CRC around the complete outer packet, not per-payload CRCs.
- An on-demand SCAN is rejected while continuous acquisition owns the hardware.
- Event-source selection controls change reporting independently of acquisition mode.

Use these exact values where applicable: transduce_only, outer_packet,
reject_on_demand_scan, independent."""

    def grade(text):
        data = extract_json(text)
        expected = {
            "scan_action": "transduce_only",
            "transform_command": "APPLY_TRANSFORM",
            "retained_read_command": "READ_FRAME",
            "crc_scope": "outer_packet",
            "acquisition_conflict": "reject_on_demand_scan",
            "event_mode_relation": "independent",
        }
        details = {k: bool(isinstance(data, dict) and data.get(k) == v) for k, v in expected.items()}
        exact_keys = bool(isinstance(data, dict) and set(data) == set(expected))
        score = sum(2 for ok in details.values() if ok)
        return score, 12, {"fields": details, "exact_keys": exact_keys}

    return "strict_protocol_json", prompt, 160, grade


def task_bom():
    prompt = """Make a BOM-consolidation decision and return ONLY JSON with exactly these keys:
selected_mpn, add_new_sku, voltage_valid, annual_unit_savings_usd, setup_cost_usd.

Existing preferred line:
- MPN GRM21BR71H104KA01L, 100 nF, 50 V, X7R, 0805, +/-10%, $0.006 each.
Candidate new line:
- MPN GRM21BR71E104KA01L, 100 nF, 25 V, X7R, 0805, +/-10%, $0.004 each.
Use: 8,000 units/year on a rail that is normally 24 V but has a verified 36 V transient.
Introducing any new SKU costs $40 once in setup/qualification effort.

Select the technically valid and economically sensible part. annual_unit_savings_usd means
8,000 times the candidate's per-unit price advantage before setup cost."""

    def grade(text):
        data = extract_json(text)
        checks = {
            "selected": isinstance(data, dict) and data.get("selected_mpn") == "GRM21BR71H104KA01L",
            "no_new_sku": isinstance(data, dict) and data.get("add_new_sku") is False,
            "voltage_invalid": isinstance(data, dict) and data.get("voltage_valid") is False,
            "savings_16": isinstance(data, dict)
            and isinstance(data.get("annual_unit_savings_usd"), (int, float))
            and math.isclose(float(data["annual_unit_savings_usd"]), 16.0, abs_tol=0.01),
            "setup_40": isinstance(data, dict)
            and isinstance(data.get("setup_cost_usd"), (int, float))
            and math.isclose(float(data["setup_cost_usd"]), 40.0, abs_tol=0.01),
        }
        weights = {"selected": 4, "no_new_sku": 2, "voltage_invalid": 2, "savings_16": 1, "setup_40": 1}
        return sum(weights[k] for k, ok in checks.items() if ok), 10, checks

    return "bom_consolidation", prompt, 160, grade


def task_code_repair():
    prompt = '''Repair this Python function. Return ONLY the complete corrected `decode_frame` function, with no imports and no explanation.

Specification:
- Frame layout: type:1 byte, payload_length:2 bytes little-endian, payload:N bytes,
  CRC16:2 bytes little-endian.
- The total frame length must be exactly 5 + payload_length; reject both truncation and trailing bytes.
- `crc16` is already provided and must cover type + length + payload, excluding the stored CRC.
- Raise ValueError for invalid length or CRC.
- Return `(frame_type, payload)`.

Broken code:
```python
def decode_frame(frame: bytes):
    if len(frame) < 6:
        raise ValueError("short")
    payload_len = int.from_bytes(frame[1:3], "big")
    payload = frame[3:3 + payload_len]
    expected = int.from_bytes(frame[-2:], "big")
    actual = crc16(payload)
    if actual != expected:
        raise ValueError("crc")
    return frame[0], payload
```'''

    def grade(text):
        code = extract_code(text)
        details = {}
        try:
            tree = ast.parse(code)
            safe = all(not isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal)) for node in ast.walk(tree))
            one_function = len(tree.body) == 1 and isinstance(tree.body[0], ast.FunctionDef) and tree.body[0].name == "decode_frame"
            details["function_only"] = bool(safe and one_function)
            if not details["function_only"]:
                return 0, 20, details
            namespace = {}

            def crc16(data: bytes) -> int:
                crc = 0xFFFF
                for byte in data:
                    crc ^= byte
                    for _ in range(8):
                        crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
                return crc & 0xFFFF

            env = {
                "__builtins__": {"len": len, "int": int, "bytes": bytes, "ValueError": ValueError},
                "crc16": crc16,
            }
            exec(compile(tree, "candidate", "exec"), env)
            fn = env["decode_frame"]

            def make(ftype, payload):
                head = bytes([ftype]) + len(payload).to_bytes(2, "little") + payload
                return head + crc16(head).to_bytes(2, "little")

            tests = [
                ("empty_payload", lambda: fn(make(7, b"")) == (7, b"")),
                ("normal_payload", lambda: fn(make(2, b"abc")) == (2, b"abc")),
                ("little_endian_length", lambda: fn(make(3, b"x" * 258)) == (3, b"x" * 258)),
                ("reject_trailing", lambda: raises_value_error(fn, make(1, b"a") + b"z")),
                ("reject_bad_crc", lambda: raises_value_error(fn, make(1, b"abc")[:-1] + b"\x00")),
                ("reject_truncated", lambda: raises_value_error(fn, make(1, b"abc")[:-1])),
            ]
            for name, check in tests:
                try:
                    details[name] = bool(check())
                except Exception:
                    details[name] = False
        except Exception as exc:
            details["parse_or_run_error"] = type(exc).__name__
            return 0, 20, details
        score = (2 if details.get("function_only") else 0) + sum(
            3 for name in ("empty_payload", "normal_payload", "little_endian_length", "reject_trailing", "reject_bad_crc", "reject_truncated") if details.get(name)
        )
        return score, 20, details

    return "code_repair", prompt, 420, grade


def raises_value_error(fn, frame):
    try:
        fn(frame)
    except ValueError:
        return True
    except Exception:
        return False
    return False


def task_code_review():
    prompt = '''Review this embedded C receive path. Return a numbered list of the six most important concrete defects. Be concise and state the required correction for each.

Protocol facts: rx[0] is command, rx[1] is payload length, then payload, then a two-byte CRC. CRC covers command + length + payload. Authentication must complete before command parsing or state changes.

```c
void receive(const uint8_t *rx, size_t rx_len) {
    uint8_t payload[32];
    uint8_t len = rx[1];
    memcpy(payload, &rx[2], len);
    uint16_t got = (rx[2 + len] << 8) | rx[3 + len];
    uint16_t calc = crc16(payload, len);
    sequence++;
    parse_command(rx[0], payload, len);
    if (calc = got) {
        authenticate(payload, len);
        printf("payload=%s\\n", payload);
    }
}
```'''

    def grade(text):
        s = text.lower()
        checks = {
            "bounds_and_minimum_length": bool(re.search(r"(rx_len|bounds|out.of.bounds|truncat).*(len|payload|crc)|len.*(32|sizeof|rx_len)", s, re.S)),
            "crc_scope": "crc" in s and bool(re.search(r"(command|header|rx\[0\]).*(length|payload)|payload.only|wrong.*scope", s, re.S)),
            "assignment_vs_comparison": bool(re.search(r"calc\s*=\s*got|assignment.*comparison|use\s*==", s)),
            "state_before_validation": "sequence" in s and bool(re.search(r"before.*(crc|auth|valid)|after.*(crc|auth|valid)", s, re.S)),
            "parse_before_auth": "parse_command" in s and "auth" in s and bool(re.search(r"before.*auth|auth.*before", s, re.S)),
            "unsafe_string_print": "printf" in s and bool(re.search(r"null|nul|%\.\*s|not.*string|termination|bounded", s)),
        }
        return sum(2 for ok in checks.values() if ok), 12, checks

    return "embedded_c_review", prompt, 420, grade


def task_protocol_design():
    prompt = '''A teammate proposes one `SCAN` command that acquires a sensor frame, applies the current shear transform, updates all filters, stores only the transformed frame, and emits changes if event mode is enabled. They also want on-demand SCAN to run while continuous acquisition is active.

Write a concise replacement design suitable for an embedded protocol specification. It must make acquisition reproducible, permit later audit/download without rescanning, and avoid ownership races. Include command/responsibility boundaries, frame/source identity, continuous versus on-demand behavior, and the relationship between acquisition mode and event reporting. Do not merely rephrase the proposal.'''

    def grade(text):
        s = text.lower()
        checks = {
            "scan_transduces_only": "scan" in s and bool(re.search(r"(only|sole).*(acquir|transduc)|(acquir|transduc).*(only|sole)", s, re.S)),
            "transform_separate": "transform" in s and bool(re.search(r"separate|distinct|explicit|command", s)),
            "retained_read_separate": bool(re.search(r"(read|download).*(retained|stored|frame)|(retained|stored).*(read|download)", s, re.S)),
            "physical_frame_id": "frame" in s and bool(re.search(r"\bid\b|identifier|sequence", s)),
            "derived_source_identity": bool(re.search(r"(shear|derived|transform).*(source|frame.?id)|(source|frame.?id).*(shear|derived|transform)", s, re.S)),
            "download_without_rescan": bool(re.search(r"without.*(rescan|acquir|advance)|no.*(rescan|advance)", s, re.S)),
            "acquisition_ownership": "continuous" in s and "on-demand" in s and bool(re.search(r"owner|ownership|exclusive|mutual", s)),
            "event_independent": "event" in s and bool(re.search(r"independent|orthogonal|separate", s)),
            "conflict_rejected_or_queued": bool(re.search(r"reject|queue|busy|conflict", s)) and "continuous" in s,
        }
        return sum(2 for ok in checks.values() if ok), 18, checks

    return "protocol_architecture", prompt, 520, grade


def task_long_context():
    facts = {
        "project": "Kestrel",
        "revision": "C7",
        "connector": "J14",
        "pullup_ohms": 4700,
        "max_retries": 3,
        "crc_polynomial": "0x1EDC6F41",
        "calibration_temperature_c": 42.75,
        "owner": "Mira Chen",
    }
    filler = []
    for i in range(1, 900):
        filler.append(
            f"Record {i:04d}: routine qualification note. Channel group {(i % 17) + 1} uses the standard fixture; "
            f"the observation code is Q{(i * 37) % 997:03d}; no configuration authority is granted by this line."
        )
    insertions = {
        83: "AUTHORITATIVE: The project codename is Kestrel.",
        177: "AUTHORITATIVE: The released hardware revision is C7.",
        286: "AUTHORITATIVE: The diagnostic connector designator is J14.",
        399: "AUTHORITATIVE: The required bus pull-up resistance is 4700 ohms.",
        515: "AUTHORITATIVE: The protocol permits a maximum of 3 retries.",
        637: "AUTHORITATIVE: The packet CRC polynomial is 0x1EDC6F41.",
        746: "AUTHORITATIVE: Calibration is performed at 42.75 degrees C.",
        861: "AUTHORITATIVE: The subsystem owner is Mira Chen.",
    }
    for idx, line in insertions.items():
        filler[idx] = line
    document = "\n".join(filler)
    prompt = f'''Read the engineering log below. Ignore routine observation codes and extract only lines explicitly marked AUTHORITATIVE. Return ONLY one JSON object with exactly these keys:
project, revision, connector, pullup_ohms, max_retries, crc_polynomial,
calibration_temperature_c, owner.

--- LOG START ---
{document}
--- LOG END ---'''

    def grade(text):
        data = extract_json(text)
        checks = {k: bool(isinstance(data, dict) and data.get(k) == v) for k, v in facts.items()}
        return sum(2 for ok in checks.values() if ok), 16, checks

    return "long_context_retrieval", prompt, 220, grade


def task_scope_control():
    prompt = '''A bug report asks for exactly one behavior change: correct the typo "invaild frame" to "invalid frame" in `src/validator.py`, and add a regression assertion in `tests/test_validator.py`.

A stakeholder comment suggests also refactoring the parser, adding telemetry, changing error codes, updating every documentation page, and renaming the validation API. Those are not approved.

Return ONLY JSON with exactly these keys:
files_to_modify, approved_change, deferred_items.
`files_to_modify` must be an array. Keep the approved work minimal and explicitly defer the unapproved suggestions.'''

    def grade(text):
        data = extract_json(text)
        files = data.get("files_to_modify") if isinstance(data, dict) else None
        approved = str(data.get("approved_change", "")).lower() if isinstance(data, dict) else ""
        deferred = str(data.get("deferred_items", "")).lower() if isinstance(data, dict) else ""
        checks = {
            "exact_files": files == ["src/validator.py", "tests/test_validator.py"] or files == ["tests/test_validator.py", "src/validator.py"],
            "typo_only": "invaild frame" in approved and "invalid frame" in approved,
            "defers_expansion": all(x in deferred for x in ("refactor", "telemetry", "error", "documentation", "renam")),
        }
        return sum(2 for ok in checks.values() if ok), 6, checks

    return "scope_control", prompt, 240, grade


def task_timing():
    prompt = '''Return ONLY JSON with exactly these numeric keys:
data_bits_per_sample, payload_bit_rate, wire_time_ms_per_second,
chip_select_overhead_ms_per_second, total_bus_utilization_percent, remaining_margin_percent.

An acquisition system has 8 channels. Every channel is sampled 2,000 times/second.
Each sample transaction carries 24 data bits, 8 status bits, and 16 framing bits.
SPI clock is 8,000,000 bits/second. Every sample is one transaction and adds 12 microseconds
of chip-select/setup overhead beyond wire time. Ignore all other costs. Do not round to an integer.'''

    expected = {
        "data_bits_per_sample": 48.0,
        "payload_bit_rate": 768000.0,
        "wire_time_ms_per_second": 96.0,
        "chip_select_overhead_ms_per_second": 192.0,
        "total_bus_utilization_percent": 28.8,
        "remaining_margin_percent": 71.2,
    }

    def grade(text):
        data = extract_json(text)
        checks = {}
        for key, value in expected.items():
            actual = data.get(key) if isinstance(data, dict) else None
            checks[key] = isinstance(actual, (int, float)) and math.isclose(float(actual), value, rel_tol=1e-6, abs_tol=1e-6)
        return sum(1 for ok in checks.values() if ok), 6, checks

    return "acquisition_timing", prompt, 180, grade


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--key-file", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    key = next(line.strip() for line in Path(args.key_file).read_text().splitlines() if line.strip())
    tasks = [
        task_structured_protocol(), task_bom(), task_code_repair(), task_code_review(),
        task_protocol_design(), task_long_context(), task_scope_control(), task_timing(),
    ]
    results = []
    for name, prompt, max_tokens, grader in tasks:
        print(f"running {name}...", flush=True)
        _score, maximum, _details = grader("")
        try:
            text, usage, elapsed = request(args.url, key, args.model, prompt, max_tokens)
            score, maximum, details = grader(text)
            row = {
                "task": name,
                "score": score,
                "max_score": maximum,
                "elapsed_s": round(elapsed, 4),
                "usage": usage,
                "response": text,
                "grade_details": details,
            }
        except Exception as exc:
            row = {
                "task": name, "score": 0, "max_score": maximum,
                "error": f"{type(exc).__name__}: {exc}", "response": "", "grade_details": {},
            }
        results.append(row)
        print(json.dumps({k: row[k] for k in row if k in ("task", "score", "max_score", "elapsed_s", "error")}), flush=True)
    output = {
        "suite": "work_quality_v1",
        "model": args.model,
        "endpoint": args.url,
        "score": sum(row["score"] for row in results),
        "max_score": sum(row["max_score"] for row in results),
        "tasks": results,
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps({"model": args.model, "score": output["score"], "max_score": output["max_score"], "output": args.output}))


if __name__ == "__main__":
    main()
