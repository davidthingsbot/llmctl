"""Two native ACE-Step takes of a soft gong and water-bubble transition."""
import time
import generate_bumpers as batch

if __name__ == '__main__':
    batch.SPECS = [('gong-bubbles-ai', 'A sparse peaceful audio transition, isolated sound-design sting. One softly struck small bronze gong, warm and rounded, with a gentle shimmering decay. As the gong fades, a few distinct water bubbles rise and pop softly underneath it. Close delicate hollow bubbling, not running water or ocean waves. Gong begins immediately, bubbles follow, then everything decays into silence. No melody, no drums, no vocals, no continuous accompaniment, no repeating rhythmic loop. One brief event.')]
    batch.OUT = batch.demo.ROOT / 'output' / ('gong-bubbles-' + time.strftime('%Y%m%dT%H%M%S'))
    batch.demo.OUT = batch.OUT
    batch.demo.generate_music = batch.generate_all
    batch.demo.main()
    print('GONG_OUTPUT', batch.OUT, flush=True)
