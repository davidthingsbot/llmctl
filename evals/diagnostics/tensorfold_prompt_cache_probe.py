"""Prompt-cache probe for the TensorFold recipe's v1.3.1 claim (issues #12/#13): three conversations taking turns,
~4.5k tokens of history each, six warm rounds. Reports what share of the prompt tokens the engine served from its
kept prompt states (frontend /health cached_tokens_total vs prompt_tokens_total deltas). Thinking off, short replies.
usage: tensorfold_prompt_cache_probe.py <label> [conversations=3] [rounds=6]   (Claude, 2026-10-02)"""
import json, pathlib, sys, time, urllib.request
BASE = 'http://127.0.0.1:8005'; MODEL = 'GLM-5.3-Flash-EXL3'
KEY = next(k.strip() for k in pathlib.Path('/home/david/.config/vllm/api-keys').read_text().splitlines() if k.strip())
label = sys.argv[1]; n_conv = int(sys.argv[2]) if len(sys.argv) > 2 else 3; rounds = int(sys.argv[3]) if len(sys.argv) > 3 else 6
def call(path, payload=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(payload).encode() if payload is not None else None,
                                 headers={'Authorization': 'Bearer ' + KEY, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=600) as r: return json.load(r)
def health(): h = call('/health'); return h['prompt_tokens_total'], h['cached_tokens_total']
# ~4.5k tokens of distinct filler per conversation so the histories cannot share a prefix
filler = [' '.join(f'conversation {c} fact {i}: the {["red","green","blue"][c%3]} ledger entry number {i*7919 % 10007} was filed on day {i%28+1}.' for i in range(260)) for c in range(n_conv)]
convs = [[{'role': 'system', 'content': 'You answer in one short sentence.'},
          {'role': 'user', 'content': f'Here is a long record you must remember.\n{filler[c]}\nAcknowledge in one word.'}] for c in range(n_conv)]
# cold turn 1 for every conversation (nothing to reuse yet)
for c in range(n_conv):
    r = call('/v1/chat/completions', dict(model=MODEL, messages=convs[c], temperature=0, max_tokens=24, chat_template_kwargs={'enable_thinking': False}))
    convs[c].append({'role': 'assistant', 'content': r['choices'][0]['message']['content'] or ''})
p0, c0 = health(); t0 = time.time(); per_turn = []
for rnd in range(rounds):
    for c in range(n_conv):
        convs[c].append({'role': 'user', 'content': f'Round {rnd+1}: what color is the ledger in your record? One word.'})
        pb, cb = health(); tb = time.time()
        r = call('/v1/chat/completions', dict(model=MODEL, messages=convs[c], temperature=0, max_tokens=24, chat_template_kwargs={'enable_thinking': False}))
        pa, ca = health()
        convs[c].append({'role': 'assistant', 'content': r['choices'][0]['message']['content'] or ''})
        per_turn.append({'round': rnd+1, 'conv': c, 'prompt_tokens': pa-pb, 'cached': ca-cb, 'seconds': round(time.time()-tb, 2),
                         'reply': (r['choices'][0]['message']['content'] or '').strip()[:40]})
p1, c1 = health()
res = {'label': label, 'conversations': n_conv, 'rounds': rounds, 'warm_prompt_tokens': p1-p0, 'warm_cached_tokens': c1-c0,
       'cache_hit_share': round((c1-c0)/max(1, p1-p0), 4), 'warm_wall_seconds': round(time.time()-t0, 1), 'turns': per_turn}
out = pathlib.Path(f'/home/david/work/llmctl/evals/results/dw-spark0/glm53-tensorfold-v132-update/prompt-cache-{label}.json')
out.parent.mkdir(parents=True, exist_ok=True); out.write_text(json.dumps(res, indent=2) + '\n')
print(f"{label}: {n_conv} conversations x {rounds} warm rounds: prompt tokens {p1-p0}, served from cache {c1-c0} "
      f"= {res['cache_hit_share']*100:.1f}% hit, {res['warm_wall_seconds']} s wall; wrong answers: "
      f"{sum(1 for t in per_turn if ['red','green','blue'][t['conv']%3] not in t['reply'].lower())}/{len(per_turn)}")
