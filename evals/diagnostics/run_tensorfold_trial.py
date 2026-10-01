"""Isolated authorized TensorFold preparation -> startup -> retained evaluation battery.
No agent repointing, persistent default changes, restart loops or automatic rollback.
"""
import argparse,datetime,fcntl,json,os,pathlib,shutil,subprocess,sys,time,urllib.request,uuid
ROOT=pathlib.Path('/home/david/work/llmctl');RECIPE=pathlib.Path('/home/david/work/glm53-tensorfold')
sys.path.insert(0,str(ROOT/'evals'))
from eval_runtime import atomic_write_json
BASE='http://127.0.0.1:18888';MODEL='GLM-5.3-Flash-EXL3';WORKER='david@10.100.100.11'
KEYFILE=pathlib.Path('/home/david/.config/vllm/api-keys')
MANIFESTS=['vision-v1/manifest.json','vision-v2/hard-manifest.json','vision-candidates-extra10/manifest.json']

def command(args,timeout=30):
    return subprocess.run(args,capture_output=True,text=True,check=True,timeout=timeout)

def snapshot_attempt(out):
    """Copy every predecessor artifact once; callers must hold the experiment lock."""
    archive=out/'attempt-backups'
    archive.mkdir(exist_ok=True)
    dest=archive/(datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex)
    # Exclude only the root archive, retaining even nested directories of that name.
    shutil.copytree(out,dest,symlinks=True,ignore=lambda directory,names: ['attempt-backups'] if pathlib.Path(directory)==out else [])
    return dest

def valid_result(d,vision=False,concurrency=False):
    if concurrency:return bool(d.get('results')) and not any(r.get('failed') for r in d['results'])
    return (d.get('status')=='complete' if vision else bool(d.get('complete'))) and bool(d.get('tasks')) and not any(t.get('error') or t.get('retry_error') for t in d['tasks'])
def tasks():
    ts=[]
    for m in MANIFESTS:ts+=json.loads((ROOT/'evals/fixtures'/m).read_text())['tasks']
    assert len(ts)==25 and len({t['id'] for t in ts})==25 and sum(len(t['expected']) for t in ts)==78
    assert all(pathlib.Path(t['image']).is_file() for t in ts)
    return ts

def main():
    p=argparse.ArgumentParser();p.add_argument('--self-test',action='store_true');p.add_argument('--resume',type=pathlib.Path);a=p.parse_args()
    if a.self_test:
        tasks();assert valid_result({'complete':True,'tasks':[{}]});assert not valid_result({'complete':True,'tasks':[{'error':'bad'}]});assert not valid_result({'status':'partial','tasks':[{}]},vision=True)
        assert not valid_result({'results':[{'failed':1}]},concurrency=True)
        for suite in ['work_quality_suite','deep_reasoning_suite','vision_suite','concurrency_sweep']:
            command([sys.executable,str(ROOT/'evals'/(suite+'.py')),'--help'])
        command([sys.executable,str(ROOT/'evals/diagnostics/tensorfold_trial_memguard.py'),'--self-test'])
        print('PASS: CLI contracts, 25 fixtures/78 fields, guard logic, incomplete/error-result rejection');return
    # Acquire before creating the result directory or any predecessor snapshot.
    with open('/home/david/.config/llmctl/experiment-sequence.lock','a') as sequence:
        fcntl.flock(sequence,fcntl.LOCK_EX|fcntl.LOCK_NB)
        run_trial(a)

def run_trial(a):
    out=a.resume.resolve() if a.resume else ROOT/'evals/results/dw-spark0'/('glm53-tensorfold-high-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    if not a.resume:out.mkdir(parents=True)
    state={'status':'waiting_for_preparation','model':MODEL,'endpoint':BASE,'recipe_commit':command(['git','-C',str(RECIPE),'rev-parse','HEAD']).stdout.strip(),'reasoning_effort':'high','text_ceiling':32768,'vision_ceiling':16384,'temperature':0,'retry_credit':0.7,'routing':'unchanged','stages':{}}
    if a.resume:
        prior=json.loads((out/'status.json').read_text());assert prior['model']==MODEL and prior['recipe_commit']==state['recipe_commit']
        snapshot_attempt(out)
        state=prior;state['status']='resuming';state.pop('error',None)
    print('RESULT_DIRECTORY',out,flush=True)
    def save():atomic_write_json(out/'status.json',state)
    def stage(name):state['step']=name;print('STEP',name,flush=True);save()
    def memory():
        head=int(next(l.split()[1] for l in pathlib.Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:')))/1048576
        worker=command(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=5',WORKER,'free -b'],15)
        remote=int(next(l.split()[-1] for l in worker.stdout.splitlines() if l.startswith('Mem:')))/2**30
        row={'utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'head_available_gib':head,'worker_available_gib':remote,'step':state.get('step')}
        with (out/'memory.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
        if min(head,remote)<6:raise RuntimeError('fresh memory gate below 6 GiB')
        return row
    def request(path,payload=None,timeout=7200):
        req=urllib.request.Request(BASE+path,data=json.dumps(payload).encode() if payload is not None else None,headers={'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=timeout) as r:return json.load(r)
    def chat(messages,**kwargs):
        memory();return request('/v1/chat/completions',{'model':MODEL,'messages':messages,'temperature':0,'max_tokens':4096,'reasoning_effort':'high',**kwargs})
    def run(args,name,timeout):
        stage(name);memory();request('/health',timeout=10)
        with (out/(name+'.log')).open('w') as f:subprocess.run(args,cwd=ROOT,env={**os.environ,'STATS':'0'},stdout=f,stderr=subprocess.STDOUT,check=True,timeout=timeout)
    try:
        save();stage('waiting-for-prepare-lock')
        lock=open('/home/david/.local/state/glm53-tensorfold/prepare.lock','a');deadline=time.monotonic()+21600
        while True:
            try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);break
            except BlockingIOError:
                if time.monotonic()>deadline:raise TimeoutError('preparation did not finish within six hours')
                time.sleep(15)
        marker=pathlib.Path('/home/david/.local/state/glm53-tensorfold/prepared')
        if not marker.exists():raise RuntimeError('preparation ended without successful prepared marker; see prepare log')
        state['prepared_receipt']=marker.read_text();fcntl.flock(lock,fcntl.LOCK_UN);lock.close()
        for args in [['systemctl','--user','is-active','glm53-tf-trial-memguard.service'],['ssh','-o','BatchMode=yes',WORKER,'systemctl --user is-active glm53-tf-trial-memguard.service']]:command(args)
        if not a.resume:
            stage('startup');memory()
            with (out/'startup.log').open('w') as f:subprocess.run(['./start.sh'],cwd=RECIPE,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=4200)
        stage('smoke');health=request('/health',timeout=10);atomic_write_json(out/'health-initial.json',health)
        models=request('/v1/models',timeout=10);assert any(m['id']==MODEL for m in models['data']);atomic_write_json(out/'models.json',models)
        reply=chat([{'role':'user','content':'Reply with exactly READY.'}]);atomic_write_json(out/'text-smoke.json',reply);assert 'READY' in (reply['choices'][0]['message'].get('content') or '')
        reply=chat([{'role':'user','content':'What is 17 times 23? Give only the result.'}]);atomic_write_json(out/'reasoning-smoke.json',reply)
        msg=reply['choices'][0]['message'];assert msg.get('reasoning_content') or msg.get('reasoning'),'high reasoning trace missing'
        tools=[{'type':'function','function':{'name':'lookup_component','description':'Look up the specified electronic component','parameters':{'type':'object','properties':{'part':{'type':'string'}},'required':['part']}}}]
        messages=[{'role':'user','content':'Use lookup_component to look up MCP6002.'}]
        reply=chat(messages,tools=tools,tool_choice='auto');atomic_write_json(out/'tool-smoke.json',reply)
        msg=reply['choices'][0]['message'];calls=msg.get('tool_calls') or [];assert len(calls)==1 and calls[0]['function']['name']=='lookup_component';assert json.loads(calls[0]['function']['arguments'])['part']=='MCP6002'
        reply=chat(messages+[msg,{'role':'tool','tool_call_id':calls[0]['id'],'content':'{"part":"MCP6002","channels":2,"kind":"op-amp"}'}],tools=tools);atomic_write_json(out/'tool-roundtrip.json',reply);assert reply['choices'][0]['message'].get('content')
        reply=chat([{'role':'user','content':'Reply exactly READY; do not call any tools.'}],tools=tools,tool_choice='none');atomic_write_json(out/'tool-none.json',reply);assert not reply['choices'][0]['message'].get('tool_calls')
        state['status']='evaluating';save()
        template=json.dumps({'enable_thinking':True,'reasoning_effort':'high'})
        for suite in ['deep_reasoning_suite','work_quality_suite']:
            dest=out/(suite+'.json')
            if a.resume and dest.exists() and valid_result(json.loads(dest.read_text())):
                print('RETAIN completed',suite,flush=True);continue
            run([sys.executable,str(ROOT/'evals'/(suite+'.py')),'--url',BASE+'/v1/chat/completions','--model',MODEL,'--key-file',str(KEYFILE),'--extended','--template-kwargs',template,'--min-tokens','32768','--retry','--retry-credit','0.7','--output',str(dest)],suite,28800)
            d=json.loads(dest.read_text());assert valid_result(d),suite+' incomplete/API errors';state['stages'][suite]={'score':d['score'],'max_score':d['max_score']};save()
        fixture_dir=out/'fixtures';fixture_dir.mkdir(exist_ok=bool(a.resume));atomic_write_json(fixture_dir/'manifest.json',{'tasks':tasks()})
        # The retained CLI's 240s network timeout is too short for high-reasoning
        # vision. Override only this endpoint in this child, leaving grading unchanged.
        wrapper="import urllib.request,runpy,sys,pathlib; old=urllib.request.urlopen; url=sys.argv[1]; script=sys.argv[2]; sys.path.insert(0,str(pathlib.Path(script).parent)); urllib.request.urlopen=lambda req,*a,**kw: old(req,*a,**({**kw,'timeout':7200} if getattr(req,'full_url','')==url else kw)); sys.argv=sys.argv[2:]; runpy.run_path(script,run_name='__main__')"
        dest=out/'vision.json';run([sys.executable,'-c',wrapper,BASE+'/v1/chat/completions',str(ROOT/'evals/vision_suite.py'),'--fixtures',str(fixture_dir),'--url',BASE+'/v1/chat/completions','--model',MODEL,'--key-file',str(KEYFILE),'--output',str(dest),'--template-kwargs',template,'--max-tokens','16384'],'vision-all25',28800)
        d=json.loads(dest.read_text());assert valid_result(d,vision=True);state['stages']['vision']={'score':d['score'],'max_score':d['max_score']};save()
        dest=out/'concurrency-high.json';run([sys.executable,str(ROOT/'evals/concurrency_sweep.py'),'--url',BASE+'/v1/chat/completions','--model',MODEL,'--key-file',str(KEYFILE),'--levels','1,2,4','--max-tokens','1024','--template-kwargs',template,'--output',str(dest)],'concurrency-high',3600);assert valid_result(json.loads(dest.read_text()),concurrency=True)
        dest=out/'concurrency-off.json';run([sys.executable,str(ROOT/'evals/concurrency_sweep.py'),'--url',BASE+'/v1/chat/completions','--model',MODEL,'--key-file',str(KEYFILE),'--levels','1,2,4','--max-tokens','400','--template-kwargs','{"enable_thinking":false}','--output',str(dest)],'concurrency-off',3600);assert valid_result(json.loads(dest.read_text()),concurrency=True)
        run(['env','API_URL='+BASE,sys.executable,str(RECIPE/'tools/bench.py'),'local-upstream-script'],'publisher-repo-bench',7200)
        stage('long-context-retrieval')
        for target in [32000,100000,200000,500000,900000]:
            memory();request('/health',timeout=10);needle=uuid.uuid4().hex
            unit='Archived instrument inventory: routine calibration and maintenance records.\n'
            prefix='Archive key: '+needle+'\n';suffix='\nReturn only the archive key at the beginning.'
            count=request('/tokenize',{'prompt':prefix+unit*1000+suffix})['count'];prompt=prefix+unit*int(target*1000/count)+suffix
            actual=request('/tokenize',{'prompt':prompt})['count'];assert actual+512<1048576
            begun=time.monotonic();reply=chat([{'role':'user','content':prompt}],max_tokens=512,reasoning_effort='none');row={'target':target,'tokenized_count':actual,'expected':needle,'elapsed_s':time.monotonic()-begun,'response':reply,'correct':(reply['choices'][0]['message'].get('content') or '').strip()==needle};atomic_write_json(out/('long-'+str(target)+'.json'),row)
            if not row['correct']:raise RuntimeError('retrieval failed at '+str(target))
        atomic_write_json(out/'health-final.json',request('/health',timeout=10));state['status']='complete';save()
        print('COMPLETE',json.dumps(state),flush=True)
    except Exception as exc:
        state['status']='blocked';state['error']=str(exc);save();print('BLOCKED',json.dumps(state),flush=True);raise
if __name__=='__main__':main()
