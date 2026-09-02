#!/usr/bin/env python3
"""Render the dw-spark0 leaderboard from the result files.

Rows are models; the frontier control (Fable 5.1 / Opus 5, answered offline) is
the reference row. Only the clean-sweep files (full-*.json) are used, plus
results/frontier-control/control.json. Tier subtotals are computed from task
names; legacy tasks are the eight in each original suite.
"""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "results"
MACHINE = sys.argv[1] if len(sys.argv) > 1 else "dw-spark0"
R = ROOT / MACHINE

def tier(task):
    if task.endswith("_easy"): return "easy"
    if task.endswith("_medium") or task in ("cobs_codec", "stream_reassembler"): return "medium"
    if task.endswith("_hard"): return "hard"
    return "legacy"

def tiers(tasks):
    out = {t: [0, 0] for t in ("legacy", "easy", "medium", "hard")}
    for row in tasks:
        k = tier(row["task"]); out[k][0] += row["score"]; out[k][1] += row["max_score"]
    return out

def fmt_tiers(t):
    return " / ".join(f"{t[k][0]}" for k in ("legacy", "easy", "medium", "hard")) + \
           f" = **{sum(v[0] for v in t.values())}**/{sum(v[1] for v in t.values())}"

def load(p):
    try: return json.loads(p.read_text())
    except Exception: return None

models = {}
for p in sorted(R.glob("full-*.json")):
    d = load(p)
    if not d: continue
    name = d.get("model")
    if "concurrency" in p.name:
        name = p.name[len("full-concurrency-"):-5]
        models.setdefault(name, {})["conc"] = d
    elif "deep-reasoning" in p.name:
        models.setdefault(name, {})["reason"] = d
    else:
        models.setdefault(name, {})["work"] = d

def retry_note(d):
    """cost.retries is authoritative: files from before the retry_enabled field
    existed still record how many do-overs happened."""
    if not d: return ""
    r = (d.get("cost") or {}).get("retries")
    if r:
        return f" (retry×{r})"
    if d.get("retry_enabled"):
        return " (retry×0)"
    return " (cold)"

lines = [f"# {MACHINE} leaderboard", "",
         "Clean sweep, all three tiers, 12k-token floor. Tier columns are legacy / easy / medium / hard. "
         "`(cold)` = no retry; `(retry×N)` = N tasks got a do-over, credited at 0.7. "
         "Fable 5.1 answered offline and is the harness reference: anything it does not max is a harness suspect.", "",
         "| model | work L/E/M/H = total | reasoning L/E/M/H = total | concurrency 1/2/4/8 tok/s | tokens | wall |",
         "|---|---|---|---|---:|---:|"]

ctrl = load(ROOT / "frontier-control" / "control.json")
if ctrl:
    w = tiers([t for t in ctrl["tasks"] if t["suite"] == "work"])
    r = tiers([t for t in ctrl["tasks"] if t["suite"] == "reason"])
    lines.append(f"| **Fable 5.1 (reference)** | {fmt_tiers(w)} | {fmt_tiers(r)} | — | — | — |")

for name in sorted(models, key=lambda n: -((models[n].get("work") or {}).get("score", 0))):
    m = models[name]
    w, r, c = m.get("work"), m.get("reason"), m.get("conc")
    wcell = (fmt_tiers(tiers(w["tasks"])) + retry_note(w)) if w else "—"
    rcell = (fmt_tiers(tiers(r["tasks"])) + retry_note(r)) if r else "—"
    if c:
        rows = [x for x in c["results"] if "aggregate_tok_s" in x]
        ccell = " / ".join(f"{x['aggregate_tok_s']:.0f}" for x in rows)
    else:
        ccell = "—"
    tok = sum((x.get("cost") or {}).get("completion_tokens", 0) for x in (w, r) if x)
    wall = sum((x.get("cost") or {}).get("wall_seconds", 0) for x in (w, r) if x)
    lines.append(f"| `{name}` | {wcell} | {rcell} | {ccell} | {tok or '—'} | {f'{wall/60:.0f} min' if wall else '—'} |")

lines += ["", "## Retry gaps (score_first → credited)", ""]
any_retry = False
for name, m in sorted(models.items()):
    for suite_key in ("work", "reason"):
        d = m.get(suite_key)
        if not d: continue
        for t in d["tasks"]:
            if "score_retry" in t:
                any_retry = True
                lines.append(f"- `{name}` {t['task']}: {t['score_first']} → retry {t['score_retry']} → credited **{t['score']}**/{t['max_score']}")
if not any_retry:
    lines.append("_No retry-era results yet._")

out = R / "LEADERBOARD.md"
out.write_text("\n".join(lines) + "\n")
print("\n".join(lines))
