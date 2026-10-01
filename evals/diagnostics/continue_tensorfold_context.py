"""Continue unstarted TensorFold context checks; preserve strict-format failures."""
import datetime,json,pathlib,re,sys,time,urllib.request,uuid,fcntl
ROOT=pathlib.Path('/home/david/work/llmctl');sys.path.insert(0,str(ROOT/'evals'))
from eval_runtime import atomic_write_json
from run_tensorfold_trial import command,snapshot_attempt,valid_result
OUT=ROOT/'evals/results/dw-spark0/glm53-tensorfold-high-20261001T115956Z'
BASE='http://127.0.0.1:18888'

def validate_predecessor():
    """Only extend the retained 100K format-only failure, never other failures."""
    existing=['context-extension-status.json','status-before-context-extension.json']+['long-'+str(n)+'.json' for n in [200000,500000,900000]]
    if any((OUT/name).exists() for name in existing):
        raise RuntimeError('context extension artifacts already exist; refusing to overwrite predecessor or checks')
    def read(name):return json.loads((OUT/name).read_text())
    def require(condition,message):
        if not condition:raise RuntimeError(message)
    original=read('status.json')
    require(original.get('status')=='blocked' and original.get('step')=='long-context-retrieval' and original.get('error')=='retrieval failed at 100000',
            'predecessor must be blocked only on the retained 100K format mismatch')
    for name,vision in [('deep_reasoning_suite',False),('work_quality_suite',False),('vision',True)]:
        d=read(name+'.json')
        require(valid_result(d,vision=vision) and d.get('status')=='complete' and not d.get('error') and not d.get('retry_error')
                and all(t.get('status')=='complete' for t in d['tasks']),name+' must be complete without API errors')
        if 'planned_tasks' in d:
            require(len(d['tasks'])==len(d['planned_tasks']) and {t.get('task') for t in d['tasks']}==set(d['planned_tasks']),name+' has missing planned tasks')
    for name in ['concurrency-high','concurrency-off']:
        d=read(name+'.json');rows=d.get('results',[])
        require(d.get('levels')==[1,2,4] and len(rows)==3 and {r.get('streams') for r in rows}=={1,2,4}
                and all(r.get('failed')==0 and not r.get('error') for r in rows)
                and not d.get('error') and d.get('status','complete')=='complete',name+' requires successful 1/2/4 receipts')
    # The publisher CLI emits four prefill rows followed by two decode rows.
    # A present but truncated/error log is not a completed benchmark receipt.
    lines=(OUT/'publisher-repo-bench.log').read_text().strip().splitlines()
    require(len(lines)==7 and lines[0]=='== local-upstream-script'
            and all(re.fullmatch(r'prefill\s+[\d,]+ tok:\s+[\d.]+ s\s+[\d.]+ tok/s\s+TTFT\s+[\d.]+ s\s+\(.+\)',line) for line in lines[1:5])
            and re.fullmatch(r'decode code greedy\s*:\s*[\d.]+ tok/s \(median of 5\)',lines[5])
            and re.fullmatch(r'decode chat sampled\s*:\s*[\d.]+ tok/s \(median of 5\)',lines[6]),
            'publisher benchmark log is missing completed prefill/decode results')
    for target in [32000,100000]:
        row=read('long-'+str(target)+'.json');expected=row.get('expected','')
        require(row.get('target')==target and re.fullmatch(r'[0-9a-f]{32}',expected) is not None and not row.get('error'), 'invalid retained context receipt')
        choices=row.get('response',{}).get('choices',[])
        require(len(choices)==1,'retained context response must have exactly one choice')
        text=(choices[0]['message'].get('content') or '').strip()
        keys=re.findall(r'(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])',text)
        require(keys==[expected],'retained context response must return the unique expected key')
        require((row.get('correct') is True and text==expected) if target==32000 else (row.get('correct') is False and text!=expected),
                '32K must pass and 100K must fail only strict formatting')
    return original

def post(path,payload=None):
    req=urllib.request.Request(BASE+path,data=json.dumps(payload).encode() if payload else None,headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=7200) as r:return json.load(r)
def memory():
    h=int(next(l.split()[1] for l in pathlib.Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:')))/1048576
    r=command(['ssh','-o','BatchMode=yes','-o','ConnectTimeout=5','david@10.100.100.11','free -b'],15)
    w=int(next(l.split()[-1] for l in r.stdout.splitlines() if l.startswith('Mem:')))/2**30
    for args in [['systemctl','--user','is-active','glm53-tf-trial-memguard.service'],['ssh','-o','BatchMode=yes','david@10.100.100.11','systemctl --user is-active glm53-tf-trial-memguard.service']]:command(args)
    if min(h,w)<8:raise RuntimeError('pre-request available memory below 8 GiB')
    return {'head_available_gib':h,'worker_available_gib':w}
def main():
    with open('/home/david/.config/llmctl/experiment-sequence.lock','a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        original=validate_predecessor()
        snapshot_attempt(OUT)
        atomic_write_json(OUT/'status-before-context-extension.json',original)
        extend_context(original)

def extend_context(original):
    status={'status':'running','step':'long-context-extension','results':[],'note':'Original 100K answer retrieved the correct key but violated exact-only formatting. Original strict result remains unchanged.'};atomic_write_json(OUT/'context-extension-status.json',status)
    try:
        for target in [200000,500000,900000]:
            print('START',target,flush=True);mem=memory();assert post('/health')['ok'];needle=uuid.uuid4().hex
            unit='Archived instrument inventory: routine calibration and maintenance records.\n';prefix='Archive key: '+needle+'\n';suffix='\nReturn only the archive key at the beginning.'
            count=post('/tokenize',{'prompt':prefix+unit*1000+suffix})['count'];prompt=prefix+unit*int(target*1000/count)+suffix;actual=post('/tokenize',{'prompt':prompt})['count'];assert actual+512<1048576
            started=time.monotonic();reply=post('/v1/chat/completions',{'model':'GLM-5.3-Flash-EXL3','messages':[{'role':'user','content':prompt}],'temperature':0,'max_tokens':512,'reasoning_effort':'none'})
            text=(reply['choices'][0]['message'].get('content') or '').strip();keys=re.findall(r'(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])',text)
            row={'target':target,'tokenized_count':actual,'expected':needle,'elapsed_s':time.monotonic()-started,'response':reply,'correct':text==needle,'retrieval_correct':keys==[needle],'memory_before':mem};atomic_write_json(OUT/('long-'+str(target)+'.json'),row)
            status['results'].append({k:row[k] for k in ['target','tokenized_count','elapsed_s','correct','retrieval_correct']});atomic_write_json(OUT/'context-extension-status.json',status)
            print('RESULT',json.dumps(status['results'][-1]),flush=True)
            if not row['retrieval_correct']:raise RuntimeError('key retrieval failed at '+str(target))
        status['status']='complete';atomic_write_json(OUT/'health-final.json',post('/health'));atomic_write_json(OUT/'context-extension-status.json',status)
        original.update(status='complete_with_format_failure',step='finished',context_extension=status);original.pop('error',None);atomic_write_json(OUT/'status.json',original)
    except Exception as exc:
        status.update(status='blocked',error=str(exc));atomic_write_json(OUT/'context-extension-status.json',status);raise
if __name__=='__main__':main()
