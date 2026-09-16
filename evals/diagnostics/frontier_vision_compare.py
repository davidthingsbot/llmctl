"""Blind Codex image-only comparison. No source/answer files in model workdir."""
import concurrent.futures
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
ROOT=pathlib.Path('/home/david/work/llmctl')
sys.path.insert(0,str(ROOT/'evals'))
from vision_suite import grade
from eval_runtime import atomic_write_json
manifest=pathlib.Path(sys.argv[1])
output=pathlib.Path(sys.argv[2])
tasks=json.loads(manifest.read_text())['tasks']
artifacts=output.with_suffix(''); artifacts.mkdir(parents=True,exist_ok=True)

def evaluate(task):
    row={'id':task['id'],'expected':task['expected'],'question':task['question']}
    started=time.monotonic()
    with tempfile.TemporaryDirectory(prefix='blind-vision-') as directory:
        path=pathlib.Path(directory); image=path/'input.png'; shutil.copyfile(task['image'],image)
        answer=path/'answer.txt'
        prompt='Answer the question using only the attached image. Do not call tools, run commands, access files or the network. Return only the requested JSON object.\n'+task['question']
        command=['codex','exec','--ignore-user-config','--ignore-rules','--ephemeral','--sandbox','read-only','--skip-git-repo-check','--model','gpt-6-astra','-c','model_reasoning_effort="low"','--json','--output-last-message',str(answer),'--image',str(image),'--',prompt]
        try:
            result=subprocess.run(command,cwd=path,capture_output=True,text=True,timeout=360)
            (artifacts/(task['id']+'.jsonl')).write_text(result.stdout)
            (artifacts/(task['id']+'.stderr')).write_text(result.stderr)
            events=[]
            for line in result.stdout.splitlines():
                try: events.append(json.loads(line))
                except ValueError: pass
            tool_events=[e for e in events if e.get('item',{}).get('type') in ('command_execution','mcp_tool_call','web_search','file_change')]
            row.update(exit_code=result.returncode,tool_events=tool_events)
            if result.returncode or not answer.exists() or tool_events:
                row['error']='invalid run: process failure, missing answer, or tool use'
            else:
                text=answer.read_text(); row['response']=text; row.update(grade(text,task['expected']))
        except subprocess.TimeoutExpired:
            row['error']='frontier request timed out'
    row['elapsed_s']=round(time.monotonic()-started,3)
    return row

report={'suite_manifest':str(manifest),'model':'gpt-6-astra','interface':'Codex CLI attached image, tools prohibited','reasoning_effort':'low','temperature':'CLI default; not controlled','status':'partial','tasks':[]}
atomic_write_json(output,report)
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    for row in pool.map(evaluate,tasks):
        report['tasks'].append(row); atomic_write_json(output,report)
        print(json.dumps({k:row.get(k) for k in ('id','score','max_score','error','elapsed_s')}),flush=True)
report['status']='complete'
report['score']=sum(t.get('score',0) for t in report['tasks'])
report['max_score']=sum(len(t['expected']) for t in tasks)
report['invalid_runs']=sum('error' in t for t in report['tasks'])
atomic_write_json(output,report)
print(json.dumps({k:report[k] for k in ('status','score','max_score','invalid_runs')}),flush=True)
