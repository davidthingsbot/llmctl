"""Paired Mistral eval using verified top-level reasoning_effort and raw archives."""
import datetime,fcntl,io,json,pathlib,sys,threading,time,urllib.request,urllib.error,subprocess
ROOT=pathlib.Path('/home/david/work/llmctl');sys.path.insert(0,str(ROOT/'evals'))
import work_quality_suite as work
import deep_reasoning_suite as deep
import concurrency_sweep as concurrency
from vision_suite import run_suite
from eval_runtime import atomic_write_json
OUT=ROOT/'evals/results/dw-spark0'/('mistral-tp2-paired-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'));OUT.mkdir(parents=True)
URL='http://127.0.0.1:19440/v1/chat/completions'; MODEL='mistral-medium-3.5-nvfp4-tp2';KEY=pathlib.Path('/home/david/.config/vllm/api-keys')
lock=open('/home/david/.config/llmctl/experiment-sequence.lock','w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
original_open=urllib.request.urlopen
phase={'mode':'none','suite':'initializing'};counter=0;mutex=threading.Lock();stop=threading.Event()
report={'status':'running','model':MODEL,'text_max_tokens':32768,'vision_max_tokens':16384,'concurrency_max_tokens':1024,'request_timeout_s':7200,'modes':{},'note':'Top-level reasoning_effort sent explicitly; no synthetic reasoning prompts. Raw reasoning and final content archived separately in API JSON. Concurrency is a bounded token-generation test, not task-completion scoring.'}

def capture_open(request,*args,**kwargs):
    global counter
    if not isinstance(request,urllib.request.Request) or request.full_url!=URL:
        return original_open(request,*args,**kwargs)
    payload=json.loads(request.data);payload.pop('chat_template_kwargs',None);payload['reasoning_effort']=phase['mode']
    request=urllib.request.Request(URL,data=json.dumps(payload).encode(),headers=dict(request.header_items()),method='POST')
    with mutex:
        counter+=1; ident=f'{counter:04d}-{phase["suite"]}'
    folder=OUT/phase['mode']/'raw';folder.mkdir(parents=True,exist_ok=True)
    record={'mode':phase['mode'],'suite':phase['suite'],'request':payload,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    atomic_write_json(folder/(ident+'-request.json'),record)
    started=time.monotonic()
    # One response timeout in both modes. Existing suites use a smaller default.
    kwargs['timeout']=7200
    response=original_open(request,**kwargs)
    if payload.get('stream'):
        return response  # Preserve streaming timing; sweep stores throughput/failures.
    with response:
        data=response.read()
    atomic_write_json(folder/(ident+'-response.json'),{'elapsed_s':time.monotonic()-started,'response':json.loads(data)})
    return io.BytesIO(data)

def memory():
    with (OUT/'memory.jsonl').open('a',buffering=1) as f:
        while not stop.is_set():
            r={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),**phase}
            try:
                r['head_available_gib']=int(next(l.split()[1] for l in pathlib.Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:')))/1048576
                p=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=5','dw-spark1','free -b'],capture_output=True,text=True,timeout=10)
                if p.returncode:raise RuntimeError('worker memory unavailable')
                r['worker_available_gib']=int(next(l.split()[-1] for l in p.stdout.splitlines() if l.startswith('Mem:')))/2**30
            except Exception as exc:r['error']=str(exc)
            f.write(json.dumps(r)+'\n');stop.wait(5)

def health():
    with original_open('http://127.0.0.1:19440/health',timeout=5) as r:assert r.status==200

def run_main(module,arguments):
    saved=sys.argv;sys.argv=[module.__file__,*arguments]
    try:module.main()
    finally:sys.argv=saved

tasks=[]
for p in ['vision-v1/manifest.json','vision-v2/hard-manifest.json','vision-candidates-extra10/manifest.json']:
    tasks+=json.loads((ROOT/'evals/fixtures'/p).read_text())['tasks']
assert len(tasks)==25
urllib.request.urlopen=capture_open
thread=threading.Thread(target=memory,daemon=True);thread.start()
print('RESULT_DIRECTORY',OUT,flush=True)
failure=None
try:
    for mode in ['none','high']:
        dest=OUT/mode;dest.mkdir(exist_ok=True);phase['mode']=mode
        report['modes'][mode]={'status':'running'};atomic_write_json(OUT/'status.json',report)
        phase['suite']='vision';health()
        result=run_suite(tasks,URL,MODEL,KEY,dest/'vision.json',request_settings={'max_tokens':16384,'chat_template_kwargs':{}})
        result['top_level_reasoning_effort']=mode;atomic_write_json(dest/'vision.json',result)
        if result['status']!='complete':raise RuntimeError(mode+' vision aborted')
        report['modes'][mode]['vision']={'score':result['score'],'max_score':result['max_score']}
        for module in (work,deep):
            name=pathlib.Path(module.__file__).stem;phase['suite']=name;health()
            print('START',mode,name,flush=True)
            run_main(module,['--url',URL,'--model',MODEL,'--key-file',str(KEY),'--extended','--no-template-kwargs','--min-tokens','32768','--retry','--retry-credit','0.7','--output',str(dest/(name+'.json'))])
            result=json.loads((dest/(name+'.json')).read_text());result['top_level_reasoning_effort']=mode;atomic_write_json(dest/(name+'.json'),result)
            if not result.get('complete') or any(t.get('error') or t.get('retry_error') for t in result['tasks']):raise RuntimeError(mode+' '+name+' errors; inspect checkpoints')
            report['modes'][mode][name]={'score':result['score'],'max_score':result['max_score']}
        phase['suite']='concurrency';health()
        run_main(concurrency,['--url',URL,'--model',MODEL,'--key-file',str(KEY),'--template-kwargs','{}','--max-tokens','1024','--output',str(dest/'concurrency.json')])
        result=json.loads((dest/'concurrency.json').read_text());result['top_level_reasoning_effort']=mode;atomic_write_json(dest/'concurrency.json',result)
        if any(x.get('failed') for x in result['results']):raise RuntimeError(mode+' concurrency failures')
        health();report['modes'][mode]['status']='complete';atomic_write_json(OUT/'status.json',report)
        print('MODE_COMPLETE',mode,json.dumps(report['modes'][mode]),flush=True)
    report['status']='complete'
except Exception as exc:
    failure=exc;report['status']='blocked';report['error']=str(exc);print('BLOCKED',str(exc),flush=True)
finally:
    urllib.request.urlopen=original_open;stop.set();thread.join(15);atomic_write_json(OUT/'status.json',report);print('FINAL',json.dumps(report),flush=True)
if failure is not None:raise SystemExit(1)
