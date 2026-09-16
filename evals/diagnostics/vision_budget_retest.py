import json,pathlib,sys,time,base64,urllib.request
root=pathlib.Path('/home/david/work/llmctl');sys.path.insert(0,str(root/'evals'))
from vision_suite import grade
from eval_runtime import atomic_write_json
key=pathlib.Path('/home/david/.config/vllm/api-keys').read_text().strip()
tasks=json.loads((root/'evals/fixtures/vision-v2/hard-manifest.json').read_text())['tasks']
selected=[t for t in tasks if t['id'] in ('hard_v2_logic_network','hard_v2_cube')]
output=root/'evals/results/dw-spark0/vision-hard6-glm53-nvfp4-budget4096.json'
report={'model':'glm53-flash-nvfp4-vision','max_tokens':4096,'reasoning_effort':'low','status':'partial','tasks':[]}
for t in selected:
    payload={'model':report['model'],'temperature':0,'max_tokens':4096,'chat_template_kwargs':{'reasoning_effort':'low'},'messages':[{'role':'user','content':[{'type':'text','text':t['question']+' Return only the JSON object, no explanation.'},{'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(pathlib.Path(t['image']).read_bytes()).decode()}}]}]}
    req=urllib.request.Request('http://127.0.0.1:8006/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
    start=time.monotonic()
    with urllib.request.urlopen(req,timeout=600) as response: raw=json.load(response)
    row={'id':t['id'],'expected':t['expected'],'raw_response':raw,'elapsed_s':time.monotonic()-start,**grade(raw['choices'][0]['message'].get('content') or '',t['expected'])}
    report['tasks'].append(row);atomic_write_json(output,report)
    print(json.dumps(row),flush=True)
report['status']='complete';atomic_write_json(output,report)
