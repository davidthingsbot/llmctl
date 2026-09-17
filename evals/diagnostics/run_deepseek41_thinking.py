"""DeepSeek V4.1 high-thinking follow-up; raw responses and checkpoints retained."""
import datetime,fcntl,io,json,os,pathlib,subprocess,sys,threading,time,urllib.request
ROOT=pathlib.Path('/home/david/work/llmctl');sys.path.insert(0,str(ROOT/'evals'))
import deep_reasoning_suite as deep
import work_quality_suite as work
from eval_runtime import atomic_write_json
ENTRY=os.environ.get('THINKING_ENTRY','deepseek41-exl3')
STOP_ENTRY=os.environ.get('THINKING_STOP_ENTRY','mistral-medium-vision-tp2')
PREFIX=os.environ.get('THINKING_RESULT_PREFIX','deepseek41-thinking-high')
OUT=ROOT/'evals/results/dw-spark0'/(PREFIX+'-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'));OUT.mkdir(parents=True)
BASE=os.environ.get('THINKING_BASE_URL','http://127.0.0.1:8007')
URL=BASE+'/v1/chat/completions';MODEL=os.environ.get('THINKING_MODEL','DeepSeek-v4.1-Flash-EXL3');KEY=pathlib.Path('/home/david/.config/vllm/api-keys');key=KEY.read_text().strip()
lock=open('/home/david/.config/llmctl/experiment-sequence.lock','w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
original_open=urllib.request.urlopen
phase='startup';counter=0;stop=threading.Event()
state={'status':'starting','model':MODEL,'template_kwargs':{'enable_thinking':True,'reasoning_effort':os.environ.get('THINKING_EFFORT','high')},'text_max_tokens':32768,'baseline_note':os.environ.get('THINKING_BASELINE_NOTE','Previous thinking-off battery used12000 output tokens, so report budget difference.'),'vision':os.environ.get('THINKING_VISION_STATUS','unsupported'),'suites':{}}

def save():
    state['phase']=phase;atomic_write_json(OUT/'status.json',state)
def run(args,name,timeout):
    with (OUT/(name+'.log')).open('w') as f:subprocess.run(args,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,env={**os.environ,'STATS':'0'},timeout=timeout,check=True)
def health():
    with original_open(BASE+'/health',timeout=5) as r:assert r.status==200

def capture(request,*args,**kwargs):
    global counter
    if not isinstance(request,urllib.request.Request) or request.full_url!=URL:return original_open(request,*args,**kwargs)
    payload=json.loads(request.data);counter+=1;name=f'{counter:04d}-{phase}'
    atomic_write_json(OUT/(name+'-request.json'),payload)
    kwargs['timeout']=7200
    started=time.monotonic()
    with original_open(request,**kwargs) as r:data=r.read()
    atomic_write_json(OUT/(name+'-response.json'),{'elapsed_s':time.monotonic()-started,'response':json.loads(data)})
    return io.BytesIO(data)

def chat(messages,**extra):
    payload={'model':MODEL,'messages':messages,'temperature':0,'max_tokens':32768,'chat_template_kwargs':state['template_kwargs'],**extra}
    req=urllib.request.Request(URL,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
    with capture(req) as r:return json.load(r)

def sampler():
    with (OUT/'memory.jsonl').open('a',buffering=1) as f:
        while not stop.is_set():
            row={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'phase':phase}
            try:
                row['head_available_gib']=int(next(l.split()[1] for l in pathlib.Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:')))/1048576
                r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=5','dw-spark1','free -b'],capture_output=True,text=True,timeout=10)
                if r.returncode:raise RuntimeError('worker probe failed')
                row['worker_available_gib']=int(next(l.split()[-1] for l in r.stdout.splitlines() if l.startswith('Mem:')))/2**30
            except Exception as exc:row['error']=str(exc)
            f.write(json.dumps(row)+'\n');stop.wait(5)

thread=threading.Thread(target=sampler,daemon=True);thread.start();save();print('RESULT_DIRECTORY',OUT,flush=True)
failure=None
try:
    run(['./llmctl','down',STOP_ENTRY],'stop-previous',180)
    run(['./llmctl','up','--no-point',ENTRY],'startup',4200)
    health();phase='reasoning-smoke';save()
    raw=chat([{'role':'user','content':'What is 17 times 19? Return only the integer as your final answer.'}],return_prompt_text=True)
    msg=raw['choices'][0]['message'];reason=msg.get('reasoning') or msg.get('reasoning_content') or ''
    if not reason or str(17*19)!=(msg.get('content') or '').strip():raise RuntimeError('thinking/final-answer smoke not verified; inspect raw response')
    state['smoke']={'reasoning_nonempty':True,'correct':True,'finish_reason':raw['choices'][0]['finish_reason']};state['status']='testing';save()
    urllib.request.urlopen=capture
    for module in [deep,work]:
        phase=pathlib.Path(module.__file__).stem;health();save();print('START',phase,flush=True)
        old=sys.argv
        sys.argv=[module.__file__,'--url',URL,'--model',MODEL,'--key-file',str(KEY),'--extended','--template-kwargs',json.dumps(state['template_kwargs']),'--min-tokens','32768','--retry','--retry-credit','0.7','--output',str(OUT/(phase+'.json'))]
        try:module.main()
        finally:sys.argv=old
        d=json.loads((OUT/(phase+'.json')).read_text())
        if not d.get('complete') or any(t.get('error') or t.get('retry_error') for t in d['tasks']):raise RuntimeError(phase+' request/checker errors; see checkpoints')
        state['suites'][phase]={'score':d['score'],'max_score':d['max_score'],'cost':d['cost']};save();print('SUITE_COMPLETE',phase,d['score'],d['max_score'],flush=True)
    phase='tool-check';health();save()
    tools=[{'type':'function','function':{'name':'get_weather','description':'Get current weather for a city','parameters':{'type':'object','properties':{'city':{'type':'string'}},'required':['city']}}}]
    messages=[{'role':'user','content':'Use get_weather to check the current weather in Seattle.'}]
    raw=chat(messages,tools=tools,tool_choice='auto');msg=raw['choices'][0]['message'];calls=msg.get('tool_calls') or []
    if len(calls)!=1 or calls[0]['function']['name']!='get_weather' or json.loads(calls[0]['function']['arguments']).get('city')!='Seattle':raise RuntimeError('tool check failed')
    # Synthetic tool response solely for protocol test; not a weather lookup.
    final=chat(messages+[msg,{'role':'tool','tool_call_id':calls[0]['id'],'content':'{"condition":"rain","temperature_c":12}'}],tools=tools)
    if not final['choices'][0]['message'].get('content'):raise RuntimeError('tool round-trip final missing')
    state['tool_check']='passed';health()
    if os.environ.get('THINKING_RUN_VISION')=='1':
        from vision_suite import run_suite
        phase='vision';save();tasks=[]
        for name in ['vision-v1/manifest.json','vision-v2/hard-manifest.json','vision-candidates-extra10/manifest.json']:
            tasks+=json.loads((ROOT/'evals/fixtures'/name).read_text())['tasks']
        visual=run_suite(tasks,URL,MODEL,KEY,OUT/'vision.json',request_settings={'max_tokens':16384,'chat_template_kwargs':state['template_kwargs']})
        if visual['status']!='complete':raise RuntimeError('vision incomplete; see checkpoints')
        state['vision']={'score':visual['score'],'max_score':visual['max_score'],'output_limit':16384}
        health()
    state['status']='complete'
except Exception as exc:
    failure=exc;state['status']='blocked';state['error']=str(exc);print('BLOCKED',str(exc),flush=True)
finally:
    urllib.request.urlopen=original_open;stop.set();thread.join(15);save();print('FINAL',json.dumps(state),flush=True)
if failure is not None:raise SystemExit(1)
