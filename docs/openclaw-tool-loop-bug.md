# Embedded/local-model agent runs have no per-turn tool-iteration cap → unbounded loop

**openclaw version:** 2026.6.11
**Provider:** local OpenAI-compatible endpoint (vLLM) serving Qwen3.6 (dense 27B FP8 and 35B-A3B MoE FP8)
**Agent:** default `agent:main:main`, heartbeat enabled (`agents.defaults.heartbeat.every: 30m`)

## Summary

A single agent turn can loop **indefinitely** when the model emits terminating
text **and** a tool call in the same assistant message every iteration. The
embedded (local-model) run loop continues as long as the assistant message
contains a tool call — which is correct in general — but there is **no per-turn
cap on the number of tool-execution iterations**, so a model that staples a tool
call onto every message never terminates and nothing stops it.

Observed: a heartbeat turn ran **113 iterations over ~21 minutes**, one model
call every ~10s (and ~2s on the faster MoE model), and only stopped when the
gateway was manually restarted.

## Reproduction

1. Point an agent at a local model (no per-call billing to mask the cost).
2. Give the heartbeat/agent a task whose instructions include writing a small
   state file each run (e.g. "record your check state to `memory/state.json`,
   then reply `HEARTBEAT_OK`").
3. With an accreted/compacted session context, the model begins emitting
   `HEARTBEAT_OK` **and** a `write` tool call in the same turn, every turn.
4. The runner executes the write, appends the result, re-calls the model, which
   again returns `HEARTBEAT_OK` + a write. This never ends.

Trajectory shows every iteration as `[thinking, toolCall]` + `Tool result
(write): Successfully wrote NNN bytes`, and the compaction summary is pages of
the same repeated write — which further primes the repetition.

## Root cause

The assistant keeps returning a tool call, so the loop keeps going. The text is
not the problem (a tool call legitimately means "I need this result"); the
problem is the **absence of any ceiling** on tool-execution iterations within a
single turn.

The caps that exist do **not** cover this:

- `agents.defaults.runRetries` (base 24 + perProfile 8×providers) →
  `MAX_RUN_LOOP_ITERATIONS` in the embedded runner's `while(true)`, tagged
  `[run-retry-limit]`. This bounds **provider-fallback retries** (failed
  attempts). A loop of **succeeding** tool calls never increments it.
- `maxTurns` → only wired to the Claude-Code backend adapter and the xAI search
  tool; the embedded/local path never receives it.
- `session.agentToAgent.maxPingPongTurns` (default 5) → agent-to-agent exchanges
  only.
- `maxConsecutiveFailures` → typing-indicator guard.
- `tools.codeMode.maxPendingToolCalls` → code-mode only.
- Stall detector → emits `classification=stalled_agent_run recovery=none`, and
  in any case does not fire here because each tool call **completes** (the run
  looks like it is making progress).

## Impact

- On a local model there is no per-call cost to surface the runaway, so it can
  run for many minutes/hours until a human notices.
- Sustained GPU/power draw; blocks the agent lane; on a later update this same
  bloated session also made compaction time out and fall through to (expired)
  cloud fallbacks, wedging the main lane entirely.

## Proposed fix

Add a configurable **per-turn tool-iteration cap** to the embedded conversation
loop (the counterpart of `maxTurns` for the local path, and of Hermes'
`agent.max_turns`):

- New config, e.g. `agents.defaults.maxToolIterations` (default ~40–60).
- Increment per tool-execution round within a turn; when it exceeds the cap,
  terminate the turn with a clear final message (e.g. "tool-iteration limit
  reached") instead of re-calling the model.
- Optionally, a lightweight identical-tool-call guard (same tool name + same
  arguments N times consecutively) to catch degenerate repetition earlier.

This mirrors behavior the Claude-Code path and other harnesses (e.g. Hermes'
`max_turns: 60`) already have, and bounds the blast radius regardless of model
or context.

## Workaround in place

An external watchdog restarts the agent gateway when a single gateway client
drives a sustained request loop — but that is blunt (it drops in-flight work and
session context). A native per-turn cap is the correct fix.
