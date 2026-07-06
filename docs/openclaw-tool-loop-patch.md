# OpenClaw tool-loop cap — local patch (re-apply after every OpenClaw update)

## What this is

A small patch to OpenClaw's embedded agent loop that **caps the number of
tool-call rounds per turn**, so a wedged turn self-terminates instead of looping
forever. It makes OpenClaw stop itself — the fix we actually want — rather than
relying on the external `llmctl watchdog` (which just restarts the gateway and
loses in-flight context).

Apply it with:

```sh
node ~/work/llmctl/scripts/patch-openclaw-tool-loop.js        # apply (idempotent)
node ~/work/llmctl/scripts/patch-openclaw-tool-loop.js --check   # is it applied?
node ~/work/llmctl/scripts/patch-openclaw-tool-loop.js --revert  # remove it
systemctl --user restart openclaw-gateway.service               # load it
```

Tune the cap at runtime (default **50**):

```
Environment=OPENCLAW_MAX_TOOL_ROUNDS=50   # in the gateway's systemd unit, or the shell for `openclaw agent --local`
```

## Why it's needed

OpenClaw's local-model run loop continues purely on whether the assistant's last
message contained a tool call. When a model emits terminating text (`HEARTBEAT_OK`)
**and** a tool call in the same turn — every turn — the loop never ends. There is
**no config knob** for a per-turn cap on the embedded path (verified against
2026.6.11; `maxTurns` only reaches the claude-code adapter + xAI search,
`runRetries` bounds provider-fallback *failures* not successful tool rounds, the
stall detector reports `recovery=none` and doesn't fire on a loop that keeps
completing calls). Observed impact: a heartbeat looped **113 times over 21 min**
until the gateway was manually restarted. Upstream bug report:
`docs/openclaw-tool-loop-bug.md` (file at github.com/openclaw/openclaw/issues).

## Why it needs re-applying after updates

`npm update` overwrites `node_modules/openclaw/dist`, and the dist filenames are
**content-hashed** — they change every release (e.g. `pi-embedded-rWtLEwl7.js`
in 2026.5.2 became part of `proxy-CoylXPU6.js` by 2026.6.11). So the patch cannot
key on a filename or line number.

## How the patch finds its target (so you can re-derive it if the anchors ever break)

The script scans `openclaw/dist/*.js` for the file containing **both** of these
unique anchor strings (1 occurrence each, as of 2026.6.11) and edits that file:

- **Declaration anchor:** `let hasMoreToolCalls = true;`
  → the script inserts `let __llmctlRounds = 0;` right after it (function-scope
  counter, above the inner tool loop).
- **Check anchor:** `hasMoreToolCalls = !executedToolBatch.terminate;`
  → the script appends, on the same line, a guard: increment `__llmctlRounds`
  each tool round, and when it reaches the cap force `hasMoreToolCalls = false`
  (which makes OpenClaw's own "no more tool calls → end turn" path fire) and log
  `[llmctl] tool-round cap (N) hit`.

The target loop lives in the function that streams the assistant response and
calls `executeToolCalls(...)` — structurally:

```js
while (true) {                                   // follow-up messages
  let hasMoreToolCalls = true;
  let __llmctlRounds = 0;                         // <-- inserted
  while (hasMoreToolCalls || pendingMessages.length > 0) {
    const message = await streamAssistantResponse(...);   // call the model
    const toolCalls = message.content.filter(c => c.type === "toolCall");
    hasMoreToolCalls = false;
    if (toolCalls.length > 0) {
      const executedToolBatch = await executeToolCalls(...);
      hasMoreToolCalls = !executedToolBatch.terminate;    // <-- guard appended here
    }
  }
}
```

If a future OpenClaw refactor renames these identifiers, the script aborts safely
(it never edits a file whose anchors aren't unique). To re-derive: find the file
containing `executeToolCalls(`, locate the enclosing `while` loop that re-invokes
the model while there are tool calls, and place a per-turn counter + cap there.

## Verifying it works

```sh
# drive the embedded agent through many sequential tool rounds with a low cap:
OPENCLAW_MAX_TOOL_ROUNDS=3 openclaw agent --local --session-id captest \
  -m 'Create ten files /tmp/llmtest_1.txt .. llmtest_10.txt, one write_file call each, strictly one at a time.'
# expect: log "[llmctl] tool-round cap (3) hit", and only 3 files written (not 10).
```

## Relationship to the watchdog

Keep `llmctl watchdog` installed as a **backstop**: it covers the window between
an OpenClaw update (which reverts this patch) and the next time you re-run the
patch script. The patch is the primary fix; the watchdog is the safety net for
when the patch is temporarily gone.
