"""Continue unstarted TensorFold context checks; preserve strict-format failures."""
import datetime,json,pathlib,re,sys,time,urllib.request,uuid,fcntl
ROOT=pathlib.Path('/home/david/work/llmctl');sys.path.insert(0,str(ROOT/'evals'))
from eval_runtime import atomic_write_json
from run_tensorfold_trial import command
OUT=ROOT/'evals/results/dw-spark0/glm53-tensorfold-high-20261001T115956Z'
BASE='http://127.0.0.1:18888'
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
    lock=open('/home/david/.config/llmctl/experiment-sequence.lock','w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
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
        original=json.loads((OUT/'status.json').read_text());atomic_write_json(OUT/'status-before-context-extension.json',original);original.update(status='complete_with_format_failure',step='finished',context_extension=status);original.pop('error',None);atomic_write_json(OUT/'status.json',original)
    except Exception as exc:
        status.update(status='blocked',error=str(exc));atomic_write_json(OUT/'context-extension-status.json',status);raise
if __name__=='__main__':main()
