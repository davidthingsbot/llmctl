"""Bounded real post-update verification; raw receipts retained, credentials excluded."""
import base64, concurrent.futures, io, json, pathlib, time, urllib.request
from PIL import Image
OUT=pathlib.Path('/home/david/work/llmctl/evals/results/dw-spark0/glm53-tensorfold-v13-update')
OUT.mkdir(parents=True,exist_ok=True)
BASE='http://127.0.0.1:8005'
KEY=next(k.strip() for k in pathlib.Path('/home/david/.config/vllm/api-keys').read_text().splitlines() if k.strip())
MODEL='GLM-5.3-Flash-EXL3'
def call(path,payload=None):
    req=urllib.request.Request(BASE+path,data=json.dumps(payload).encode() if payload is not None else None,headers={'Authorization':'Bearer '+KEY,'Content-Type':'application/json'})
    with urllib.request.urlopen(req,timeout=300) as response:return json.load(response)
def save(name,result):
    (OUT/(name+'.json')).write_text(json.dumps(result,indent=2)+'\n')
for attempt in range(120):
    try:
        health=call('/health')
        if health.get('ok'):break
    except Exception:pass
    time.sleep(5)
else:raise RuntimeError('Updated frontend did not become ready within 10 minutes')
save('health-start',health)
if health['context_length']!=1048576:raise RuntimeError('Context changed')
listing=call('/v1/models');save('models',listing)
if listing['data'][0]['id']!=MODEL:raise RuntimeError('Model changed')
def chat(messages,**kwargs):
    return call('/v1/chat/completions',dict(model=MODEL,messages=messages,temperature=0,max_tokens=1024,**kwargs))
text=chat([{'role':'user','content':'Reply with exactly READY.'}]);save('thinking-text',text)
if (text['choices'][0]['message'].get('content') or '').strip()!='READY':raise RuntimeError('Text smoke failed')
print('PASS default-thinking real text',flush=True)
tools=[{'type':'function','function':{'name':'add_tags','description':'Attach tags to a document.','parameters':{'type':'object','properties':{'doc_id':{'type':'integer'},'tags':{'type':'array','items':{'type':'string'}}},'required':['doc_id','tags']}}}]
messages=[{'role':'user','content':'Use add_tags to tag document 42 with urgent, finance and q3.'}]
r=chat(messages,tools=tools);save('tool-array',r);m=r['choices'][0]['message'];calls=m.get('tool_calls') or []
if len(calls)!=1:raise RuntimeError('Expected one typed tool call')
a=json.loads(calls[0]['function']['arguments'])
if a.get('doc_id')!=42 or set(a.get('tags',[]))!={'urgent','finance','q3'}:raise RuntimeError('Typed tool arguments failed')
messages += [m,{'role':'tool','tool_call_id':calls[0]['id'],'content':'Tags applied successfully.'}]
r=chat(messages,tools=tools);save('tool-roundtrip',r)
if not r['choices'][0]['message'].get('content'):raise RuntimeError('No final tool-roundtrip answer')
print('PASS typed tool call and roundtrip',flush=True)
history=[{'role':'user','content':'Earlier task.'},{'role':'assistant','content':None,'tool_calls':[{'id':'bad-history-call','type':'function','function':{'name':'add_tags','arguments':'[1,2]'}}]},{'role':'tool','tool_call_id':'bad-history-call','content':'bad call result'},{'role':'user','content':'Ignore the earlier task. Reply with exactly OK.'}]
r=chat(history,tools=tools,chat_template_kwargs={'enable_thinking':False});save('malformed-history',r)
if (r['choices'][0]['message'].get('content') or '').strip()!='OK':raise RuntimeError('Malformed-history recovery failed')
print('PASS malformed-history recovery',flush=True)
buf=io.BytesIO();Image.new('RGB',(64,64),'red').save(buf,format='PNG');uri='data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()
parts=[{'type':'text','text':'These five images each show the same solid color. What color? Reply with one word.'}]+[{'type':'image_url','image_url':{'url':uri}} for _ in range(5)]
r=chat([{'role':'user','content':parts}],chat_template_kwargs={'enable_thinking':False});save('five-image-vision',r)
if 'red' not in (r['choices'][0]['message'].get('content') or '').lower():raise RuntimeError('Five-image smoke failed')
print('PASS five-image real vision (not a full vision evaluation)',flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
    results=list(ex.map(lambda _:chat([{'role':'user','content':'Reply with exactly OK.'}],chat_template_kwargs={'enable_thinking':False}),range(4)))
save('four-concurrent',results)
if any((r['choices'][0]['message'].get('content') or '').strip()!='OK' for r in results):raise RuntimeError('Four-request smoke failed')
print('PASS four simultaneous short requests',flush=True)
# Check SSE and truncated tool boundary without creating or executing any real tool.
payload=dict(model=MODEL,messages=[{'role':'user','content':'Use add_tags to attach 100 different tags to document 42. Do not answer in prose.'}],tools=tools,temperature=0,max_tokens=12,stream=True,chat_template_kwargs={'enable_thinking':False})
req=urllib.request.Request(BASE+'/v1/chat/completions',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+KEY,'Content-Type':'application/json'})
events=[]
with urllib.request.urlopen(req,timeout=120) as response:
    for line in response:
        line=line.decode().strip()
        if line=='data: [DONE]':break
        if line.startswith('data: '):events.append(json.loads(line[6:]))
save('truncated-tool-stream',events)
finished=[]
for e in events:
    for choice in e.get('choices',[]):
        if choice.get('finish_reason'):finished.append(choice['finish_reason'])
        for tool in choice.get('delta',{}).get('tool_calls',[]):
            args=tool.get('function',{}).get('arguments')
            if args and not isinstance(json.loads(args),dict):raise RuntimeError('Partial/non-object streamed tool args')
if not finished:raise RuntimeError('SSE lacked finish reason')
print('PASS streamed token-limit tool boundary; finish='+str(finished),flush=True)
save('health-final',call('/health'));save('verification',{'status':'complete','checks':['default-thinking-text','typed-tool-array','tool-roundtrip','malformed-history','five-image-vision','four-short-concurrent','token-limit-tool-stream'],'scope':'post-update functional smoke, not repeated quality/performance/full-context evaluation'})
print('COMPLETE',OUT,flush=True)
