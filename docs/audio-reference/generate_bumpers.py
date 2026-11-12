"""Generate eight instrumental chapter-cue experiments with one model load."""
import dataclasses
import json
import time
import generate_demo as demo

SPECS = [
    ('01-dark-postpunk', 'Instrumental chapter-transition sting. One sharp low tom hit introduces a descending three-note electric-bass motif, answered by a metallic chorus-treated guitar chord. Dark restrained post-punk. Immediate attack, brief musical gesture in the first three seconds, then natural reverb decay into silence. One isolated sting, no vocals, no continuous drum groove, no repeating loop.'),
    ('02-soft-piano-bell', 'Instrumental soft chapter divider. Two warm felt-piano notes followed by a soft bell overtone. Intimate, thoughtful, understated. Immediate first note, brief pause between notes, gentle natural decay to silence after the first three seconds. One isolated short musical logo, no vocals, no drums, no continuous accompaniment or repeated melody.'),
    ('03-dramatic-impact', 'Instrumental dramatic reveal transition sting. A very short reverse-cymbal swell into one deep cinematic impact and a dissonant string accent, followed by fading low resonance into silence. Impact within the first second, decay after three seconds. One isolated event, not a rhythmic sequence. No vocals, no sustained drum groove, no full song arrangement.'),
    ('04-gothic-bass-guitar', 'Instrumental gothic post-punk chapter bumper. A tight floor-tom accent, a wiry three-note bass-guitar phrase and a shimmering angular guitar chord. Dark, dry and spacious. Immediate attack, complete short phrase within three seconds, clean decisive ending with reverb tail fading to silence. No singing, no repeating loop, no full song arrangement.'),
]
ORIGINAL = demo.generate_music
OUT = demo.ROOT / 'output' / ('chapter-bumpers-' + time.strftime('%Y%m%dT%H%M%S'))
demo.OUT = OUT


def generate_all(dit, lm, base_params, base_config, save_dir):
    """Retain requests and results for both seeds of every cue style."""
    manifest = []
    last = None
    for index, (name, caption) in enumerate(SPECS):
        for take in range(1, 3):
            seed = 62000 + index * 10 + take
            target = OUT / f'{name}-take-{take}'
            target.mkdir()
            params = dataclasses.replace(base_params, caption=caption, lyrics='[Instrumental]', instrumental=True, vocal_language='unknown', duration=10, seed=seed)
            config = dataclasses.replace(base_config, seeds=[seed])
            (target / 'request.json').write_text(json.dumps({'params': dataclasses.asdict(params), 'config': dataclasses.asdict(config)}, indent=2))
            started = time.monotonic()
            print('CUE_START', target.name, flush=True)
            last = ORIGINAL(dit, lm, params, config, save_dir=str(target))
            receipt = {'name': target.name, 'success': last.success, 'error': last.error, 'audios': last.audios, 'seconds': time.monotonic() - started}
            (target / 'result.json').write_text(json.dumps(receipt, indent=2, default=str))
            manifest.append(receipt)
            (OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2, default=str))
            if not last.success:
                raise RuntimeError(str(receipt))
            print('CUE_DONE', target.name, flush=True)
    return last


if __name__ == '__main__':
    demo.generate_music = generate_all
    demo.main()
    print('BUMPER_OUTPUT', OUT, flush=True)
