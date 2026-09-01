#!/usr/bin/env python3
"""Domain-specific local-model quality evaluation for David's engineering work."""

from __future__ import annotations

import argparse
import ast
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
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


def extract_code(text: str) -> str:
    """Strip a markdown code fence, tolerating an unterminated one.

    Two ways this has silently scored a correct answer zero:
    a ```verilog or ```cuda tag (the regex once accepted only python), and a
    reply that OPENS a fence and never closes it — seen 2026-09-01 from
    qwen38-27b-nvfp4 on ml_easy, where correct numpy scored 0/16 because the
    backticks were handed to ast.parse.
    """
    match = re.search(r"```[a-zA-Z0-9_+#-]*\s*(.*?)```", text, re.S | re.I)
    if match:
        return match.group(1).strip()
    # Unterminated fence: drop the opening line and any dangling backticks.
    opened = re.search(r"```[a-zA-Z0-9_+#-]*[ \t]*\r?\n(.*)", text, re.S)
    if opened:
        return opened.group(1).replace("```", "").strip()
    return text.strip()


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
                "You are being evaluated on practical engineering work. Follow the requested "
                "output format exactly, do not invent missing facts, and prioritize correctness "
                "over commentary."
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
    # Mistral-tokenizer models reject this outright ("chat_template is not
    # supported for Mistral tokenizers", HTTP 400). They have no thinking mode
    # to disable, so omitting it is a no-op for them — but it is NOT a no-op for
    # the Qwen models, so it stays on by default to keep results comparable.
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
    elapsed = time.monotonic() - started
    message = data["choices"][0]["message"]
    return (
        _visible_answer(message, strip_reasoning),
        data.get("usage", {}),
        elapsed,
    )


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
bits_per_transaction, bus_bit_rate, wire_time_ms_per_second,
chip_select_overhead_ms_per_second, total_bus_utilization_percent, remaining_margin_percent.

bits_per_transaction is EVERY bit clocked out for one sample: data, status and framing
together. bus_bit_rate is bits_per_transaction times the total samples per second across
all channels.

An acquisition system has 8 channels. Every channel is sampled 2,000 times/second.
Each sample transaction carries 24 data bits, 8 status bits, and 16 framing bits.
SPI clock is 8,000,000 bits/second. Every sample is one transaction and adds 12 microseconds
of chip-select/setup overhead beyond wire time. Ignore all other costs. Do not round to an integer.'''

    expected = {
        "bits_per_transaction": 48.0,
        "bus_bit_rate": 768000.0,
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



def task_cobs_codec():
    prompt = '''Implement COBS (Consistent Overhead Byte Stuffing). Return ONLY the two
complete functions `cobs_encode` and `cobs_decode`, no imports, no explanation.

Encoding removes every zero byte from the payload so 0x00 can delimit frames.

Rules:
- The encoded output contains no zero bytes and never includes the delimiter itself.
- Output is a sequence of groups. Each group is one code byte `n` (1..255) followed
  by `n - 1` non-zero data bytes.
- A code byte `n < 255` means: those `n - 1` data bytes were followed by a zero byte
  in the input, and that zero is consumed by the encoding.
- A code byte of exactly 255 means: 254 data bytes NOT followed by a zero. Encoding
  continues with a new group.
- The empty input encodes to a single byte 0x01.

`cobs_decode` must invert `cobs_encode` exactly, and must raise ValueError on input
that no encoder could have produced (a zero byte anywhere, a group whose data runs
past the end of the input, or a trailing code byte promising bytes that are absent).

Worked examples:
  b""                     -> b"\\x01"
  b"\\x00"                 -> b"\\x01\\x01"
  b"\\x11\\x22\\x00\\x33"      -> b"\\x03\\x11\\x22\\x02\\x33"
  b"\\x11\\x22\\x33\\x44"      -> b"\\x05\\x11\\x22\\x33\\x44"
  b"\\x00\\x11\\x00"          -> b"\\x01\\x02\\x11\\x01"
'''

    def grade(text):
        code = extract_code(text)
        details = {}
        try:
            tree = ast.parse(code)
            safe = all(not isinstance(n, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal))
                       for n in ast.walk(tree))
            names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
            details["functions_only"] = bool(safe and {"cobs_encode", "cobs_decode"} <= names
                                             and all(isinstance(n, ast.FunctionDef) for n in tree.body))
            if not details["functions_only"]:
                return 0, 24, details
            env = {"__builtins__": {"len": len, "int": int, "bytes": bytes, "bytearray": bytearray,
                                    "range": range, "enumerate": enumerate, "ValueError": ValueError,
                                    "IndexError": IndexError, "list": list, "min": min, "max": max}}
            exec(compile(tree, "candidate", "exec"), env)
            enc, dec = env["cobs_encode"], env["cobs_decode"]

            vectors = [
                ("vec_empty", b"", b"\x01"),
                ("vec_single_zero", b"\x00", b"\x01\x01"),
                ("vec_embedded_zero", b"\x11\x22\x00\x33", b"\x03\x11\x22\x02\x33"),
                ("vec_no_zero", b"\x11\x22\x33\x44", b"\x05\x11\x22\x33\x44"),
                ("vec_leading_trailing_zero", b"\x00\x11\x00", b"\x01\x02\x11\x01"),
            ]
            for name, raw, expected in vectors:
                try:
                    details[name] = enc(raw) == expected
                except Exception:
                    details[name] = False

            try:
                details["encode_never_emits_zero"] = all(
                    0 not in enc(bytes(payload)) for payload in
                    (b"", b"\x00" * 300, bytes(range(256)), b"\x00\x01" * 200))
            except Exception:
                details["encode_never_emits_zero"] = False

            # The 254-byte group boundary is where COBS implementations break, but
            # whether a trailing 0x01 group follows an exactly-full 255-group is a
            # genuine convention difference — both forms decode identically. So
            # grade the OVERHEAD BOUND, which every correct encoder satisfies and
            # every mis-grouped one violates: at most one code byte per 254 bytes
            # of run, plus one.
            try:
                details["overhead_bound"] = all(
                    len(enc(p)) <= len(p) + 1 + len(p) // 254
                    for p in (b"\x01" * 253, b"\x01" * 254, b"\x01" * 255,
                              b"\x01" * 508, b"\x01" * 762, bytes(range(1, 256)) * 3))
            except Exception:
                details["overhead_bound"] = False

            # Round-tripping across the boundary catches the off-by-one regardless
            # of which convention the candidate chose.
            try:
                details["boundary_roundtrip"] = all(
                    dec(enc(p)) == p for p in
                    (b"\x01" * 253, b"\x01" * 254, b"\x01" * 255, b"\x01" * 256,
                     b"\x01" * 507, b"\x01" * 508, b"\x01" * 509,
                     b"\x00" + b"\x01" * 254, b"\x01" * 254 + b"\x00"))
            except Exception:
                details["boundary_roundtrip"] = False

            roundtrip = [b"", b"\x00", b"\x00\x00\x00", bytes(range(256)),
                         b"\x01" * 253, b"\x01" * 254, b"\x01" * 255, b"\x01" * 600,
                         b"\x00" + b"\x02" * 254 + b"\x00"]
            try:
                details["roundtrip"] = all(dec(enc(p)) == p for p in roundtrip)
            except Exception:
                details["roundtrip"] = False

            def rejects(data):
                try:
                    dec(data)
                except ValueError:
                    return True
                except Exception:
                    return False
                return False

            details["decode_rejects_zero_byte"] = rejects(b"\x03\x11\x00")
            details["decode_rejects_overrun"] = rejects(b"\x05\x11\x22")
        except Exception as exc:
            details["parse_or_run_error"] = type(exc).__name__
            return 0, 24, details
        vec = sum(2 for k in ("vec_empty", "vec_single_zero", "vec_embedded_zero", "vec_no_zero",
                              "vec_leading_trailing_zero") if details.get(k))
        boundary = sum(3 for k in ("overhead_bound", "boundary_roundtrip") if details.get(k))
        rest = sum(2 for k in ("encode_never_emits_zero", "roundtrip") if details.get(k))
        rej = sum(1 for k in ("decode_rejects_zero_byte", "decode_rejects_overrun") if details.get(k))
        return min(24, vec + boundary + rest + rej + (2 if details.get("functions_only") else 0)), 24, details

    return "cobs_codec", prompt, 1300, grade


def task_stream_reassembler():
    prompt = '''Implement a framing reassembler for a byte stream that arrives in arbitrary
chunks. Return ONLY the complete class `Reassembler`, no imports, no explanation.

Wire format, repeated back to back:
  sync   : 2 bytes, 0xAA 0x55
  length : 2 bytes, little-endian, the payload length in bytes
  payload: `length` bytes
  check  : 1 byte, the XOR of every payload byte (0x00 for an empty payload)

`Reassembler().feed(chunk: bytes) -> list[bytes]` returns the payloads of every
frame completed by that chunk, in order. State carries across calls: a frame may
be split across any number of chunks, including one byte at a time.

Requirements:
- A chunk may contain several whole frames, or none.
- Bytes before a sync word are garbage and are discarded silently.
- A frame whose check byte does not match is discarded, and the stream must
  resync so that a valid frame immediately following it is still returned.
- `length` may be 0. A `length` above 4096 is invalid: discard and resync.
- The payload may itself contain 0xAA 0x55; length governs, not scanning.
- No exceptions: malformed input yields fewer frames, never a raised error.
'''

    def grade(text):
        code = extract_code(text)
        details = {}

        def frame(payload):
            check = 0
            for b in payload:
                check ^= b
            return b"\xaa\x55" + len(payload).to_bytes(2, "little") + payload + bytes([check])

        try:
            tree = ast.parse(code)
            safe = all(not isinstance(n, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal))
                       for n in ast.walk(tree))
            classes = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "Reassembler"]
            details["class_only"] = bool(safe and classes)
            if not details["class_only"]:
                return 0, 24, details
            # __build_class__ and __name__ are what a `class` statement needs; without
            # them the exec raises NameError before any test runs.
            env = {"__name__": "candidate",
                   "__builtins__": {"len": len, "int": int, "bytes": bytes, "bytearray": bytearray,
                                    "range": range, "enumerate": enumerate, "list": list,
                                    "min": min, "max": max, "object": object, "ValueError": ValueError,
                                    "IndexError": IndexError, "slice": slice, "reversed": reversed,
                                    "__build_class__": __build_class__, "__name__": "candidate",
                                    "print": lambda *a, **k: None}}
            exec(compile(tree, "candidate", "exec"), env)
            R = env["Reassembler"]

            def run(chunks):
                r = R()
                got = []
                for c in chunks:
                    got.extend(r.feed(c))
                return got

            checks = {
                "single_frame": lambda: run([frame(b"hello")]) == [b"hello"],
                "empty_payload": lambda: run([frame(b"")]) == [b""],
                "two_frames_one_chunk": lambda: run([frame(b"ab") + frame(b"cd")]) == [b"ab", b"cd"],
                # one byte at a time is where a naive index-based parser falls apart
                "split_byte_by_byte": lambda: run([bytes([b]) for b in frame(b"abcdef")]) == [b"abcdef"],
                "split_across_two_chunks": lambda: (
                    lambda f: run([f[:4], f[4:]]) == [b"payload"])(frame(b"payload")),
                "garbage_before_sync": lambda: run([b"\x01\x02\xaa\x03" + frame(b"ok")]) == [b"ok"],
                # the discriminating case: a corrupt frame must not swallow the next
                "resync_after_bad_check": lambda: (
                    lambda bad: run([bad[:-1] + bytes([bad[-1] ^ 0xFF]) + frame(b"good")]) == [b"good"]
                )(frame(b"bad")),
                "oversize_length_rejected": lambda: run(
                    [b"\xaa\x55" + (5000).to_bytes(2, "little") + b"\x00" * 10 + frame(b"after")]
                ) == [b"after"],
                "payload_containing_sync": lambda: run([frame(b"\xaa\x55\xaa\x55")]) == [b"\xaa\x55\xaa\x55"],
                "no_frame_no_output": lambda: run([b"\x00\x01\x02"]) == [],
                "stateful_across_calls": lambda: (
                    lambda f: run([f[:1], f[1:3], f[3:6], f[6:]]) == [b"chunked"])(frame(b"chunked")),
            }
            for name, check in checks.items():
                try:
                    details[name] = bool(check())
                except Exception:
                    details[name] = False
        except Exception as exc:
            details["parse_or_run_error"] = type(exc).__name__
            return 0, 24, details
        easy = sum(2 for k in ("single_frame", "empty_payload", "two_frames_one_chunk",
                               "garbage_before_sync", "no_frame_no_output") if details.get(k))
        hard = sum(3 for k in ("split_byte_by_byte", "resync_after_bad_check",
                               "payload_containing_sync") if details.get(k))
        mid = sum(1 for k in ("split_across_two_chunks", "oversize_length_rejected",
                              "stateful_across_calls") if details.get(k))
        return min(24, easy + hard + mid + (2 if details.get("class_only") else 0)), 24, details

    return "stream_reassembler", prompt, 900, grade



VERILOG_TESTBENCH = r"""
module tb;
  localparam WIDTH = 8, DEPTH = 4;
  reg clk = 0, rst_n = 0, wr_en = 0, rd_en = 0;
  reg [WIDTH-1:0] din = 0;
  wire [WIDTH-1:0] dout;
  wire full, empty;
  integer pass = 0, fail = 0;

  sync_fifo #(.WIDTH(WIDTH), .DEPTH(DEPTH)) dut
    (.clk(clk), .rst_n(rst_n), .wr_en(wr_en), .din(din),
     .rd_en(rd_en), .dout(dout), .full(full), .empty(empty));

  always #5 clk = ~clk;

  task check(input integer id, input cond);
    begin
      if (cond) begin pass = pass + 1; $display("CHECK %0d PASS", id); end
      else      begin fail = fail + 1; $display("CHECK %0d FAIL", id); end
    end
  endtask

  task push(input [WIDTH-1:0] value);
    begin @(negedge clk); wr_en = 1; din = value; @(negedge clk); wr_en = 0; end
  endtask

  task pop;
    begin @(negedge clk); rd_en = 1; @(negedge clk); rd_en = 0; end
  endtask

  initial begin
    #12 rst_n = 1;
    @(negedge clk);
    check(0, empty === 1'b1 && full === 1'b0);

    push(8'hA1); push(8'hB2); push(8'hC3);
    check(1, full === 1'b0 && empty === 1'b0);
    push(8'hD4);
    check(2, full === 1'b1);

    // A write while full must be ignored, not corrupt the contents.
    push(8'hEE);
    check(3, full === 1'b1);

    pop; check(4, dout === 8'hA1);
    pop; check(5, dout === 8'hB2);
    check(6, full === 1'b0);
    pop; check(7, dout === 8'hC3);
    pop; check(8, dout === 8'hD4);
    check(9, empty === 1'b1);

    // A read while empty must be ignored.
    pop;
    check(10, empty === 1'b1);

    // Pointer wrap-around: the same depth must be usable again.
    push(8'h11); push(8'h22); push(8'h33); push(8'h44);
    check(11, full === 1'b1);
    pop; check(12, dout === 8'h11);
    pop; pop; pop;
    check(13, empty === 1'b1);

    $display("SUMMARY pass=%0d fail=%0d", pass, fail);
    $finish;
  end
endmodule
"""


def task_verilog_medium():
    prompt = '''Write a synchronous FIFO in Verilog-2001. Return ONLY the complete module,
no testbench, no explanation.

module sync_fifo #(parameter WIDTH = 8, parameter DEPTH = 4)
  (input clk, input rst_n,
   input wr_en, input [WIDTH-1:0] din,
   input rd_en, output reg [WIDTH-1:0] dout,
   output full, output empty);

Requirements:
- DEPTH is a power of two. Storage is a register array of DEPTH entries.
- `rst_n` is asynchronous, active low: it empties the FIFO.
- On a clock edge with `wr_en` and not `full`, `din` is stored.
- On a clock edge with `wr_en` while `full`, nothing is written and nothing is corrupted.
- On a clock edge with `rd_en` and not `empty`, the oldest entry appears on `dout`.
- On a clock edge with `rd_en` while `empty`, nothing happens.
- `full` and `empty` must be distinguishable when the read and write pointers are
  equal — that is the whole difficulty.
- Must be synthesisable RTL: non-blocking assignments in sequential blocks, no
  inferred latches, no combinational loops.
'''

    def grade(text):
        code = extract_code(text)
        details = {}
        if "module" not in code or "sync_fifo" not in code:
            details["module_present"] = False
            return 0, 26, details
        details["module_present"] = True
        workdir = tempfile.mkdtemp(prefix="verilog-")
        design = os.path.join(workdir, "sync_fifo.v")
        bench = os.path.join(workdir, "tb.v")
        try:
            with open(design, "w") as handle:
                handle.write(code + "\n")
            with open(bench, "w") as handle:
                handle.write(VERILOG_TESTBENCH)

            if shutil.which("iverilog") and shutil.which("vvp"):
                details["simulator"] = "iverilog"
                build = subprocess.run(["iverilog", "-g2001", "-o",
                                        os.path.join(workdir, "sim"), design, bench],
                                       capture_output=True, text=True, timeout=60)
                details["compiles"] = build.returncode == 0
                if details["compiles"]:
                    run = subprocess.run(["vvp", os.path.join(workdir, "sim")],
                                         capture_output=True, text=True, timeout=60)
                    out = run.stdout
                    labels = ['empty_after_reset', 'not_full_at_three', 'full_at_depth', 'write_while_full_ignored', 'first_out_is_first_in', 'second_out', 'not_full_after_reads', 'third_out', 'fourth_out', 'empty_after_draining', 'read_while_empty_ignored', 'full_after_wrap', 'wrap_first_out', 'empty_after_wrap_drain']
                    for line in out.splitlines():
                        if line.startswith("CHECK "):
                            _, ident, verdict = line.split()
                            if ident.isdigit() and int(ident) < len(labels):
                                details[labels[int(ident)]] = verdict == "PASS"
                    match = re.search(r"SUMMARY pass=(\d+) fail=(\d+)", out)
                    details["ran_to_completion"] = bool(match)
                else:
                    details["compile_error"] = build.stderr.strip().splitlines()[:3]
            else:
                # Absent tooling must be visible, not silently scored as failure.
                details["simulator"] = "absent"

            if shutil.which("verilator"):
                # Stylistic warnings (filename/module mismatch, unused signals) say
                # nothing about correctness; the rest catch RTL that simulates but
                # does not synthesise.
                lint = subprocess.run(
                    ["verilator", "--lint-only", "-Wall", "-Wno-DECLFILENAME", "-Wno-EOFNEWLINE",
                     "-Wno-UNUSEDSIGNAL", "-Wno-UNUSEDPARAM", "-Wno-VARHIDDEN", design],
                    capture_output=True, text=True, timeout=60)
                details["lint_clean"] = lint.returncode == 0
                if not details["lint_clean"]:
                    details["lint_first"] = [l for l in lint.stderr.splitlines()
                                             if l.startswith("%")][:3]
            else:
                details["lint_clean"] = None
        except Exception as exc:
            details["harness_error"] = f"{type(exc).__name__}: {exc}"
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

        if details.get("simulator") == "absent":
            # Structural fallback so a machine without the toolchain still scores
            # something meaningful, flagged so the number is not compared blindly.
            seq = re.search(r"always\s*@\s*\(\s*posedge", code) is not None
            nonblocking = code.count("<=") >= 2
            details["structural_sequential"] = bool(seq and nonblocking)
            return (10 if details["structural_sequential"] else 3), 26, details

        behaviour = sum(1 for k in (
            "empty_after_reset", "not_full_at_three", "full_at_depth",
            "write_while_full_ignored", "first_out_is_first_in", "second_out",
            "not_full_after_reads", "third_out", "fourth_out", "empty_after_draining",
            "read_while_empty_ignored", "full_after_wrap", "wrap_first_out",
            "empty_after_wrap_drain") if details.get(k))
        score = (2 if details.get("compiles") else 0) + behaviour \
            + (4 if details.get("lint_clean") else 0) \
            + (6 if behaviour == 14 else 0)
        return min(26, score), 26, details

    return "verilog_medium", prompt, 900, grade


CUDA_HARNESS = r"""
#include <cstdio>
#include <cstdlib>
#include <cmath>

__CANDIDATE__

int main() {
    const int cases[] = {1, 31, 32, 33, 255, 256, 257, 1000, 4096, 100000};
    const int ncases = sizeof(cases) / sizeof(cases[0]);
    int failures = 0, ran = 0;
    for (int c = 0; c < ncases; ++c) {
        int n = cases[c];
        int threads = 256;
        int blocks = (n + threads - 1) / threads;
        // Allocate a whole number of blocks and POISON everything past n. A kernel
        // that reads out of range then sums poison and is caught; without this the
        // tail is freshly-zeroed memory and an unguarded kernel passes by luck.
        int padded = blocks * threads;
        float *h = (float *)malloc(padded * sizeof(float));
        double expected = 0.0;
        for (int i = 0; i < n; ++i) { h[i] = (float)((i % 7) + 1); expected += h[i]; }
        for (int i = n; i < padded; ++i) h[i] = 1.0e6f;
        float *d_in = 0, *d_out = 0;
        if (cudaMalloc(&d_in, padded * sizeof(float)) != cudaSuccess ||
            cudaMalloc(&d_out, blocks * sizeof(float)) != cudaSuccess) {
            printf("GPU_UNAVAILABLE\n"); free(h); return 3;
        }
        cudaMemcpy(d_in, h, padded * sizeof(float), cudaMemcpyHostToDevice);
        block_sum<<<blocks, threads, threads * sizeof(float)>>>(d_in, d_out, n);
        if (cudaDeviceSynchronize() != cudaSuccess) { printf("GPU_UNAVAILABLE\n"); return 3; }
        float *partial = (float *)malloc(blocks * sizeof(float));
        cudaMemcpy(partial, d_out, blocks * sizeof(float), cudaMemcpyDeviceToHost);
        double got = 0.0;
        for (int b = 0; b < blocks; ++b) got += partial[b];
        ran++;
        if (fabs(got - expected) > 1e-3 * expected + 1e-3) {
            printf("CASE %d FAIL got=%f want=%f\n", n, got, expected);
            failures++;
        } else {
            printf("CASE %d PASS\n", n);
        }
        cudaFree(d_in); cudaFree(d_out); free(h); free(partial);
    }
    printf("SUMMARY ran=%d failures=%d\n", ran, failures);
    return 0;
}
"""



def _barrier_inside_thread_conditional(code):
    """True if a __syncthreads() sits inside a branch guarded by a thread index.

    compute-sanitizer's synccheck does not flag this on Volta-and-later hardware
    — independent thread scheduling makes it usually work — but it is undefined
    behaviour and the classic reduction bug, so it is worth detecting textually.
    """
    for match in re.finditer(r"if\s*\([^)]*\b(?:tid|threadIdx)\b[^)]*\)\s*\{", code):
        depth, i = 0, match.end() - 1
        while i < len(code):
            if code[i] == "{":
                depth += 1
            elif code[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        if "__syncthreads" in code[match.end():i]:
            return True
    return False


def task_cuda_medium():
    prompt = '''Write a CUDA kernel that reduces an array of floats to one partial sum per
block. Return ONLY the kernel, no host code, no main, no includes, no explanation.

    __global__ void block_sum(const float* in, float* out, int n)

Contract:
- Launched as block_sum<<<blocks, threads, threads * sizeof(float)>>>(in, out, n)
  with threads = 256 and blocks = ceil(n / threads).
- Each block sums the elements it is responsible for and writes that single
  partial sum to out[blockIdx.x]. The host adds the partials afterwards.
- `n` is NOT necessarily a multiple of the block size, and may be smaller than one
  block. Out-of-range elements must contribute nothing.
- Use the dynamically allocated shared memory (declare it `extern __shared__`).
- Every thread in the block must reach every __syncthreads(). Placing a barrier
  where only some threads arrive is undefined behaviour, even when it appears to
  work.
'''

    def grade(text):
        code = extract_code(text)
        details = {}
        if "__global__" not in code or "block_sum" not in code:
            details["kernel_present"] = False
            return 0, 26, details
        details["kernel_present"] = True
        if not shutil.which("nvcc"):
            details["nvcc"] = "absent"
            details["uses_shared"] = "__shared__" in code
            details["uses_barrier"] = "__syncthreads" in code
            details["guards_n"] = bool(re.search(r"<\s*n\b", code))
            return (6 if all((details["uses_shared"], details["uses_barrier"],
                              details["guards_n"])) else 2), 26, details

        workdir = tempfile.mkdtemp(prefix="cuda-")
        source = os.path.join(workdir, "candidate.cu")
        binary = os.path.join(workdir, "candidate")
        try:
            with open(source, "w") as handle:
                handle.write(CUDA_HARNESS.replace("__CANDIDATE__", code))
            build = subprocess.run(["nvcc", "-o", binary, source],
                                   capture_output=True, text=True, timeout=300)
            details["compiles"] = build.returncode == 0
            if not details["compiles"]:
                details["compile_error"] = [l for l in build.stderr.splitlines()
                                            if "error" in l.lower()][:3]
                return 0, 26, details
            run = subprocess.run([binary], capture_output=True, text=True, timeout=300)
            out = run.stdout
            if "GPU_UNAVAILABLE" in out or run.returncode == 3:
                # The GPU is busy serving a model. Compilation still proves a lot;
                # flag the gap rather than scoring a correct kernel as broken.
                details["gpu"] = "unavailable"
                details["uses_shared"] = "__shared__" in code
                details["uses_barrier"] = "__syncthreads" in code
                return 10, 26, details
            details["gpu"] = "used"
            for line in out.splitlines():
                if line.startswith("CASE "):
                    parts = line.split()
                    details[f"n_{parts[1]}"] = parts[2] == "PASS"
            match = re.search(r"SUMMARY ran=(\d+) failures=(\d+)", out)
            details["all_cases_pass"] = bool(match and match.group(2) == "0")

            # A __syncthreads() that only some threads reach is undefined behaviour
            # that frequently WORKS on current hardware, so the functional tests
            # cannot see it. synccheck can.
            sanitizer = shutil.which("compute-sanitizer") or "/usr/local/cuda/bin/compute-sanitizer"
            if os.path.exists(sanitizer):
                audit = subprocess.run(
                    [sanitizer, "--tool", "synccheck", "--error-exitcode", "9", binary],
                    capture_output=True, text=True, timeout=600)
                details["barrier_divergence_clean"] = audit.returncode == 0
                if not details["barrier_divergence_clean"]:
                    details["sanitizer_first"] = [
                        l.strip() for l in audit.stdout.splitlines()
                        if "Barrier error" in l or "ERROR SUMMARY" in l][:2]
            else:
                details["barrier_divergence_clean"] = None
        except subprocess.TimeoutExpired:
            details["timeout"] = True
            return 0, 26, details
        except Exception as exc:
            details["harness_error"] = f"{type(exc).__name__}: {exc}"
            return 0, 26, details
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

        cases = sum(1 for key in details if key.startswith("n_") and details[key])
        # The ragged sizes are the discriminating ones: 1, 31, 33, 257, 1000.
        ragged = sum(2 for key in ("n_1", "n_31", "n_33", "n_257", "n_1000")
                     if details.get(key))
        details["barrier_in_thread_conditional"] = _barrier_inside_thread_conditional(code)
        barrier = (2 if details.get("barrier_divergence_clean") else 0) \
            + (2 if not details["barrier_in_thread_conditional"] else 0)
        return min(26, 2 + cases + ragged + barrier), 26, details

    return "cuda_medium", prompt, 700, grade



CPP_ML_HARNESS = r"""
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <vector>

__CANDIDATE__

static int checks_pass = 0, checks_fail = 0;
static void check(const char* name, bool ok) {
    if (ok) { checks_pass++; printf("CHECK %s PASS\n", name); }
    else    { checks_fail++; printf("CHECK %s FAIL\n", name); }
}

int main() {
    const int n_in = 2, n_hidden = 4;
    const int n_params = n_hidden * n_in + n_hidden + n_hidden + 1;

    // XOR: not linearly separable, so a working hidden layer is required.
    double X[8] = {0,0, 0,1, 1,0, 1,1};
    double Y[4] = {0, 1, 1, 0};

    // Deterministic pseudo-random start, no library dependence.
    std::vector<double> p(n_params), g(n_params);
    unsigned s = 12345u;
    for (int i = 0; i < n_params; ++i) {
        s = s * 1664525u + 1013904223u;
        p[i] = ((double)(s >> 8) / 16777216.0) * 2.0 - 1.0;
    }

    double l0 = mlp_loss_and_grad(p.data(), n_in, n_hidden, X, Y, 4, g.data());
    check("loss_is_finite", std::isfinite(l0));
    check("loss_positive", l0 > 0.0);

    // Finite-difference gradient check: the unforgeable part. An analytic
    // gradient that disagrees here is wrong, however plausible the code looks.
    double worst = 0.0;
    for (int i = 0; i < n_params; ++i) {
        const double h = 1e-6;
        double save = p[i];
        std::vector<double> dummy(n_params);
        p[i] = save + h;
        double lp = mlp_loss_and_grad(p.data(), n_in, n_hidden, X, Y, 4, dummy.data());
        p[i] = save - h;
        double lm = mlp_loss_and_grad(p.data(), n_in, n_hidden, X, Y, 4, dummy.data());
        p[i] = save;
        double numeric = (lp - lm) / (2 * h);
        double diff = fabs(numeric - g[i]) / (fabs(numeric) + fabs(g[i]) + 1e-9);
        if (diff > worst) worst = diff;
    }
    printf("GRADCHECK worst_rel_err=%.3e\n", worst);
    check("gradient_matches_numeric", worst < 1e-4);

    // Gradients must be OVERWRITTEN, not accumulated. Passing a fresh vector
    // would not test this — std::vector zero-initialises, so accumulating into
    // it gives the right answer. Reuse the SAME buffer twice instead.
    std::vector<double> g2(n_params);
    mlp_loss_and_grad(p.data(), n_in, n_hidden, X, Y, 4, g2.data());
    mlp_loss_and_grad(p.data(), n_in, n_hidden, X, Y, 4, g2.data());
    bool same = true;
    for (int i = 0; i < n_params; ++i) if (fabs(g2[i] - g[i]) > 1e-9) same = false;
    check("gradients_not_accumulated", same);

    // A single sample must work: n_samples is not assumed to be > 1.
    std::vector<double> g1(n_params);
    double one = mlp_loss_and_grad(p.data(), n_in, n_hidden, X, Y, 1, g1.data());
    check("single_sample_ok", std::isfinite(one) && one > 0.0);

    // Train by plain gradient descent using the candidate's own gradients.
    for (int epoch = 0; epoch < 20000; ++epoch) {
        mlp_loss_and_grad(p.data(), n_in, n_hidden, X, Y, 4, g.data());
        for (int i = 0; i < n_params; ++i) p[i] -= 0.5 * g[i];
    }
    double lfinal = mlp_loss_and_grad(p.data(), n_in, n_hidden, X, Y, 4, g.data());
    printf("TRAIN final_loss=%.6f initial_loss=%.6f\n", lfinal, l0);
    check("loss_decreased", lfinal < l0);
    check("xor_learned", lfinal < 0.05);

    printf("SUMMARY pass=%d fail=%d\n", checks_pass, checks_fail);
    return 0;
}
"""


def task_cpp_medium():
    prompt = '''Implement the forward pass, loss and analytic gradients of a small neural
network in C++, from scratch. Return ONLY the function, no main, no includes, no
explanation. You may not use any library beyond <cmath>.

    double mlp_loss_and_grad(const double* params, int n_in, int n_hidden,
                             const double* X, const double* y, int n_samples,
                             double* grad);

Network, for one input vector x of length n_in:
  h_j    = tanh( sum_k W1[j][k] * x[k] + b1[j] )      for j in 0..n_hidden-1
  z      = sum_j W2[j] * h_j + b2
  p      = 1 / (1 + exp(-z))
  loss   = -( y*log(p) + (1-y)*log(1-p) )

Return the loss AVERAGED over the n_samples, and write d(average loss)/d(param)
into grad[], which the caller has sized correctly.

`params` is one flat array in exactly this order:
  W1  n_hidden * n_in doubles, row-major: W1[j][k] is params[j*n_in + k]
  b1  n_hidden doubles
  W2  n_hidden doubles
  b2  1 double
`grad` uses the identical layout. `X` is n_samples * n_in doubles, row-major;
`y` is n_samples doubles, each 0.0 or 1.0.

Requirements:
- grad[] must be OVERWRITTEN each call, not accumulated across calls.
- n_samples may be 1.
- The gradients must be the true analytic derivatives: they are checked against
  finite differences to a relative tolerance of 1e-4.
'''

    def grade(text):
        code = extract_code(text)
        details = {}
        if "mlp_loss_and_grad" not in code:
            details["function_present"] = False
            return 0, 28, details
        details["function_present"] = True
        if not shutil.which("g++"):
            details["compiler"] = "absent"
            return 4, 28, details
        workdir = tempfile.mkdtemp(prefix="cppml-")
        source = os.path.join(workdir, "candidate.cpp")
        binary = os.path.join(workdir, "candidate")
        try:
            with open(source, "w") as handle:
                handle.write(CPP_ML_HARNESS.replace("__CANDIDATE__", code))
            build = subprocess.run(["g++", "-O2", "-o", binary, source],
                                   capture_output=True, text=True, timeout=180)
            details["compiles"] = build.returncode == 0
            if not details["compiles"]:
                details["compile_error"] = [l for l in build.stderr.splitlines()
                                            if "error" in l.lower()][:3]
                return 0, 28, details
            run = subprocess.run([binary], capture_output=True, text=True, timeout=180)
            out = run.stdout
            for line in out.splitlines():
                if line.startswith("CHECK "):
                    _, name, verdict = line.split()
                    details[name] = verdict == "PASS"
            worst = re.search(r"GRADCHECK worst_rel_err=([0-9.e+-]+)", out)
            if worst:
                details["worst_relative_gradient_error"] = float(worst.group(1))
            final = re.search(r"TRAIN final_loss=([0-9.e+-]+)", out)
            if final:
                details["final_loss"] = float(final.group(1))
        except subprocess.TimeoutExpired:
            details["timeout"] = True
            return 0, 28, details
        except Exception as exc:
            details["harness_error"] = f"{type(exc).__name__}: {exc}"
            return 0, 28, details
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

        score = 3 if details.get("compiles") else 0
        score += sum(2 for k in ("loss_is_finite", "loss_positive",
                                 "gradients_not_accumulated", "single_sample_ok",
                                 "loss_decreased") if details.get(k))
        # The gradient check and actually learning XOR are what separate a real
        # derivation from code that merely runs.
        score += 8 if details.get("gradient_matches_numeric") else 0
        score += 7 if details.get("xor_learned") else 0
        return min(28, score), 28, details

    return "cpp_medium", prompt, 1500, grade


def task_ml_medium():
    prompt = '''Implement a two-layer neural network's forward pass, loss and analytic
gradients with numpy. Return ONLY the two functions, no training loop, no
explanation. `import numpy as np` is the only import permitted.

    def init_params(n_in, n_hidden, seed):
        """Return a dict with keys W1, b1, W2, b2."""

    def loss_and_grads(params, X, y):
        """Return (loss, grads) where grads has the same keys as params."""

Shapes:
  W1 (n_hidden, n_in)   b1 (n_hidden,)   W2 (n_hidden,)   b2 scalar float
  X  (n_samples, n_in)  y  (n_samples,) of 0.0 or 1.0

Network:
  H = tanh(X @ W1.T + b1)          shape (n_samples, n_hidden)
  z = H @ W2 + b2                  shape (n_samples,)
  p = sigmoid(z)
  loss = mean over samples of -( y*log(p) + (1-y)*log(1-p) )

`grads[k]` must be d(loss)/d(params[k]) with the same shape as params[k], and
grads["b2"] a scalar. They are checked against finite differences to a relative
tolerance of 1e-5, so they must be the true analytic derivatives.

`init_params` must be deterministic for a given seed, and must NOT initialise
every weight to the same value — identical hidden units cannot learn different
features. Keep the initial weights small.
'''

    def grade(text):
        code = extract_code(text)
        details = {}
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            details["parse_error"] = str(exc)
            return 0, 26, details
        allowed_import = True
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                allowed_import &= all(a.name == "numpy" for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                allowed_import &= node.module == "numpy"
        details["only_numpy_imported"] = allowed_import
        if not allowed_import:
            return 0, 26, details
        names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
        details["both_functions"] = {"init_params", "loss_and_grads"} <= names
        if not details["both_functions"]:
            return 0, 26, details
        try:
            import numpy as np
        except ImportError:
            details["numpy"] = "absent"
            return 3, 26, details

        # numpy is permitted, not required: "return ONLY the two functions" is
        # reasonably read as omitting the import line, so provide np ourselves.
        env = {"__name__": "candidate", "np": np, "numpy": np}
        try:
            exec(compile(tree, "candidate", "exec"), env)
            init, lag = env["init_params"], env["loss_and_grads"]

            rng = np.random.RandomState(0)
            n_in, n_hidden, n = 3, 5, 12
            X = rng.randn(n, n_in)
            y = (rng.rand(n) > 0.5).astype(float)

            p0 = init(n_in, n_hidden, 0)
            p1 = init(n_in, n_hidden, 0)
            p2 = init(n_in, n_hidden, 1)
            details["shapes"] = (np.shape(p0["W1"]) == (n_hidden, n_in)
                                 and np.shape(p0["b1"]) == (n_hidden,)
                                 and np.shape(p0["W2"]) == (n_hidden,))
            details["deterministic"] = all(
                np.allclose(np.asarray(p0[k]), np.asarray(p1[k])) for k in ("W1", "b1", "W2"))
            details["seed_changes_init"] = not np.allclose(np.asarray(p0["W1"]),
                                                           np.asarray(p2["W1"]))
            details["symmetry_broken"] = float(np.std(np.asarray(p0["W1"]))) > 1e-6

            loss, grads = lag(p0, X, y)
            details["loss_finite"] = bool(np.isfinite(loss)) and loss > 0
            details["grad_keys"] = set(grads) == {"W1", "b1", "W2", "b2"}

            # Finite differences over every parameter: an analytic gradient that
            # disagrees is wrong, however reasonable the code reads.
            worst = 0.0
            for key in ("W1", "b1", "W2", "b2"):
                arr = np.asarray(p0[key], dtype=float)
                flat = arr.reshape(-1).copy()
                ganalytic = np.asarray(grads[key], dtype=float).reshape(-1)
                for i in range(flat.size):
                    h = 1e-6
                    save = flat[i]
                    flat[i] = save + h
                    p0[key] = flat.reshape(arr.shape) if arr.shape else float(flat[0])
                    lp, _ = lag(p0, X, y)
                    flat[i] = save - h
                    p0[key] = flat.reshape(arr.shape) if arr.shape else float(flat[0])
                    lm, _ = lag(p0, X, y)
                    flat[i] = save
                    p0[key] = flat.reshape(arr.shape) if arr.shape else float(flat[0])
                    numeric = (lp - lm) / (2 * h)
                    denom = abs(numeric) + abs(ganalytic[i]) + 1e-9
                    worst = max(worst, abs(numeric - ganalytic[i]) / denom)
            details["worst_relative_gradient_error"] = float(worst)
            details["gradient_matches_numeric"] = worst < 1e-5

            # Learn a genuinely non-linear boundary the grader generates, so
            # memorising XOR does not help: inside-vs-outside a circle.
            rng2 = np.random.RandomState(7)
            Xc = rng2.randn(400, 2) * 1.2
            yc = (np.sqrt((Xc ** 2).sum(axis=1)) < 1.3).astype(float)
            params = init(2, 8, 3)
            for _ in range(3000):
                _, g = lag(params, Xc, yc)
                for key in ("W1", "b1", "W2", "b2"):
                    params[key] = np.asarray(params[key], dtype=float) - 0.5 * np.asarray(g[key], dtype=float)
            final_loss, _ = lag(params, Xc, yc)
            H = np.tanh(Xc @ np.asarray(params["W1"]).T + np.asarray(params["b1"]))
            pred = (1 / (1 + np.exp(-(H @ np.asarray(params["W2"]) + float(params["b2"])))) > 0.5)
            accuracy = float((pred == (yc > 0.5)).mean())
            details["final_loss"] = float(final_loss)
            details["accuracy"] = accuracy
            details["learns_circle"] = accuracy >= 0.95

            single_loss, single_g = lag(init(2, 8, 3), Xc[:1], yc[:1])
            details["single_sample_ok"] = bool(np.isfinite(single_loss))
        except Exception as exc:
            details["run_error"] = f"{type(exc).__name__}: {exc}"
            return 0, 26, details

        score = sum(2 for k in ("shapes", "deterministic", "seed_changes_init",
                                "symmetry_broken", "loss_finite", "grad_keys",
                                "single_sample_ok") if details.get(k))
        score += 8 if details.get("gradient_matches_numeric") else 0
        score += 4 if details.get("learns_circle") else 0
        return min(26, score), 26, details

    return "ml_medium", prompt, 900, grade




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



def task_cpp_easy():
    prompt = '''Implement a fixed-capacity circular buffer in C++. Return ONLY the struct,
no main, no includes, no explanation. You may use nothing beyond <cstddef>.

    struct RingBuffer {
        RingBuffer(int capacity);      // capacity >= 1
        bool push(int value);          // false if full, buffer unchanged
        bool pop(int& out);            // false if empty, out untouched
        int  size() const;
        bool empty() const;
        bool full() const;
    };

Requirements:
- Fixed capacity given at construction. Store up to 1024 elements; you may use a
  plain member array sized 1024.
- FIFO order: the first value pushed is the first popped.
- Pushing when full returns false and does not overwrite or lose data.
- Popping when empty returns false and leaves `out` alone.
- The buffer must wrap: after filling and draining repeatedly it keeps working.
'''

    def grade(text):
        code = extract_code(text)
        details = {}
        if "RingBuffer" not in code:
            details["struct_present"] = False
            return 0, 16, details
        details["struct_present"] = True
        if not shutil.which("g++"):
            details["compiler"] = "absent"
            return 3, 16, details
        harness = r"""
#include <cstdio>
#include <cstddef>
__CANDIDATE__
static int p=0,f=0;
static void chk(const char* n, bool ok){ if(ok){p++;printf("CHECK %s PASS\n",n);} else {f++;printf("CHECK %s FAIL\n",n);} }
int main(){
    { RingBuffer b(4); int v=0;
      chk("starts_empty", b.empty() && b.size()==0 && !b.full());
      chk("pop_empty_false", !b.pop(v));
      chk("push_then_size", b.push(1) && b.size()==1 && !b.empty());
      chk("fifo_order", b.push(2)&&b.push(3)&&b.pop(v)&&v==1&&b.pop(v)&&v==2&&b.pop(v)&&v==3);
      chk("empty_after_drain", b.empty()); }
    { RingBuffer b(3);
      chk("fills_to_capacity", b.push(1)&&b.push(2)&&b.push(3)&&b.full()&&b.size()==3);
      chk("push_when_full_false", !b.push(4));
      int v=0; b.pop(v);
      chk("full_push_did_not_corrupt", v==1); }
    { RingBuffer b(3); int v=0; bool ok=true;
      for(int round=0; round<50 && ok; ++round){
          for(int i=0;i<3;++i) ok = ok && b.push(round*10+i);
          for(int i=0;i<3;++i){ ok = ok && b.pop(v) && v==round*10+i; } }
      chk("wraps_repeatedly", ok); }
    { RingBuffer b(1); int v=0;
      chk("capacity_one", b.push(7)&&b.full()&&!b.push(8)&&b.pop(v)&&v==7&&b.empty()); }
    printf("SUMMARY pass=%d fail=%d\n",p,f); return 0; }
"""
        workdir = tempfile.mkdtemp(prefix="cppring-")
        src, binary = os.path.join(workdir, "c.cpp"), os.path.join(workdir, "c")
        try:
            open(src, "w").write(harness.replace("__CANDIDATE__", code))
            build = subprocess.run(["g++", "-O1", "-o", binary, src],
                                   capture_output=True, text=True, timeout=120)
            details["compiles"] = build.returncode == 0
            if not details["compiles"]:
                details["compile_error"] = [l for l in build.stderr.splitlines() if "error" in l.lower()][:3]
                return 0, 16, details
            run = subprocess.run([binary], capture_output=True, text=True, timeout=60)
            for line in run.stdout.splitlines():
                if line.startswith("CHECK "):
                    _, n, verdict = line.split()
                    details[n] = verdict == "PASS"
        except Exception as exc:
            details["harness_error"] = f"{type(exc).__name__}: {exc}"
            return 0, 16, details
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
        passed = sum(1 for k in ("starts_empty","pop_empty_false","push_then_size","fifo_order",
                                 "empty_after_drain","fills_to_capacity","push_when_full_false",
                                 "full_push_did_not_corrupt","wraps_repeatedly","capacity_one")
                     if details.get(k))
        return min(16, 2 + passed + (4 if passed == 10 else 0)), 16, details

    return "cpp_easy", prompt, 700, grade


def task_ml_easy():
    prompt = '''Implement a numerically stable softmax and cross-entropy with numpy. Return
ONLY the two functions, no explanation. `import numpy as np` is the only import
permitted.

    def softmax(Z):
        """Z is (n_samples, n_classes). Return row-wise softmax, same shape."""

    def cross_entropy(Z, y):
        """Z is (n_samples, n_classes) LOGITS, y is (n_samples,) integer labels.
        Return the mean cross-entropy loss as a float."""

Requirements:
- Rows of softmax(Z) must sum to 1 and contain no NaN.
- It must be numerically stable: logits of +1000 or -1000 must not overflow or
  produce NaN. Subtract the row maximum before exponentiating.
- cross_entropy takes LOGITS, not probabilities, and must also be stable.
- Both must work for a single row.
'''

    def grade(text):
        code = extract_code(text)
        details = {}
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            details["parse_error"] = str(exc)
            return 0, 16, details
        ok_imports = all((isinstance(n, ast.Import) and all(a.name == "numpy" for a in n.names))
                         or (isinstance(n, ast.ImportFrom) and n.module == "numpy")
                         for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)))
        details["only_numpy_imported"] = ok_imports
        names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
        details["both_functions"] = {"softmax", "cross_entropy"} <= names
        if not (ok_imports and details["both_functions"]):
            return 0, 16, details
        try:
            import numpy as np
        except ImportError:
            details["numpy"] = "absent"
            return 3, 16, details
        # numpy is permitted, not required: "return ONLY the two functions" is
        # reasonably read as omitting the import line, so provide np ourselves.
        env = {"__name__": "candidate", "np": np, "numpy": np}
        try:
            exec(compile(tree, "candidate", "exec"), env)
            sm, ce = env["softmax"], env["cross_entropy"]
            rng = np.random.RandomState(0)
            Z = rng.randn(6, 4) * 2
            P = np.asarray(sm(Z), dtype=float)
            details["shape"] = P.shape == (6, 4)
            details["rows_sum_to_one"] = bool(np.allclose(P.sum(axis=1), 1.0))
            details["matches_reference"] = bool(np.allclose(
                P, np.exp(Z - Z.max(axis=1, keepdims=True))
                / np.exp(Z - Z.max(axis=1, keepdims=True)).sum(axis=1, keepdims=True)))
            big = np.array([[1000.0, 999.0, 998.0], [-1000.0, -1001.0, -1002.0]])
            Pb = np.asarray(sm(big), dtype=float)
            details["stable_large_logits"] = bool(np.all(np.isfinite(Pb))
                                                  and np.allclose(Pb.sum(axis=1), 1.0))
            single = np.asarray(sm(np.array([[1.0, 2.0, 3.0]])), dtype=float)
            details["single_row"] = single.shape == (1, 3) and bool(np.allclose(single.sum(), 1.0))
            y = np.array([0, 1, 2, 3, 0, 1])
            loss = float(ce(Z, y))
            ref = float(np.mean(-(Z[np.arange(6), y]
                                  - (Z.max(axis=1) + np.log(np.exp(Z - Z.max(axis=1, keepdims=True)).sum(axis=1))))))
            details["cross_entropy_value"] = abs(loss - ref) < 1e-6
            big_loss = float(ce(big, np.array([0, 0])))
            details["cross_entropy_stable"] = bool(np.isfinite(big_loss))
        except Exception as exc:
            details["run_error"] = f"{type(exc).__name__}: {exc}"
            return 0, 16, details
        weights = {"shape": 1, "rows_sum_to_one": 2, "matches_reference": 3,
                   "stable_large_logits": 4, "single_row": 1,
                   "cross_entropy_value": 3, "cross_entropy_stable": 2}
        return sum(w for k, w in weights.items() if details.get(k)), 16, details

    return "ml_easy", prompt, 700, grade


VERILOG_EASY_TB = r"""
module tb;
  reg clk = 0, rst_n = 0, sig = 0;
  wire pulse;
  integer pass = 0, fail = 0, seen = 0;
  edge_detect dut(.clk(clk), .rst_n(rst_n), .sig(sig), .pulse(pulse));
  always #5 clk = ~clk;

  task check(input integer id, input cond);
    begin
      if (cond) begin pass = pass + 1; $display("CHECK %0d PASS", id); end
      else      begin fail = fail + 1; $display("CHECK %0d FAIL", id); end
    end
  endtask

  // count cycles where pulse is high
  always @(posedge clk) if (rst_n && pulse) seen = seen + 1;

  initial begin
    #12 rst_n = 1;
    @(negedge clk);
    check(0, pulse === 1'b0);              // idle low

    seen = 0;
    @(negedge clk) sig = 1;                // rising edge
    repeat (4) @(negedge clk);
    check(1, seen == 1);                   // exactly one cycle, not a level

    seen = 0;
    repeat (4) @(negedge clk);
    check(2, seen == 0);                   // stays low while sig held high

    seen = 0;
    @(negedge clk) sig = 0;                // falling edge
    repeat (4) @(negedge clk);
    check(3, seen == 0);                   // no pulse on falling edge

    seen = 0;
    @(negedge clk) sig = 1;
    repeat (2) @(negedge clk);
    @(negedge clk) sig = 0;
    @(negedge clk) sig = 1;
    repeat (3) @(negedge clk);
    check(4, seen == 2);                   // two separate rising edges

    rst_n = 0; @(negedge clk);
    check(5, pulse === 1'b0);              // reset clears the output

    $display("SUMMARY pass=%0d fail=%0d", pass, fail);
    $finish;
  end
endmodule
"""


def task_verilog_easy():
    prompt = '''Write a rising-edge detector in Verilog-2001. Return ONLY the module, no
testbench, no explanation.

module edge_detect(input clk, input rst_n, input sig, output reg pulse);

Requirements:
- `pulse` is high for EXACTLY ONE clock cycle after `sig` goes from 0 to 1.
  It is a pulse, not a level: holding `sig` high must not hold `pulse` high.
- No pulse on a falling edge of `sig`.
- `rst_n` is asynchronous, active low, and clears `pulse`.
- Synthesisable RTL: non-blocking assignments in the sequential block, no
  inferred latches.
'''

    def grade(text):
        code = extract_code(text)
        details = {}
        if "edge_detect" not in code:
            details["module_present"] = False
            return 0, 16, details
        details["module_present"] = True
        labels = ["idle_low", "one_cycle_pulse", "not_a_level", "no_pulse_on_falling",
                  "two_separate_edges", "reset_clears"]
        workdir = tempfile.mkdtemp(prefix="vlog-easy-")
        design = os.path.join(workdir, "edge_detect.v")
        bench = os.path.join(workdir, "tb.v")
        try:
            open(design, "w").write(code + "\n")
            open(bench, "w").write(VERILOG_EASY_TB)
            if shutil.which("iverilog") and shutil.which("vvp"):
                details["simulator"] = "iverilog"
                build = subprocess.run(["iverilog", "-g2001", "-o", os.path.join(workdir, "sim"),
                                        design, bench], capture_output=True, text=True, timeout=60)
                details["compiles"] = build.returncode == 0
                if details["compiles"]:
                    run = subprocess.run(["vvp", os.path.join(workdir, "sim")],
                                         capture_output=True, text=True, timeout=60)
                    for line in run.stdout.splitlines():
                        if line.startswith("CHECK "):
                            _, ident, verdict = line.split()
                            if ident.isdigit() and int(ident) < len(labels):
                                details[labels[int(ident)]] = verdict == "PASS"
                else:
                    details["compile_error"] = build.stderr.strip().splitlines()[:2]
            else:
                details["simulator"] = "absent"
                return 6, 16, details
            if shutil.which("verilator"):
                lint = subprocess.run(["verilator", "--lint-only", "-Wall", "-Wno-DECLFILENAME",
                                       "-Wno-EOFNEWLINE", "-Wno-UNUSEDSIGNAL", design],
                                      capture_output=True, text=True, timeout=60)
                details["lint_clean"] = lint.returncode == 0
        except Exception as exc:
            details["harness_error"] = f"{type(exc).__name__}: {exc}"
            return 0, 16, details
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
        behaviour = sum(2 for k in labels if details.get(k))
        return min(16, (1 if details.get("compiles") else 0) + behaviour
                   + (3 if details.get("lint_clean") else 0)), 16, details

    return "verilog_easy", prompt, 600, grade


CUDA_EASY_HARNESS = r"""
#include <cstdio>
#include <cstdlib>
#include <cmath>
__CANDIDATE__
int main(){
    const int sizes[] = {1, 33, 256, 1000, 100000};
    int fails = 0;
    for (int c = 0; c < 5; ++c) {
        int n = sizes[c];
        float a = 2.5f;
        float *hx = (float*)malloc(n*sizeof(float)), *hy = (float*)malloc(n*sizeof(float));
        for (int i=0;i<n;++i){ hx[i]=(float)(i%13); hy[i]=(float)(i%7); }
        float *dx=0,*dy=0;
        if (cudaMalloc(&dx,n*sizeof(float))!=cudaSuccess || cudaMalloc(&dy,n*sizeof(float))!=cudaSuccess){
            printf("GPU_UNAVAILABLE\n"); return 3; }
        cudaMemcpy(dx,hx,n*sizeof(float),cudaMemcpyHostToDevice);
        cudaMemcpy(dy,hy,n*sizeof(float),cudaMemcpyHostToDevice);
        // Deliberately FEWER blocks than elements: a kernel without a grid-stride
        // loop (or without a bounds guard) gets this wrong.
        int threads = 128, blocks = 4;
        saxpy<<<blocks, threads>>>(n, a, dx, dy);
        if (cudaDeviceSynchronize()!=cudaSuccess){ printf("GPU_UNAVAILABLE\n"); return 3; }
        float* out = (float*)malloc(n*sizeof(float));
        cudaMemcpy(out,dy,n*sizeof(float),cudaMemcpyDeviceToHost);
        int bad = 0;
        for (int i=0;i<n;++i){ float want = a*hx[i]+hy[i]; if (fabs(out[i]-want) > 1e-4f) bad++; }
        printf("CASE %d %s\n", n, bad==0 ? "PASS" : "FAIL");
        if (bad) fails++;
        cudaFree(dx); cudaFree(dy); free(hx); free(hy); free(out);
    }
    printf("SUMMARY failures=%d\n", fails);
    return 0; }
"""


def task_cuda_easy():
    prompt = '''Write a CUDA kernel computing y = a*x + y over n floats. Return ONLY the
kernel, no host code, no main, no includes, no explanation.

    __global__ void saxpy(int n, float a, const float* x, float* y)

Contract:
- It is launched with FEWER total threads than there are elements, so each thread
  must handle several elements. Use a grid-stride loop.
- `n` may be smaller than one block. No thread may read or write past n - 1.
- y[i] becomes a * x[i] + y[i] for every i in 0..n-1, exactly once.
'''

    def grade(text):
        code = extract_code(text)
        details = {}
        if "saxpy" not in code or "__global__" not in code:
            details["kernel_present"] = False
            return 0, 16, details
        details["kernel_present"] = True
        if not shutil.which("nvcc"):
            details["nvcc"] = "absent"
            return 4, 16, details
        workdir = tempfile.mkdtemp(prefix="cuda-easy-")
        src, binary = os.path.join(workdir, "c.cu"), os.path.join(workdir, "c")
        try:
            open(src, "w").write(CUDA_EASY_HARNESS.replace("__CANDIDATE__", code))
            build = subprocess.run(["nvcc", "-o", binary, src], capture_output=True,
                                   text=True, timeout=300)
            details["compiles"] = build.returncode == 0
            if not details["compiles"]:
                details["compile_error"] = [l for l in build.stderr.splitlines()
                                            if "error" in l.lower()][:3]
                return 0, 16, details
            run = subprocess.run([binary], capture_output=True, text=True, timeout=300)
            if "GPU_UNAVAILABLE" in run.stdout or run.returncode == 3:
                details["gpu"] = "unavailable"
                return 6, 16, details
            details["gpu"] = "used"
            for line in run.stdout.splitlines():
                if line.startswith("CASE "):
                    parts = line.split()
                    details[f"n_{parts[1]}"] = parts[2] == "PASS"
        except Exception as exc:
            details["harness_error"] = f"{type(exc).__name__}: {exc}"
            return 0, 16, details
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
        cases = sum(2 for k in ("n_1", "n_33", "n_256", "n_1000", "n_100000") if details.get(k))
        return min(16, 2 + cases + (4 if cases == 10 else 0)), 16, details

    return "cuda_easy", prompt, 500, grade



CUDA_HARD_HARNESS = r"""
#include <cstdio>
#include <cstdlib>
#include <cmath>
__CANDIDATE__
static int fails = 0;
static void run_case(int M, int N, int K) {
    float *hA=(float*)malloc(M*K*sizeof(float)), *hB=(float*)malloc(K*N*sizeof(float));
    float *hC=(float*)malloc(M*N*sizeof(float)), *ref=(float*)malloc(M*N*sizeof(float));
    for(int i=0;i<M*K;++i) hA[i]=(float)((i%9)-4)*0.25f;
    for(int i=0;i<K*N;++i) hB[i]=(float)((i%7)-3)*0.5f;
    for(int m=0;m<M;++m) for(int n=0;n<N;++n){ double s=0; for(int k=0;k<K;++k) s+=(double)hA[m*K+k]*hB[k*N+n]; ref[m*N+n]=(float)s; }
    // Over-allocate and POISON past the end. Without this an unguarded tile read
    // lands in freshly-zeroed memory, contributes nothing, and a kernel with no
    // bounds check passes by luck.
    int padA = M*K + 4096, padB = K*N + 4096;
    float *pA=(float*)malloc(padA*4), *pB=(float*)malloc(padB*4);
    for(int i=0;i<padA;++i) pA[i] = (i<M*K)? hA[i] : 1.0e6f;
    for(int i=0;i<padB;++i) pB[i] = (i<K*N)? hB[i] : 1.0e6f;
    float *dA=0,*dB=0,*dC=0;
    if(cudaMalloc(&dA,padA*4)!=cudaSuccess||cudaMalloc(&dB,padB*4)!=cudaSuccess||cudaMalloc(&dC,M*N*4)!=cudaSuccess){
        printf("GPU_UNAVAILABLE\n"); exit(3); }
    cudaMemcpy(dA,pA,padA*4,cudaMemcpyHostToDevice); cudaMemcpy(dB,pB,padB*4,cudaMemcpyHostToDevice);
    free(pA); free(pB);
    cudaMemset(dC,0,M*N*4);
    dim3 threads(16,16), blocks((N+15)/16,(M+15)/16);
    matmul<<<blocks,threads>>>(dA,dB,dC,M,N,K);
    if(cudaDeviceSynchronize()!=cudaSuccess){ printf("GPU_UNAVAILABLE\n"); exit(3); }
    cudaMemcpy(hC,dC,M*N*4,cudaMemcpyDeviceToHost);
    int bad=0; for(int i=0;i<M*N;++i){ float t=fabs(ref[i])*1e-3f+1e-3f; if(fabs(hC[i]-ref[i])>t) bad++; }
    printf("CASE %dx%dx%d %s\n",M,N,K, bad?"FAIL":"PASS"); if(bad) fails++;
    cudaFree(dA);cudaFree(dB);cudaFree(dC);free(hA);free(hB);free(hC);free(ref);
}
int main(){
    run_case(16,16,16);      // exactly one tile
    run_case(64,64,64);      // several whole tiles
    run_case(17,17,17);      // ragged in every dimension
    run_case(1,1,1);         // degenerate
    run_case(33,48,7);       // K smaller than the tile, non-square
    run_case(100,60,80);     // large and ragged
    printf("SUMMARY failures=%d\n",fails); return 0; }
"""


def task_cuda_hard():
    prompt = '''Write a tiled matrix-multiply CUDA kernel using shared memory. Return ONLY
the kernel, no host code, no main, no includes, no explanation.

    __global__ void matmul(const float* A, const float* B, float* C,
                           int M, int N, int K)

Computes C = A * B where A is M x K, B is K x N, C is M x N, all row-major.

Contract:
- Launched with dim3 threads(16,16) and blocks((N+15)/16, (M+15)/16). Assume a
  16 x 16 tile.
- You must stage tiles of A and B in __shared__ memory and loop over K in tiles.
  A naive kernel that reads global memory K times per output will be rejected on
  inspection.
- M, N and K are NOT necessarily multiples of 16, and may be as small as 1.
  Threads whose tile element falls outside the matrix must contribute zero, and
  no thread may read or write out of bounds.
- Every thread in a block must reach every __syncthreads(). Guarding the barrier
  behind an in-range test deadlocks or corrupts the tile.
'''

    def grade(text):
        code = extract_code(text)
        details = {}
        if "matmul" not in code or "__global__" not in code:
            details["kernel_present"] = False
            return 0, 30, details
        details["kernel_present"] = True
        details["uses_shared_memory"] = "__shared__" in code
        details["barrier_in_thread_conditional"] = _barrier_inside_thread_conditional(code)
        if not shutil.which("nvcc"):
            details["nvcc"] = "absent"
            return 5, 30, details
        workdir = tempfile.mkdtemp(prefix="cuda-hard-")
        src, binary = os.path.join(workdir, "c.cu"), os.path.join(workdir, "c")
        try:
            open(src, "w").write(CUDA_HARD_HARNESS.replace("__CANDIDATE__", code))
            build = subprocess.run(["nvcc", "-o", binary, src], capture_output=True,
                                   text=True, timeout=300)
            details["compiles"] = build.returncode == 0
            if not details["compiles"]:
                details["compile_error"] = [l for l in build.stderr.splitlines()
                                            if "error" in l.lower()][:3]
                return 0, 30, details
            run = subprocess.run([binary], capture_output=True, text=True, timeout=300)
            if "GPU_UNAVAILABLE" in run.stdout or run.returncode == 3:
                details["gpu"] = "unavailable"
                return 8, 30, details
            details["gpu"] = "used"
            for line in run.stdout.splitlines():
                if line.startswith("CASE "):
                    parts = line.split()
                    details[f"case_{parts[1]}"] = parts[2] == "PASS"
        except subprocess.TimeoutExpired:
            details["timeout"] = True
            return 0, 30, details
        except Exception as exc:
            details["harness_error"] = f"{type(exc).__name__}: {exc}"
            return 0, 30, details
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
        whole = sum(2 for k in ("case_16x16x16", "case_64x64x64") if details.get(k))
        # The ragged cases are the ones a tiled kernel gets wrong.
        ragged = sum(4 for k in ("case_17x17x17", "case_1x1x1", "case_33x48x7",
                                 "case_100x60x80") if details.get(k))
        shared = 3 if details["uses_shared_memory"] else 0
        barrier = 2 if not details["barrier_in_thread_conditional"] else 0
        return min(30, 5 + whole + ragged + shared + barrier), 30, details

    return "cuda_hard", prompt, 1400, grade


CPP_HARD_HARNESS = r"""
#include <cstdio>
#include <cmath>
#include <vector>
__CANDIDATE__
static int p=0,f=0;
static void chk(const char* n, bool ok){ if(ok){p++;printf("CHECK %s PASS\n",n);} else {f++;printf("CHECK %s FAIL\n",n);} }

// f(x,y) = (x*y + sin(x)) * exp(y)
static double build(Tape& t, double xv, double yv, int& xi, int& yi) {
    xi = t.input(xv); yi = t.input(yv);
    int xy = t.mul(xi, yi);
    int sx = t.sin_(xi);
    int sum = t.add(xy, sx);
    int ey = t.exp_(yi);
    int root = t.mul(sum, ey);
    t.backward(root);
    return t.value(root);
}
int main(){
    { Tape t; int xi,yi; double v = build(t, 0.7, -0.3, xi, yi);
      double want = (0.7*-0.3 + sin(0.7)) * exp(-0.3);
      chk("forward_value", fabs(v-want) < 1e-9);
      // analytic: df/dx = (y + cos(x)) * exp(y);  df/dy = x*exp(y) + (x*y+sin(x))*exp(y)
      double gx = (-0.3 + cos(0.7)) * exp(-0.3);
      double gy = 0.7*exp(-0.3) + (0.7*-0.3 + sin(0.7))*exp(-0.3);
      chk("grad_x", fabs(t.grad(xi)-gx) < 1e-6);
      chk("grad_y", fabs(t.grad(yi)-gy) < 1e-6); }

    // A node used twice must ACCUMULATE both paths: g = x*x + x  =>  dg/dx = 2x+1
    { Tape t; int x = t.input(1.7);
      int sq = t.mul(x,x); int g = t.add(sq,x); t.backward(g);
      chk("reused_node_accumulates", fabs(t.grad(x) - (2*1.7+1.0)) < 1e-9); }

    // Deep chain: exp(exp(sin(x))) — tests ordering of the reverse sweep
    { Tape t; int x = t.input(0.35);
      int a = t.sin_(x); int b = t.exp_(a); int c = t.exp_(b); t.backward(c);
      double want = exp(exp(sin(0.35))) * exp(sin(0.35)) * cos(0.35);
      chk("deep_chain", fabs(t.grad(x)-want) < 1e-6); }

    // Constants carry no gradient and must not break the sweep
    { Tape t; int x = t.input(2.0); int k = t.constant(3.0);
      int m = t.mul(x,k); t.backward(m);
      chk("constant_handled", fabs(t.grad(x)-3.0) < 1e-9); }

    // Finite-difference check on a fresh expression
    { double h=1e-6, xv=1.1, yv=0.4;
      Tape t; int xi,yi; build(t, xv, yv, xi, yi);
      double ga = t.grad(xi);
      Tape tp; int a1,b1; double vp = build(tp, xv+h, yv, a1, b1);
      Tape tm; int a2,b2; double vm = build(tm, xv-h, yv, a2, b2);
      chk("matches_finite_difference", fabs(ga - (vp-vm)/(2*h)) < 1e-5); }

    printf("SUMMARY pass=%d fail=%d\n",p,f); return 0; }
"""


def task_cpp_hard():
    prompt = '''Implement reverse-mode automatic differentiation in C++. Return ONLY the
struct, no main, no includes, no explanation. You may use <cmath> and <vector>.

    struct Tape {
        int constant(double v);   // a value with no gradient
        int input(double v);      // a value you will want the gradient of
        int add(int a, int b);    // returns the id of the new node
        int mul(int a, int b);
        int sin_(int a);
        int exp_(int a);
        double value(int node) const;
        void backward(int root);  // seed d(root)/d(root) = 1 and sweep back
        double grad(int node) const;
    };

Each call records a node and returns its integer id. `backward(root)` computes
the derivative of `root` with respect to every node.

Requirements:
- Gradients are checked against finite differences to 1e-5.
- A node used more than once must ACCUMULATE gradient from every path that uses
  it: for g = x*x + x, dg/dx is 2x + 1, not 2x and not 1.
- The reverse sweep must visit nodes in an order where every consumer is
  processed before its inputs; recording order makes this easy.
- Constants take part in the forward value but need no gradient.
'''

    def grade(text):
        code = extract_code(text)
        details = {}
        if "struct Tape" not in code and "class Tape" not in code:
            details["tape_present"] = False
            return 0, 30, details
        details["tape_present"] = True
        if not shutil.which("g++"):
            details["compiler"] = "absent"
            return 4, 30, details
        workdir = tempfile.mkdtemp(prefix="cpp-hard-")
        src, binary = os.path.join(workdir, "c.cpp"), os.path.join(workdir, "c")
        try:
            open(src, "w").write(CPP_HARD_HARNESS.replace("__CANDIDATE__", code))
            build = subprocess.run(["g++", "-O1", "-o", binary, src],
                                   capture_output=True, text=True, timeout=180)
            details["compiles"] = build.returncode == 0
            if not details["compiles"]:
                details["compile_error"] = [l for l in build.stderr.splitlines()
                                            if "error" in l.lower()][:3]
                return 0, 30, details
            run = subprocess.run([binary], capture_output=True, text=True, timeout=120)
            for line in run.stdout.splitlines():
                if line.startswith("CHECK "):
                    _, n, verdict = line.split()
                    details[n] = verdict == "PASS"
        except subprocess.TimeoutExpired:
            details["timeout"] = True
            return 0, 30, details
        except Exception as exc:
            details["harness_error"] = f"{type(exc).__name__}: {exc}"
            return 0, 30, details
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
        basic = sum(2 for k in ("forward_value", "constant_handled") if details.get(k))
        grads = sum(4 for k in ("grad_x", "grad_y", "deep_chain") if details.get(k))
        # Accumulation across reuse is the thing people get wrong.
        accum = 6 if details.get("reused_node_accumulates") else 0
        fd = 6 if details.get("matches_finite_difference") else 0
        return min(30, 2 + basic + grads + accum + fd), 30, details

    return "cpp_hard", prompt, 2000, grade


def task_ml_hard():
    prompt = '''Implement scaled dot-product attention with its analytic gradients, using
numpy. Return ONLY the two functions, no explanation. `import numpy as np` is the
only import permitted.

    def attention_forward(Q, K, V):
        """Q, K, V are (T, d). Return (out, cache).
        S    = Q @ K.T / sqrt(d)        (T, T)
        P    = row-wise softmax of S    (T, T)
        out  = P @ V                    (T, d)
        `cache` is whatever you need for the backward pass."""

    def attention_backward(dout, cache):
        """dout is (T, d), the gradient of a scalar loss w.r.t. out.
        Return (dQ, dK, dV), each the same shape as Q, K, V."""

Requirements:
- The softmax must be numerically stable (subtract the row max).
- The gradients must be the true analytic derivatives. They are checked against
  finite differences to a relative tolerance of 1e-5.
- The softmax Jacobian is the hard part: for a row p, dS = P * (dP - sum(dP * P)),
  and dropping the subtraction term is the classic error.
- Do not forget the 1/sqrt(d) scale in the backward pass.
'''

    def grade(text):
        code = extract_code(text)
        details = {}
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            details["parse_error"] = str(exc)
            return 0, 30, details
        ok_imports = all((isinstance(n, ast.Import) and all(a.name == "numpy" for a in n.names))
                         or (isinstance(n, ast.ImportFrom) and n.module == "numpy")
                         for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)))
        details["only_numpy_imported"] = ok_imports
        names = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
        details["both_functions"] = {"attention_forward", "attention_backward"} <= names
        if not (ok_imports and details["both_functions"]):
            return 0, 30, details
        try:
            import numpy as np
        except ImportError:
            details["numpy"] = "absent"
            return 4, 30, details
        # numpy is permitted, not required: "return ONLY the two functions" is
        # reasonably read as omitting the import line, so provide np ourselves.
        env = {"__name__": "candidate", "np": np, "numpy": np}
        try:
            exec(compile(tree, "candidate", "exec"), env)
            fwd, bwd = env["attention_forward"], env["attention_backward"]
            rng = np.random.RandomState(0)
            T, d = 5, 4
            Q, K, V = rng.randn(T, d), rng.randn(T, d), rng.randn(T, d)
            out, cache = fwd(Q, K, V)
            out = np.asarray(out, dtype=float)
            details["output_shape"] = out.shape == (T, d)

            S = Q @ K.T / np.sqrt(d)
            P = np.exp(S - S.max(axis=1, keepdims=True))
            P = P / P.sum(axis=1, keepdims=True)
            details["forward_matches_reference"] = bool(np.allclose(out, P @ V, atol=1e-8))

            big = Q * 1e3
            out_big, _ = fwd(big, K, V)
            details["stable_large_scores"] = bool(np.all(np.isfinite(np.asarray(out_big, float))))

            dout = rng.randn(T, d)
            dQ, dK, dV = bwd(dout, cache)
            dQ, dK, dV = (np.asarray(x, dtype=float) for x in (dQ, dK, dV))
            details["grad_shapes"] = (dQ.shape == Q.shape and dK.shape == K.shape
                                      and dV.shape == V.shape)

            def loss(q, k, v):
                o, _ = fwd(q, k, v)
                return float((np.asarray(o, dtype=float) * dout).sum())

            worst = 0.0
            for name, mat, analytic in (("Q", Q, dQ), ("K", K, dK), ("V", V, dV)):
                flat = mat.reshape(-1)
                for i in range(flat.size):
                    h, save = 1e-6, flat[i]
                    flat[i] = save + h
                    lp = loss(Q, K, V)
                    flat[i] = save - h
                    lm = loss(Q, K, V)
                    flat[i] = save
                    numeric = (lp - lm) / (2 * h)
                    a = analytic.reshape(-1)[i]
                    worst = max(worst, abs(numeric - a) / (abs(numeric) + abs(a) + 1e-9))
            details["worst_relative_gradient_error"] = float(worst)
            details["gradients_match_numeric"] = worst < 1e-5
        except Exception as exc:
            details["run_error"] = f"{type(exc).__name__}: {exc}"
            return 0, 30, details
        score = sum(3 for k in ("output_shape", "grad_shapes") if details.get(k))
        score += 6 if details.get("forward_matches_reference") else 0
        score += 4 if details.get("stable_large_scores") else 0
        score += 14 if details.get("gradients_match_numeric") else 0
        return min(30, score), 30, details

    return "ml_hard", prompt, 1600, grade


VERILOG_HARD_TB = r"""
module tb;
  localparam WIDTH = 8, DEPTH = 8;
  reg wclk = 0, rclk = 0, wrst_n = 0, rrst_n = 0, winc = 0, rinc = 0;
  reg [WIDTH-1:0] wdata = 0;
  wire [WIDTH-1:0] rdata;
  wire wfull, rempty;
  integer pass = 0, fail = 0, errors = 0, got = 0, i;
  reg [WIDTH-1:0] seen;

  async_fifo #(.WIDTH(WIDTH), .DEPTH(DEPTH)) dut (
    .wclk(wclk), .wrst_n(wrst_n), .winc(winc), .wdata(wdata), .wfull(wfull),
    .rclk(rclk), .rrst_n(rrst_n), .rinc(rinc), .rdata(rdata), .rempty(rempty));

  always #5 wclk = ~wclk;   // unrelated clocks, deliberately not integer-related
  always #7 rclk = ~rclk;

  task check(input integer id, input cond);
    begin
      if (cond) begin pass = pass + 1; $display("CHECK %0d PASS", id); end
      else      begin fail = fail + 1; $display("CHECK %0d FAIL", id); end
    end
  endtask

  // one write, driven strictly from the write clock
  task push(input [WIDTH-1:0] value);
    begin
      @(negedge wclk);
      while (wfull) @(negedge wclk);
      wdata = value; winc = 1;
      @(negedge wclk);
      winc = 0;
    end
  endtask

  // one read, driven strictly from the read clock; rdata is sampled while the
  // read pointer still addresses the entry being popped
  task pop(output [WIDTH-1:0] value);
    begin
      @(negedge rclk);
      while (rempty) @(negedge rclk);
      value = rdata; rinc = 1;
      @(negedge rclk);
      rinc = 0;
    end
  endtask

  initial begin
    #23 wrst_n = 1; rrst_n = 1;
    repeat (4) @(negedge rclk);
    check(0, rempty === 1'b1);

    // fill, drain, twice — the second pass exercises pointer wrap
    for (i = 0; i < 2 * DEPTH; i = i + 1) begin
      push(i[WIDTH-1:0]);
      pop(seen);
      if (seen !== i[WIDTH-1:0]) errors = errors + 1;
      got = got + 1;
    end
    check(1, got == 2 * DEPTH);
    check(2, errors == 0);

    repeat (6) @(negedge rclk);
    check(3, rempty === 1'b1);

    $display("SUMMARY pass=%0d fail=%0d got=%0d errors=%0d", pass, fail, got, errors);
    $finish;
  end

  initial begin
    #200000;
    $display("SUMMARY pass=%0d fail=%0d TIMEOUT", pass, fail);
    $finish;
  end
endmodule
"""


def task_verilog_hard():
    prompt = '''Write an asynchronous FIFO in Verilog-2001 — a FIFO whose write and read
sides run on unrelated clocks. Return ONLY the module, no testbench, no
explanation.

module async_fifo #(parameter WIDTH = 8, parameter DEPTH = 8)
  (input wclk, input wrst_n, input winc, input [WIDTH-1:0] wdata, output wfull,
   input rclk, input rrst_n, input rinc, output [WIDTH-1:0] rdata, output rempty);

Requirements:
- DEPTH is a power of two. `wclk` and `rclk` have no fixed phase or frequency
  relationship.
- A write occurs on a `wclk` edge when `winc` is high and `wfull` is low; a read
  on an `rclk` edge when `rinc` is high and `rempty` is low.
- Pointers crossing between the domains MUST be Gray-coded and passed through a
  two-flop synchroniser in the destination domain. A binary pointer crossed
  directly can be sampled mid-transition with several bits changing at once,
  which corrupts the count — it will usually still simulate correctly, so this is
  about doing it right rather than about passing by luck.
- `wfull` and `rempty` must be generated in their own clock domains.
- No data may be lost, duplicated or reordered.
- Synthesisable RTL: non-blocking assignments in sequential blocks, no latches.
'''

    def grade(text):
        code = extract_code(text)
        details = {}
        if "async_fifo" not in code:
            details["module_present"] = False
            return 0, 30, details
        details["module_present"] = True
        lowered = code.lower()
        # A binary pointer crossed directly usually simulates fine, so structure
        # is the only way to see it.
        # Look for the actual binary-to-Gray conversion (x >> 1) ^ x, not the
        # word "gray" — a variable NAMED wgray holding a binary pointer is
        # exactly the bug this is meant to catch, and simulation cannot see it
        # because binary crossings work fine without real metastability.
        details["uses_gray_coding"] = bool(re.search(r">>\s*1\s*\)?\s*\^", code)
                                           or re.search(r"\^\s*\(?\s*\w+\s*>>\s*1", code))
        # two registers in series in the destination domain, under any naming
        # Two registers genuinely in SERIES: b <= a following a <= src. Naming
        # alone is not evidence — a pair called q1/q2 both fed from the source is
        # a single-flop crossing wearing a two-flop name.
        # LIMITATION: this finds a two-flop chain anywhere in the module, so a
        # design with one correct crossing and one single-flop crossing still
        # passes. It catches the absence of synchronisation, not a bad crossing
        # among good ones.
        details["has_two_flop_synchroniser"] = bool(
            re.search(r"(\w+)\s*<=\s*[^;]+;\s*(\w+)\s*<=\s*\1\s*;", code))
        labels = ["empty_at_reset", "all_data_arrived", "no_corruption_or_reorder", "drained"]
        workdir = tempfile.mkdtemp(prefix="vlog-hard-")
        design, bench = os.path.join(workdir, "async_fifo.v"), os.path.join(workdir, "tb.v")
        try:
            open(design, "w").write(code + "\n")
            open(bench, "w").write(VERILOG_HARD_TB)
            if shutil.which("iverilog") and shutil.which("vvp"):
                details["simulator"] = "iverilog"
                build = subprocess.run(["iverilog", "-g2001", "-o", os.path.join(workdir, "sim"),
                                        design, bench], capture_output=True, text=True, timeout=90)
                details["compiles"] = build.returncode == 0
                if details["compiles"]:
                    run = subprocess.run(["vvp", os.path.join(workdir, "sim")],
                                         capture_output=True, text=True, timeout=180)
                    for line in run.stdout.splitlines():
                        if line.startswith("CHECK "):
                            _, ident, verdict = line.split()
                            if ident.isdigit() and int(ident) < len(labels):
                                details[labels[int(ident)]] = verdict == "PASS"
                    details["timed_out"] = "TIMEOUT" in run.stdout
                    m = re.search(r"got=(\d+) errors=(\d+)", run.stdout)
                    if m:
                        details["items_read"] = int(m.group(1))
                        details["order_errors"] = int(m.group(2))
                else:
                    details["compile_error"] = build.stderr.strip().splitlines()[:2]
            else:
                details["simulator"] = "absent"
                return 8, 30, details
            if shutil.which("verilator"):
                lint = subprocess.run(["verilator", "--lint-only", "-Wall", "-Wno-DECLFILENAME",
                                       "-Wno-EOFNEWLINE", "-Wno-UNUSEDSIGNAL", "-Wno-UNUSEDPARAM",
                                       "-Wno-MULTIDRIVEN", "-Wno-WIDTHEXPAND",
                                       "-Wno-WIDTHTRUNC", design],
                                      capture_output=True, text=True, timeout=90)
                details["lint_clean"] = lint.returncode == 0
        except subprocess.TimeoutExpired:
            details["timeout"] = True
            return 0, 30, details
        except Exception as exc:
            details["harness_error"] = f"{type(exc).__name__}: {exc}"
            return 0, 30, details
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
        score = 2 if details.get("compiles") else 0
        score += 3 if details.get("empty_at_reset") else 0
        score += 8 if details.get("all_data_arrived") else 0
        score += 8 if details.get("no_corruption_or_reorder") else 0
        score += 2 if details.get("drained") else 0
        score += 3 if details.get("uses_gray_coding") else 0
        score += 2 if details.get("has_two_flop_synchroniser") else 0
        score += 2 if details.get("lint_clean") else 0
        return min(30, score), 30, details

    return "verilog_hard", prompt, 1600, grade


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
        "--retry", action=argparse.BooleanOptionalAction, default=True,
        help="give every imperfect task ONE do-over, showing the model the raw "
             "checker output (compiler errors, failed check names) with no "
             "analysis. ON BY DEFAULT: repairing your own work from an error is "
             "the normal case, not a special mode. Records score_first and "
             "score_retry separately; the credited score is the retry times "
             "--retry-credit and never lower than the first attempt. "
             "--no-retry gives a cold-score-only run",
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
    tasks = [
        task_structured_protocol(), task_bom(), task_code_repair(), task_code_review(),
        task_protocol_design(), task_long_context(), task_scope_control(), task_timing(),
    ]
    if args.extended:
        tasks += [
            # easy: journeyman competence. A suite of only hard tasks says who is
            # in the top bracket and nothing about who is employable.
            task_cpp_easy(), task_verilog_easy(), task_cuda_easy(), task_ml_easy(),
            # medium: the original extended set, repositioned after two models
            # scored 100% on cpp and cuda
            task_cobs_codec(), task_stream_reassembler(),
            task_verilog_medium(), task_cuda_medium(),
            task_cpp_medium(), task_ml_medium(),
            # hard: senior practitioner. Tiled matmul, reverse-mode autodiff,
            # clock-domain crossing, attention with analytic gradients.
            task_cpp_hard(), task_verilog_hard(), task_cuda_hard(), task_ml_hard(),
        ]
    results = []
    suite_started = time.monotonic()
    for name, prompt, max_tokens, grader in tasks:
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
            row = {
                "task": name,
                "score": score,
                "max_score": maximum,
                "elapsed_s": round(elapsed, 4),
                "max_tokens": budget,
                "usage": usage,
                "response": text,
                "grade_details": details,
            }
            # One do-over. The model sees the raw checker output and nothing
            # else, then repairs its own answer. Reading an error and fixing your
            # own bug is most of real engineering, and a model that fails cold
            # but repairs reliably is far more useful in a loop than one that
            # fails cold and stays stuck — the gap between the two scores is the
            # interesting number.
            if args.retry and score < maximum:
                row["score_first"] = score
                row["retry_feedback"] = failure_report(details)
                try:
                    retry_text, retry_usage, retry_elapsed = request(
                        args.url, key, args.model, prompt, budget,
                        template_kwargs=not args.no_template_kwargs,
                        strip_reasoning=args.strip_reasoning,
                        history=[{"role": "assistant", "content": text},
                                 {"role": "user",
                                  "content": RETRY_INSTRUCTION + row["retry_feedback"]}])
                    retry_score, _, retry_details = grader(retry_text)
                    row["score_retry"] = retry_score
                    row["retry_usage"] = retry_usage
                    row["retry_elapsed_s"] = round(retry_elapsed, 4)
                    row["retry_response"] = retry_text
                    row["retry_grade_details"] = retry_details
                    credited = int(round(retry_score * args.retry_credit))
                    # A retry can never lower a score.
                    if credited > score:
                        row["score"] = credited
                        row["grade_details"] = retry_details
                except Exception as exc:
                    row["retry_error"] = f"{type(exc).__name__}: {exc}"
        except Exception as exc:
            row = {
                "task": name, "score": 0, "max_score": maximum,
                "error": f"{type(exc).__name__}: {exc}", "response": "", "grade_details": {},
            }
        results.append(row)
        print(json.dumps({k: row[k] for k in row if k in ("task", "score", "max_score", "elapsed_s", "error")}), flush=True)
    output = {
        "suite": ("work_quality_v1+hard" if args.extended else "work_quality_v1")
                 + ("" if args.retry else "+cold"),
        "model": args.model,
        "endpoint": args.url,
        "score": sum(row["score"] for row in results),
        "max_score": sum(row["max_score"] for row in results),
        "cost": _cost_summary(results, time.monotonic() - suite_started),
        "tasks": results,
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(_json_safe(output), indent=2) + "\n")
    print(json.dumps({"model": args.model, "score": output["score"], "max_score": output["max_score"], "output": args.output}))


if __name__ == "__main__":
    main()
