"""Generate an original vocal post-punk demo with standalone ACE-Step; retain memory receipts."""
import dataclasses
import json
import os
import pathlib
import resource
import threading
import time

os.environ['HF_HUB_OFFLINE']='1'
os.environ['TOKENIZERS_PARALLELISM']='false'
os.environ['ACESTEP_PROJECT_ROOT']=str(pathlib.Path(__file__).resolve().parent)

import torch
from acestep.handler import AceStepHandler
from acestep.llm_inference import LLMHandler
from acestep.inference import GenerationParams,GenerationConfig,generate_music
from acestep import model_downloader

# Upstream preflight otherwise requires unused default 2B/1.7B checkpoints too.
# Check exactly the four real components selected for this XL/4B run.
model_downloader.MAIN_MODEL_COMPONENTS = [
    'vae','Qwen3-Embedding-0.6B','acestep-v15-xl-turbo','acestep-5Hz-lm-4B'
]

ROOT=pathlib.Path(__file__).resolve().parent
OUT=ROOT/'output'/os.environ.get('ACESTEP_RUN_NAME','signal-in-the-stairwell-'+time.strftime('%Y%m%dT%H%M%S'))
LYRICS='''[Verse 1]
Blue light under the door
Your footsteps cross the floor
The lift is broken again
We count the floors like rain

[Chorus]
There is a signal in the stairwell
There is a voice inside the wire
I will not disappear here
I am the spark, I am the fire

[Verse 2]
Black coat against the glass
The last night buses pass
You leave a mark upon the wall
A little proof against it all

[Chorus]
There is a signal in the stairwell
There is a voice inside the wire
I will not disappear here
I am the spark, I am the fire
'''

def available_gib():
    """Return live available unified host memory in GiB."""
    return next(int(l.split()[1])/1048576 for l in pathlib.Path('/proc/meminfo').read_text().splitlines() if l.startswith('MemAvailable:'))

def main():
    """Load the official standalone handlers and save one 60-second vocal song."""
    OUT.mkdir(parents=True,exist_ok=False)
    assert torch.cuda.is_available(),'CUDA required'
    assert available_gib()>40,'Not enough unified memory; lend the GPU through llmctl first'
    stop=threading.Event()
    baseline=available_gib()
    samples=[]
    def monitor():
        while not stop.wait(0.5):
            free=available_gib();samples.append({'elapsed_s':time.monotonic()-started,'available_gib':free})
            if free<8:
                (OUT/'memory-safety-abort.json').write_text(json.dumps(samples[-1]))
                os._exit(90)
    started=time.monotonic()
    threading.Thread(target=monitor,daemon=True).start()
    torch.cuda.reset_peak_memory_stats()
    try:
        dit=AceStepHandler()
        print('INITIALIZING XL Turbo',flush=True)
        status,ok=dit.initialize_service(project_root=str(ROOT),config_path='acestep-v15-xl-turbo',device='cuda',compile_model=False,offload_to_cpu=False,use_flash_attention=False)
        print(status,flush=True)
        assert ok,status
        lm=LLMHandler()
        print('INITIALIZING 4B planning model',flush=True)
        status,ok=lm.initialize(checkpoint_dir=str(ROOT/'checkpoints'),lm_model_path='acestep-5Hz-lm-4B',backend='pt',device='cuda',offload_to_cpu=False,dtype=torch.bfloat16)
        print(status,flush=True)
        assert ok,status
        params=GenerationParams(caption='Dark British post-punk, gothic dance rock, expressive low female lead singing clear English lyrics immediately, melodic driving bass guitar upfront, angular chorus-soaked guitars, dry tom-tom groove with syncopated snare accents, ominous spacious verses, explosive sung chorus, varied percussion and bass fills, raw intimate live-band energy.',lyrics=LYRICS,instrumental=False,vocal_language='en',bpm=120,keyscale='D minor',timesignature='4',duration=60,inference_steps=8,guidance_scale=1.0,shift=3.0,seed=48101,thinking=True,use_cot_metas=False,use_cot_caption=False,use_cot_language=False,dcw_enabled=False)
        config=GenerationConfig(batch_size=1,use_random_seed=False,seeds=[48101],audio_format='flac')
        (OUT/'request.json').write_text(json.dumps({'params':dataclasses.asdict(params),'config':dataclasses.asdict(config)},indent=2))
        print('GENERATING',flush=True)
        t=time.monotonic();result=generate_music(dit,lm,params,config,save_dir=str(OUT))
        receipt={'success':result.success,'error':result.error,'status_message':result.status_message,'audios':result.audios,'generation_s':time.monotonic()-t,'total_s':time.monotonic()-started}
        (OUT/'result.json').write_text(json.dumps(receipt,indent=2,default=str))
        assert result.success,result.error
        for audio in result.audios:
            p=pathlib.Path(audio['path']);assert p.is_file() and p.stat().st_size>0
            print('AUDIO',p,flush=True)
    finally:
        stop.set()
        minimum=min([baseline]+[s['available_gib'] for s in samples])
        receipt={'baseline_available_gib':baseline,'minimum_available_gib':minimum,'observed_system_available_drop_gib':baseline-minimum,'process_peak_rss_gib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1048576,'torch_peak_allocated_gib':torch.cuda.max_memory_allocated()/2**30,'torch_peak_reserved_gib':torch.cuda.max_memory_reserved()/2**30,'total_s':time.monotonic()-started,'note':'Unified memory: do not add RSS to CUDA allocations; they can overlap. System available drop also includes unrelated host changes.'}
        (OUT/'memory.json').write_text(json.dumps(receipt,indent=2))
        (OUT/'memory-samples.json').write_text(json.dumps(samples))
        print('MEMORY',json.dumps(receipt),flush=True)

if __name__=='__main__':
    main()
