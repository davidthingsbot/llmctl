"""Package two generated takes and the layered synthesis as a reproducible comparison."""
import json
import pathlib
import subprocess
import sys
import zipfile
import numpy as np


def decode(path):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-ar', '48000', '-ac', '2', '-f', 'f32le', '-'], check=True, capture_output=True).stdout
    return np.frombuffer(raw, dtype='<f4').reshape(-1, 2)


def main(root):
    manifest = json.loads((root / 'manifest.json').read_text())
    assert len(manifest) == 2 and all(x['success'] for x in manifest)
    synthroot = root.parent / 'gong-bubbles-layered-01'
    mixed = decode(synthroot / 'B-Layered-Gong-and-Bubbles.wav')
    gong = decode(synthroot / 'Stem-Gong.wav')
    bubbles = decode(synthroot / 'Stem-Bubbles.wav')
    assert np.max(np.abs(mixed - gong - bubbles)) < 1e-6
    assert len(mixed) == 288000 and np.isfinite(mixed).all()
    edits = root / 'comparison'
    edits.mkdir(exist_ok=False)
    blocks = []
    receipt = []
    for i, item in enumerate(manifest, 1):
        original = pathlib.Path(item['audios'][0]['path'])
        audio = decode(original)
        assert len(audio) == 480000 and np.max(np.abs(audio)) > .001 and np.isfinite(audio).all()
        target = edits / f'A-ACE-Step-Gong-Bubbles-Take-{i}.mp3'
        subprocess.run(['ffmpeg', '-v', 'error', '-i', str(original), '-t', '6', '-af', 'afade=t=in:d=0.005,afade=t=out:st=5.5:d=0.5', '-c:a', 'libmp3lame', '-b:a', '192k', str(target)], check=True)
        block = decode(target)
        blocks.extend([block, np.zeros((48000, 2), dtype=np.float32)])
        receipt.append({'file': str(target), 'source_s': len(audio) / 48000, 'edit_s': len(block) / 48000, 'rms': float(np.sqrt(np.mean(block ** 2)))})
    blocks.append(mixed)
    preview = edits / 'Gong-and-Bubbles-A1-A2-B-Comparison.mp3'
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'f32le', '-ar', '48000', '-ac', '2', '-i', '-', '-c:a', 'libmp3lame', '-b:a', '192k', str(preview)], input=np.concatenate(blocks).astype('<f4').tobytes(), check=True)
    assert np.max(np.abs(decode(preview))) > .001
    (edits / 'verification.json').write_text(json.dumps({'ai_edits': receipt, 'synthesis_stems_sum_verified': True, 'comparison_order': ['AI take 1', 'AI take 2', 'layered synthesis'], 'note': 'AI excerpts are first six seconds with editorial fades, not listening-selected. Synthesis is modeled sound, not real recordings.'}, indent=2))
    archive = edits / 'Gong-and-Bubbles-Sources-Stems-Prompts.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as z:
        for folder, prefix in [(root, 'ACE-Step'), (synthroot, 'Layered-Synthesis')]:
            for path in sorted(folder.rglob('*')):
                if path.is_file() and path != archive:
                    z.write(path, str(pathlib.Path(prefix) / path.relative_to(folder)))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
    print(json.dumps({'preview': str(preview), 'archive': str(archive), 'verification': receipt}, indent=2))


if __name__ == '__main__':
    main(pathlib.Path(sys.argv[1]))
