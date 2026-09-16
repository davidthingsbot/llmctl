"""Generated image fixtures; real API responses saved verbatim."""
import base64
import json
import pathlib
import time
import urllib.request
import urllib.error
from PIL import Image, ImageDraw, ImageFont

root = pathlib.Path(__file__).resolve().parent
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 40)
key = pathlib.Path('/home/david/.config/vllm/api-keys').read_text().strip()
results = []
for name, color, label in [('a', 'blue', 'K7M4'), ('b', 'red', 'P9R2')]:
    image = Image.new('RGB', (640, 400), 'white')
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 40, 260, 220), fill=color)
    draw.text((40, 280), label, font=font, fill='black')
    path = root / (name + '.png')
    image.save(path)
    payload = {'model':'glm53-flash-nvfp4-vision', 'messages':[{'role':'user','content':[{'type':'text','text':'What color is the large rectangle, and what exact code is printed below it? Reply with only a JSON object with keys color and code.'}, {'type':'image_url','image_url':{'url':'data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode()}}]}], 'max_tokens':256, 'temperature':0, 'chat_template_kwargs':{'reasoning_effort':'low'}}
    req = urllib.request.Request('http://127.0.0.1:8006/v1/chat/completions', data=json.dumps(payload).encode(), headers={'Content-Type':'application/json','Authorization':'Bearer '+key})
    started=time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=180) as response:
            result=json.load(response)
        row={'fixture':name,'expected':{'color':color,'code':label},'seconds':time.monotonic()-started,'response':result}
    except urllib.error.HTTPError as exc:
        row={'fixture':name,'http_error':exc.code,'body':exc.read().decode()}
    results.append(row)
    (root/'results.json').write_text(json.dumps(results,indent=2))
    print(json.dumps(row),flush=True)
    if 'http_error' in row:
        raise SystemExit(1)
