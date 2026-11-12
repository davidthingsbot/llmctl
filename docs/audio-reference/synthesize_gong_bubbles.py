"""Render reproducible modal gong and damped chirp bubble stems, no samples or AI."""
import json
import pathlib
import subprocess
import sys
import numpy as np

SR = 48000
DURATION = 6


def save(path, audio):
    """Write stereo PCM WAV and MP3 from finite unclipped floating point audio."""
    assert audio.shape == (SR * DURATION, 2)
    assert np.isfinite(audio).all() and np.max(np.abs(audio)) < 1
    subprocess.run(['ffmpeg', '-v', 'error', '-f', 'f32le', '-ar', str(SR), '-ac', '2', '-i', '-', '-c:a', 'pcm_s24le', str(path)], input=audio.astype('<f4').tobytes(), check=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-c:a', 'libmp3lame', '-b:a', '192k', str(path.with_suffix('.mp3'))], check=True)


def main(root):
    """Mix quiet bubbles after a soft gong and retain independently editable layers."""
    root.mkdir(parents=True, exist_ok=False)
    rng = np.random.default_rng(48101)
    t = np.arange(SR * DURATION) / SR
    mono = np.zeros_like(t)
    # Inharmonic resonances, gentle attack, slower low modes, slight beating.
    ratios = [1, 1.47, 2.09, 2.56, 3.71, 4.23, 5.41, 6.8]
    amps = [1, .48, .32, .18, .12, .085, .055, .025]
    for ratio, amp in zip(ratios, amps):
        freq = 148 * ratio
        phase = 2 * np.pi * (freq * t + .45 * np.sin(2 * np.pi * .7 * t))
        env = (1 - np.exp(-t / .014)) * np.exp(-t / (1.7 / ratio ** .38))
        mono += amp * env * (np.sin(phase) + .13 * np.sin(phase + 2 * np.pi * .8 * t))
    excitation = rng.normal(size=len(t))
    excitation = np.convolve(excitation, np.ones(25) / 25, mode='same')
    mono += .06 * excitation * np.exp(-t / .035) * (1 - np.exp(-t / .003))
    gong = np.column_stack([mono, mono])
    for delay, gain in [(0.071, .12), (.137, .07), (.223, .035)]:
        n = int(delay * SR)
        gong[n:, 0] += gain * mono[:-n]
        gong[n + 233:, 1] += gain * mono[:-n - 233]
    gong *= .42 / np.max(np.abs(gong))
    bubbles = np.zeros_like(gong)
    events = []
    for onset, freq, level, pan in [(.65, 460, .16, -.3), (.94, 690, .11, .25), (1.32, 540, .13, -.15), (1.76, 930, .08, .35), (2.03, 650, .1, -.2), (2.57, 1080, .055, .15), (3.02, 790, .05, 0)]:
        u = np.arange(int(.4 * SR)) / SR
        # Rapidly damped, upward bending resonances approximate bubble plops.
        phase = 2 * np.pi * freq * (u + .32 * (u - .018 * (1 - np.exp(-u / .018))))
        env = (1 - np.exp(-u / .0009)) * np.exp(-u / .038)
        plop = level * env * (np.sin(phase) + .12 * np.sin(phase * 2.03))
        start = int(onset * SR)
        bubbles[start:start + len(u), 0] += plop * np.sqrt((1 - pan) / 2)
        bubbles[start:start + len(u), 1] += plop * np.sqrt((1 + pan) / 2)
        events.append({'onset_s': onset, 'frequency_hz': freq, 'level': level, 'pan': pan})
    fade = np.ones(len(t))
    fade[-SR:] = np.linspace(1, 0, SR)
    gong *= fade[:, None]
    bubbles *= fade[:, None]
    mixed = gong + bubbles
    for name, audio in [('B-Layered-Gong-and-Bubbles', mixed), ('Stem-Gong', gong), ('Stem-Bubbles', bubbles)]:
        save(root / (name + '.wav'), audio)
    receipt = {'method': 'procedural synthesis, not AI-generated or recorded sounds', 'duration_s': DURATION, 'sample_rate': SR, 'gong_start_s': 0, 'bubble_events': events, 'mix_peak': float(np.max(np.abs(mixed))), 'mix_rms': float(np.sqrt(np.mean(mixed ** 2)))}
    (root / 'synthesis-receipt.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main(pathlib.Path(sys.argv[1]))
