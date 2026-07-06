#!/usr/bin/env node
/*
 * patch-openclaw-tool-loop.js — cap tool-call rounds per turn in OpenClaw's
 * embedded agent loop, so a wedged turn (model emits terminating text + a tool
 * call every iteration) self-terminates instead of looping forever.
 *
 * WHY: OpenClaw's local-model run loop (proxy-*.js, function that streams the
 * assistant response and calls executeToolCalls) continues purely on
 * `hasMoreToolCalls` — there is no per-turn iteration cap and no config knob for
 * one (verified against 2026.6.11; see docs/openclaw-tool-loop-patch.md). This
 * inserts a counter that forces the turn to end after N tool rounds.
 *
 * The dist filenames are content-hashed and change on every `npm update`, so
 * this patches by UNIQUE ANCHOR STRINGS, not file/line, and is idempotent.
 * Re-run it after each OpenClaw update.
 *
 * Usage:
 *   node patch-openclaw-tool-loop.js           # apply (idempotent)
 *   node patch-openclaw-tool-loop.js --check    # report status only
 *   node patch-openclaw-tool-loop.js --revert   # remove the patch
 *   OPENCLAW_MAX_TOOL_ROUNDS=40 ... (runtime env read by the patched code; default 50)
 */
"use strict";
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const MARKER = "llmctl-tool-loop-cap";
const ANCHOR_DECL = "let hasMoreToolCalls = true;";
const ANCHOR_CHECK = "hasMoreToolCalls = !executedToolBatch.terminate;";

const INSERT_DECL =
  ANCHOR_DECL +
  "\n\t\t\tlet __llmctlRounds = 0; /* " + MARKER + " */";

const INSERT_CHECK =
  ANCHOR_CHECK +
  " /* " + MARKER + " */ { const __cap = Number(process.env.OPENCLAW_MAX_TOOL_ROUNDS) || 50;" +
  " if (hasMoreToolCalls && ++__llmctlRounds >= __cap) { hasMoreToolCalls = false;" +
  " try { console.error('[llmctl] tool-round cap (' + __cap + ') hit — ending turn to break a runaway loop'); } catch (e) {} } }";

function distDir() {
  const candidates = [];
  if (process.env.OPENCLAW_DIST) candidates.push(process.env.OPENCLAW_DIST);
  candidates.push(path.join(process.env.HOME || "", ".npm-global/lib/node_modules/openclaw/dist"));
  try {
    const root = execSync("npm root -g", { encoding: "utf8" }).trim();
    candidates.push(path.join(root, "openclaw/dist"));
  } catch (e) { /* npm not on PATH — fall back to the candidates above */ }
  for (const c of candidates) if (c && fs.existsSync(c)) return c;
  throw new Error("could not locate openclaw/dist (set OPENCLAW_DIST=/path/to/openclaw/dist)");
}

function findTarget(dir) {
  for (const f of fs.readdirSync(dir)) {
    if (!f.endsWith(".js")) continue;
    const p = path.join(dir, f);
    const s = fs.readFileSync(p, "utf8");
    if (s.includes(ANCHOR_CHECK) && s.includes(ANCHOR_DECL)) return { p, s };
  }
  throw new Error("no dist file contains the tool-loop anchors — OpenClaw internals may have changed; re-derive anchors (see docs/openclaw-tool-loop-patch.md)");
}

const mode = process.argv[2] || "--apply";
const dir = distDir();
const { p, s } = findTarget(dir);
const rel = path.basename(p);
const patched = s.includes(MARKER);

if (mode === "--check") {
  console.log(patched ? `PATCHED: ${rel}` : `NOT patched: ${rel}`);
  process.exit(patched ? 0 : 1);
}

if (mode === "--revert") {
  if (!patched) { console.log("not patched — nothing to revert"); process.exit(0); }
  let out = s.split(INSERT_DECL).join(ANCHOR_DECL).split(INSERT_CHECK).join(ANCHOR_CHECK);
  fs.writeFileSync(p, out);
  console.log(`reverted ${rel}`);
  process.exit(0);
}

// --apply (default)
if (patched) { console.log(`already patched: ${rel}`); process.exit(0); }
if ((s.split(ANCHOR_DECL).length - 1) !== 1 || (s.split(ANCHOR_CHECK).length - 1) !== 1)
  throw new Error("anchors are not unique in " + rel + " — aborting to avoid a bad edit");
let out = s.replace(ANCHOR_DECL, INSERT_DECL).replace(ANCHOR_CHECK, INSERT_CHECK);
fs.copyFileSync(p, p + ".llmctl-bak");
fs.writeFileSync(p, out);
console.log(`patched ${rel} (backup: ${rel}.llmctl-bak)`);
console.log("restart the gateway to load it:  systemctl --user restart openclaw-gateway.service");
