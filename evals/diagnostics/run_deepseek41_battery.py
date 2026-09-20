"""Stage V4.1, launch exclusively, execute authorized text battery. No rollback."""
import datetime,fcntl,json,os,pathlib,subprocess,sys,threading,time,urllib.request,uuid
ROOT=pathlib.Path('/home/david/work/llmctl'); RECIPE=pathlib.Path('/home/david/work/deepseek41-exl3')
sys.path.insert(0,str(ROOT/'evals'))
from eval_runtime import atomic_write_json
OUT=ROOT/'evals/results/dw-spark0'/('deepseek41-battery-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'));OUT.mkdir(parents=True)
keyfile=pathlib.Path('/home/david/.config/vllm/api-keys');key=keyfile.read_text().strip();BASE='http://127.0.0.1:8007';MODEL='DeepSeek-v4.1-Flash-EXL3'
lock=open('/home/david/.config/llmctl/experiment-sequence.lock','w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
state={'status':'staging','vision':'unsupported: selected SM12x kernel is text-only','model':MODEL,'template_kwargs':{'enable_thinking':False},'context_cap':262144};stop=threading.Event()
def run(args,name,timeout):
    print('STEP',name,flush=True);state['step']=name;atomic_write_json(OUT/'status.json',state)
    with (OUT/(name+'.log')).open('w') as f:subprocess.run(args,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,env={**os.environ,'STATS':'0'},timeout=timeout,check=True)
def sample():
    with (OUT/'memory.jsonl').open('a',buffering=1) as f:
        while not stop.is_set():
            row={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'step':state.get('step')}
            try:
                row['head_available_gib']=int(next(l.split()[1] for l in pathlib.Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:')))/1048576
                r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=5','dw-spark1','free -b'],capture_output=True,text=True,timeout=10)
                if r.returncode:raise RuntimeError('worker memory unavailable')
                row['worker_available_gib']=int(next(l.split()[-1] for l in r.stdout.splitlines() if l.startswith('Mem:')))/2**30
                state['latest_memory']={**row,'sampled_monotonic':time.monotonic()}
            except Exception as exc:
                state.pop('latest_memory',None)
                row['error']=str(exc)
            f.write(json.dumps(row)+'\n');stop.wait(5)
def health():
    with urllib.request.urlopen(BASE+'/health',timeout=5) as r:assert r.status==200

def post(endpoint,payload,timeout=900):
    req=urllib.request.Request(BASE+endpoint,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
    with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)

def chat(messages,**kwargs):
    return post('/v1/chat/completions',{'model':MODEL,'messages':messages,'temperature':0,'max_tokens':512,'chat_template_kwargs':{'enable_thinking':False},**kwargs})

thread=threading.Thread(target=sample,daemon=True);thread.start();print('RESULT_DIRECTORY',OUT,flush=True)
failure=None
try:
    # Wait for the already-started copy, then re-run resumable sync to verify completion.
    deadline=time.monotonic()+3600
    while pathlib.Path('/proc/246761').exists():
        if time.monotonic()>deadline:raise TimeoutError('initial weight copy still running')
        time.sleep(5)
    run(['rsync','-a','--partial','--info=stats2','--exclude=.cache',str(RECIPE/'model'),str(RECIPE/'engram-src'),'david@10.100.100.11:/home/david/work/deepseek41-exl3/'],'verify-weight-sync',3600)
    run(['./llmctl','down','qwen38-flash-next-tp2'],'stop-qwen',180)
    run(['./llmctl','up','--no-point','deepseek41-exl3'],'startup',4200)
    health();state['status']='testing'
    state['step']='smoke'
    reply=chat([{'role':'user','content':'Reply with exactly READY.'}]);atomic_write_json(OUT/'text-smoke.json',reply)
    if 'READY' not in (reply['choices'][0]['message'].get('content') or ''):raise RuntimeError('text smoke failed')
    tools=[{'type':'function','function':{'name':'get_weather','description':'Retrieve current weather for a city','parameters':{'type':'object','properties':{'city':{'type':'string'}},'required':['city']}}}]
    messages=[{'role':'user','content':'Use get_weather to check the weather in Seattle.'}]
    reply=chat(messages,tools=tools,tool_choice='auto');atomic_write_json(OUT/'tool-smoke.json',reply)
    message=reply['choices'][0]['message'];calls=message.get('tool_calls') or []
    if len(calls)!=1 or calls[0]['function']['name']!='get_weather':raise RuntimeError('tool call missing/unexpected')
    if json.loads(calls[0]['function']['arguments']).get('city')!='Seattle':raise RuntimeError('tool arguments failed')
    # Explicit synthetic tool output tests protocol completion, not real weather.
    response=chat(messages+[message,{'role':'tool','tool_call_id':calls[0]['id'],'content':'{"condition":"rain","temperature_c":12}'}],tools=tools)
    atomic_write_json(OUT/'tool-roundtrip.json',response)
    for suite in ['work_quality_suite','deep_reasoning_suite']:
        health();dest=OUT/(suite+'.json')
        run([sys.executable,'evals/'+suite+'.py','--url',BASE+'/v1/chat/completions','--model',MODEL,'--key-file',str(keyfile),'--extended','--template-kwargs','{"enable_thinking":false}','--min-tokens','12000','--retry','--retry-credit','0.7','--output',str(dest)],suite,10800)
        data=json.loads(dest.read_text())
        if not data.get('complete') or any(t.get('error') or t.get('retry_error') for t in data['tasks']):raise RuntimeError(suite+' errors; preserved partial results')
        state[suite]={'score':data['score'],'max_score':data['max_score']}
    health()
    run([sys.executable,'evals/concurrency_sweep.py','--url',BASE+'/v1/chat/completions','--model',MODEL,'--key-file',str(keyfile),'--template-kwargs','{"enable_thinking":false}','--output',str(OUT/'concurrency.json')],'concurrency',1800)
    if any(r.get('failed') for r in json.loads((OUT/'concurrency.json').read_text())['results']):raise RuntimeError('concurrency request failure')
    for target in [32000,100000,200000]:
        state['step']='long-context-'+str(target);health()
        memory=state.get('latest_memory',{})
        sample_age=time.monotonic()-memory.get('sampled_monotonic',float('-inf'))
        if sample_age>15 or any(memory.get(k,0)<5 for k in ['head_available_gib','worker_available_gib']):
            state['long_context_gate']='stopped before '+str(target)+': memory sample unavailable, stale, or below 5 GiB';break
        needle=uuid.uuid4().hex;unit='The archived equipment record contains routine inventory notes.\n';prefix='Archive key: '+needle+'\n';suffix='\nReturn only the archive key at the beginning.'
        count=post('/tokenize',{'model':MODEL,'prompt':prefix+unit*1000+suffix})['count'];prompt=prefix+unit*int(target*1000/count)+suffix
        actual=post('/tokenize',{'model':MODEL,'prompt':prompt})['count']
        if actual>240000:raise RuntimeError('long prompt exceeds safety ceiling')
        started=time.monotonic();response=chat([{'role':'user','content':prompt}],max_tokens=128)
        row={'target':target,'tokenized_count':actual,'expected':needle,'seconds':time.monotonic()-started,'response':response}
        row['correct']=(response['choices'][0]['message'].get('content') or '').strip()==needle
        atomic_write_json(OUT/('long-'+str(target)+'.json'),row)
        if not row['correct']:raise RuntimeError('long-context retrieval failed at '+str(target))
    health();state['status']='completed_with_safety_gate' if state.get('long_context_gate') else 'complete'
except Exception as exc:
    failure=exc;state['status']='blocked';state['error']=str(exc);print('BLOCKED',str(exc),flush=True)
finally:
    stop.set();thread.join(15);atomic_write_json(OUT/'status.json',state);print('FINAL',json.dumps(state),flush=True)
if failure is not None:raise SystemExit(1)
