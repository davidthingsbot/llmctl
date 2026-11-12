"""Create onset-aligned four-second audition edits; retain unedited sources."""
import json
import pathlib
import subprocess
import sys
import zipfile
import numpy as np


def run(args):
    return subprocess.run(args, check=True, capture_output=True)


def main(root):
    manifest = json.loads((root / 'manifest.json').read_text())
    assert len(manifest) == 8 and all(item['success'] for item in manifest)
    edits = root / 'edits'
    edits.mkdir(exist_ok=False)
    blocks = []
    records = []
    for item in manifest:
        source = pathlib.Path(item['audios'][0]['path'])
        probe = json.loads(run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', str(source)]).stdout)
        duration = float(probe['format']['duration'])
        assert 9.9 <= duration <= 10.2, duration
        decoded = run(['ffmpeg', '-v', 'error', '-i', str(source), '-f', 'f32le', '-ac', '2', '-ar', '48000', '-']).stdout
        audio = np.frombuffer(decoded, dtype='<f4').reshape(-1, 2).copy()
        assert np.isfinite(audio).all() and np.max(np.abs(audio)) > 0.001
        window = 480
        mono_power = np.mean(audio ** 2, axis=1)
        envelope = np.sqrt(mono_power[:len(audio)//window*window].reshape(-1, window).mean(axis=1))
        threshold = max(float(envelope.max()) * 0.08, 0.0001)
        onset = int(np.flatnonzero(envelope > threshold)[0]) * window
        start = max(0, onset - 960)
        clip = audio[start:start + 192000].copy()
        assert len(clip) == 192000
        clip[:240] *= np.linspace(0, 1, 240)[:, None]
        clip[-19200:] *= np.linspace(1, 0, 19200)[:, None]
        peak = float(np.max(np.abs(clip)))
        clip *= min(0.85 / peak, 4.0)
        wav = edits / (item['name'] + '.wav')
        mp3 = wav.with_suffix('.mp3')
        raw = clip.astype('<f4').tobytes()
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'f32le', '-ar', '48000', '-ac', '2', '-i', '-', '-c:a', 'pcm_s16le', str(wav)], input=raw, check=True)
        run(['ffmpeg', '-v', 'error', '-i', str(wav), '-c:a', 'libmp3lame', '-b:a', '192k', str(mp3)])
        run(['ffmpeg', '-v', 'error', '-i', str(mp3), '-f', 'null', '-'])
        blocks.extend([clip, np.zeros((36000, 2), dtype=np.float32)])
        records.append({'name': item['name'], 'source': str(source), 'source_duration': duration, 'edit_start_s': start / 48000, 'edit_duration_s': 4, 'source_peak': float(np.max(np.abs(audio))), 'source_rms': float(np.sqrt(np.mean(audio ** 2)))})
    montage = root / 'Chapter-Bumpers-8-Takes.mp3'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'f32le', '-ar', '48000', '-ac', '2', '-i', '-', '-c:a', 'libmp3lame', '-b:a', '192k', str(montage)], input=np.concatenate(blocks).astype('<f4').tobytes(), check=True)
    run(['ffmpeg', '-v', 'error', '-i', str(montage), '-f', 'null', '-'])
    (root / 'edit-receipts.json').write_text(json.dumps(records, indent=2))
    (root / 'README.txt').write_text('Order: dark post-punk takes 1/2; soft piano-bell takes 1/2; dramatic impact takes 1/2; gothic bass-guitar takes 1/2.\nPreview: each excerpt is 4 seconds, with 0.75 seconds silence between clips.\nEdits are automatically onset-aligned, peak-adjusted and faded, not selected by listening. Four-second endings are editorial fades, not proof of model-generated resolution.\nOriginal 10-second FLACs and generation prompts retained.\n')
    archive = root / 'Chapter-Bumpers-Sources-and-Edits.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for path in sorted(root.rglob('*')):
            if path.is_file() and path != archive:
                z.write(path, path.relative_to(root))
    print(json.dumps({'preview': str(montage), 'archive': str(archive), 'verified_clips': len(records), 'records': records}, indent=2))


if __name__ == '__main__':
    main(pathlib.Path(sys.argv[1]))
