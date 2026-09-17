"""Synthetic visual diagnostics with deterministic field-level grading."""
import json
import re


def grade(text, expected):
    raw = text.strip()
    match = re.fullmatch(r'```(?:json)?\s*(.*?)\s*```', raw, re.S)
    if match:
        raw = match.group(1)
    try:
        answer = json.loads(raw)
        if not isinstance(answer, dict):
            raise ValueError('expected JSON object')
    except (ValueError, TypeError) as exc:
        return {'score':0, 'max_score':len(expected), 'checks':{k:False for k in expected}, 'parse_error':str(exc)}
    checks = {k: k in answer and type(answer[k]) is type(value) and answer[k] == value for k,value in expected.items()}
    return {'score':sum(checks.values()), 'max_score':len(expected), 'checks':checks, 'parsed':answer}


def run_suite(tasks, url, model, key_file, output, *, template_kwargs=None, max_tokens=1024):
    """template_kwargs replaces the default {'reasoning_effort': 'low'} — that
    default is GLM's knob; Qwen3.5 ignores it and thinks until max_tokens."""
    import base64
    import hashlib
    import time
    import urllib.request
    import urllib.error
    from pathlib import Path
    from eval_runtime import atomic_write_json
    key=Path(key_file).read_text().strip()
    result={'suite':'synthetic-vision-v1','model':model,'endpoint':url,'status':'partial','score':0,'max_score':sum(len(t['expected']) for t in tasks),'tasks':[], 'settings':{'temperature':0,'max_tokens':max_tokens,'chat_template_kwargs':{'reasoning_effort':'low'} if template_kwargs is None else template_kwargs,'retry':False}}
    atomic_write_json(output,result)
    for task in tasks:
        data=Path(task['image']).read_bytes()
        row={**task,'image_sha256':hashlib.sha256(data).hexdigest(),'status':'requesting'}
        result['tasks'].append(row); atomic_write_json(output,result)
        payload={'model':model,'messages':[{'role':'user','content':[{'type':'text','text':task['question']+' Return only the JSON object, no explanation.'},{'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(data).decode()}}]}], **{k:val for k,val in result['settings'].items() if k!='retry'}}
        started=time.monotonic()
        try:
            request=urllib.request.Request(url,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
            with urllib.request.urlopen(request,timeout=240) as response:
                raw=json.load(response)
            row['raw_response']=raw
            row['elapsed_s']=round(time.monotonic()-started,3)
            atomic_write_json(output,result)
            text=raw['choices'][0]['message'].get('content') or ''
            row.update(grade(text,task['expected']),status='complete')
        except (urllib.error.URLError,TimeoutError,OSError,ValueError,KeyError,IndexError) as exc:
            row.update(error=f'{type(exc).__name__}: {exc}',status='error')
            result['status']='aborted'
            atomic_write_json(output,result)
            print(json.dumps({'task':task['id'],'error':row['error']}),flush=True)
            return result
        result['score']=sum(r.get('score',0) for r in result['tasks'])
        atomic_write_json(output,result)
        print(json.dumps({k:row[k] for k in ('id','difficulty','score','max_score','elapsed_s','checks')}),flush=True)
    result['status']='complete'
    result['perfect_tasks']=sum(r['score']==r['max_score'] for r in result['tasks'])
    result['tiers']={tier:{'score':sum(r['score'] for r in result['tasks'] if r['difficulty']==tier),'max_score':sum(r['max_score'] for r in result['tasks'] if r['difficulty']==tier)} for tier in ('easy','medium','hard')}
    atomic_write_json(output,result)
    return result


if __name__=='__main__':
    import argparse
    from pathlib import Path
    from vision_fixtures import build_suite
    parser=argparse.ArgumentParser()
    parser.add_argument('--fixtures',required=True)
    parser.add_argument('--url',required=True)
    parser.add_argument('--model',required=True)
    parser.add_argument('--key-file',required=True)
    parser.add_argument('--output',required=True)
    parser.add_argument('--template-kwargs',metavar='JSON',help="chat_template_kwargs to send instead of the default {'reasoning_effort': 'low'}; e.g. '{\"enable_thinking\": false}' for Qwen3.5")
    parser.add_argument('--max-tokens',type=int,default=1024)
    args=parser.parse_args()
    manifest=Path(args.fixtures)/'manifest.json'
    tasks=json.loads(manifest.read_text())['tasks'] if manifest.exists() else build_suite(args.fixtures)
    result=run_suite(tasks,args.url,args.model,args.key_file,args.output,
                     template_kwargs=json.loads(args.template_kwargs) if args.template_kwargs else None,
                     max_tokens=args.max_tokens)
    print(json.dumps({k:result.get(k) for k in ('status','score','max_score','perfect_tasks','tiers')}))
    raise SystemExit(0 if result['status']=='complete' else 1)
