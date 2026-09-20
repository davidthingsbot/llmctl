"""Authorized sequential dual-Spark experiments; no rollback or repointing."""
import datetime,fcntl,json,os,pathlib,subprocess,sys,threading,time,urllib.request
ROOT=pathlib.Path('/home/david/work/llmctl');sys.path.insert(0,str(ROOT/'evals'))
from vision_suite import run_suite
from eval_runtime import atomic_write_json
OUT=ROOT/'evals/results/dw-spark0'/('dual-vision-sequence-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
OUT.mkdir(parents=True)
KEY=pathlib.Path('/home/david/.config/vllm/api-keys')
lock=open('/home/david/.config/llmctl/experiment-sequence.lock','w')
fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
stop=threading.Event()
phase={'model':None,'step':'initializing'}

def sampler():
    with (OUT/'memory.jsonl').open('a',buffering=1) as f:
        while not stop.is_set():
            row={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),**phase}
            try:
                row['head_available_gib']=int(next(l.split()[1] for l in pathlib.Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:')))/1048576
                r=subprocess.run(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=5','dw-spark1','free -b'],capture_output=True,text=True,timeout=10)
                if r.returncode: raise RuntimeError('worker probe failed')
                row['worker_available_gib']=int(next(l.split()[-1] for l in r.stdout.splitlines() if l.startswith('Mem:')))/2**30
            except Exception as exc: row['error']=str(exc)
            f.write(json.dumps(row)+'\n');stop.wait(5)

def run(command,log,timeout):
    print('RUN',phase,log.name,flush=True)
    with log.open('w') as handle:
        subprocess.run(command,cwd=ROOT,stdout=handle,stderr=subprocess.STDOUT,env={**os.environ,'STATS':'0'},timeout=timeout,check=True)

def healthy(port):
    with urllib.request.urlopen(f'http://127.0.0.1:{port}/health',timeout=5) as r:
        if r.status!=200: raise RuntimeError('model health failed')

manifests=['vision-v1/manifest.json','vision-v2/hard-manifest.json','vision-candidates-extra10/manifest.json']
tasks=[]
for name in manifests: tasks+=json.loads((ROOT/'evals/fixtures'/name).read_text())['tasks']
assert len(tasks)==25 and len({t['id'] for t in tasks})==25
report={'status':'running','vision_max_tokens':4096,'task_count':len(tasks),'model_runs':[]}
thread=threading.Thread(target=sampler,daemon=True);thread.start()
print('RESULT_DIRECTORY',OUT,flush=True)
try:
    phase.update(model='mistral-medium-vision',step='stop-completed-diagnostic')
    run(['./llmctl','down','mistral-medium-vision'],OUT/'stop-mistral.log',180)
    subprocess.run(['systemctl','--user','stop','mistral-vision-memguard.service'],check=True,timeout=20)
    models=[('glm53-exl3','GLM-5.3-Flash-EXL3',8005,{'reasoning_effort':'low'}),('qwen38-flash-next-tp2','qwen38-flash-next-tp2',8004,{'enable_thinking':False})]
    for index,(entry,model,port,kwargs) in enumerate(models):
        dest=OUT/entry;dest.mkdir(); record={'entry':entry,'model':model,'status':'starting','template_kwargs':kwargs};report['model_runs'].append(record)
        phase.update(model=entry,step='load');atomic_write_json(OUT/'status.json',report)
        try:
            run(['./llmctl','up','--no-point',entry],dest/'startup.log',4200)
            healthy(port)
            phase['step']='vision';record['status']='vision';atomic_write_json(OUT/'status.json',report)
            vision=run_suite(tasks,f'http://127.0.0.1:{port}/v1/chat/completions',model,KEY,dest/'vision.json',request_settings={'max_tokens':4096,'chat_template_kwargs':kwargs})
            if vision['status']!='complete': raise RuntimeError('vision run aborted; inspect raw results')
            record['vision_score']=vision['score'];record['vision_max_score']=vision['max_score']
            for suite in ['work_quality_suite','deep_reasoning_suite']:
                healthy(port);phase['step']=suite;record['status']=suite;atomic_write_json(OUT/'status.json',report)
                run([sys.executable,'evals/'+suite+'.py','--url',f'http://127.0.0.1:{port}/v1/chat/completions','--model',model,'--key-file',str(KEY),'--extended','--template-kwargs',json.dumps(kwargs),'--min-tokens','12000','--retry','--retry-credit','0.7','--output',str(dest/(suite+'.json'))],dest/(suite+'.log'),10800)
                result=json.loads((dest/(suite+'.json')).read_text())
                if not result.get('complete') or any(t.get('error') or t.get('retry_error') for t in result['tasks']): raise RuntimeError(suite+' incomplete/request errors; see saved results')
                record[suite]={'score':result['score'],'max_score':result['max_score']}
            healthy(port);phase['step']='concurrency'
            run([sys.executable,'evals/concurrency_sweep.py','--url',f'http://127.0.0.1:{port}/v1/chat/completions','--model',model,'--key-file',str(KEY),'--template-kwargs',json.dumps(kwargs),'--output',str(dest/'concurrency.json')],dest/'concurrency.log',1200)
            sweep=json.loads((dest/'concurrency.json').read_text())
            if any(r.get('failed') for r in sweep['results']): raise RuntimeError('concurrency request failures')
            healthy(port);record['status']='complete';print('MODEL_COMPLETE',json.dumps(record),flush=True)
        except Exception as exc:
            record['status']='blocked';record['error']=str(exc);print('MODEL_BLOCKED',json.dumps(record),flush=True)
        atomic_write_json(OUT/'status.json',report)
        if index<len(models)-1:
            phase['step']='stop-before-next-candidate'
            run(['./llmctl','down',entry],dest/'stop.log',180)
    report['status']='complete' if all(r['status']=='complete' for r in report['model_runs']) else 'completed_with_blockers'
finally:
    atomic_write_json(OUT/'status.json',report);stop.set();thread.join(15)
    print('SEQUENCE_STATUS',json.dumps(report),flush=True)
if report['status']!='complete':raise SystemExit(1)
