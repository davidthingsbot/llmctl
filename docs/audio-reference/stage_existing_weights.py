"""Stage standalone metadata while reusing existing, untouched Comfy-format weights."""
import concurrent.futures,json,pathlib,struct,urllib.request
ROOT=pathlib.Path('/home/david/work/ace-step-standalone/checkpoints')
COMFY=pathlib.Path('/home/david/ComfyUI/models')
ROOT.mkdir(exist_ok=True)
def fetch(repo,name,dest):
    dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():return
    with urllib.request.urlopen('https://huggingface.co/'+repo+'/resolve/main/'+name,timeout=90) as r:
        data=r.read()
    dest.write_bytes(data)
    print('metadata',dest,flush=True)
def header(path):
    with path.open('rb') as f:
        n=struct.unpack('<Q',f.read(8))[0];d=json.loads(f.read(n));d.pop('__metadata__',None);return d
jobs=[]
for repo,prefix,target in [('ACE-Step/Ace-Step1.5','Qwen3-Embedding-0.6B/','Qwen3-Embedding-0.6B'),('ACE-Step/Ace-Step1.5','vae/','vae'),('ACE-Step/acestep-v15-xl-turbo','','acestep-v15-xl-turbo'),('ACE-Step/acestep-5Hz-lm-4B','','acestep-5Hz-lm-4B')]:
    with urllib.request.urlopen('https://huggingface.co/api/models/'+repo,timeout=30) as r:d=json.load(r)
    for row in d['siblings']:
        name=row['rfilename']
        if not name.startswith(prefix):continue
        rel=name[len(prefix):]
        if '/' in rel or rel.endswith(('.safetensors','.bin')) or rel in ['README.md','.gitattributes','model.safetensors.index.json']:continue
        jobs.append((repo,name,ROOT/target/rel))
with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
    list(pool.map(lambda x:fetch(*x),jobs))
links=[('diffusion_models/acestep_v1.5_xl_turbo_bf16.safetensors','acestep-v15-xl-turbo/model.safetensors'),('text_encoders/qwen_0.6b_ace15.safetensors','Qwen3-Embedding-0.6B/model.safetensors'),('text_encoders/qwen_4b_ace15.safetensors','acestep-5Hz-lm-4B/model.safetensors')]
# ComfyUI's VAE uses a different key namespace. Fetch the native decoder instead.
fetch('ACE-Step/Ace-Step1.5','vae/diffusion_pytorch_model.safetensors',ROOT/'vae/diffusion_pytorch_model.safetensors')
for src,dest in links:
    p=ROOT/dest
    if not p.exists():p.symlink_to(COMFY/src)
    print('reused',p,'tensors',len(header(COMFY/src)),flush=True)
for repo,src in [('ACE-Step/acestep-v15-xl-turbo','diffusion_models/acestep_v1.5_xl_turbo_bf16.safetensors'),('ACE-Step/acestep-5Hz-lm-4B','text_encoders/qwen_4b_ace15.safetensors')]:
    with urllib.request.urlopen('https://huggingface.co/'+repo+'/raw/main/model.safetensors.index.json',timeout=30) as r:idx=json.load(r)
    official=set(idx['weight_map']);local=set(header(COMFY/src))
    print('KEY_CHECK',repo,'missing',sorted(official-local),'extra',sorted(local-official),flush=True)
    assert not (official-local), 'Standalone checkpoint keys missing'
print('STAGED existing weights; no conversion or changes to source files',flush=True)
