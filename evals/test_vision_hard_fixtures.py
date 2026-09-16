"""Offline fixture tests: independent oracles, geometry, and manifest contract."""
import hashlib
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

import vision_hard_fixtures as v
from vision_suite import grade


V1 = Path(__file__).parent / 'fixtures' / 'vision-v1'
KNOWN = {
    'hard_v2_reconciliation': {
        'released_good_units': 152, 'released_value_cents': 25285,
        'held_ids': ['E55', 'F66'], 'largest_value_id': 'B22'},
    'hard_v2_crossing_plot': {
        'start_minute': 1, 'end_minute': 2, 'crossing_second': 70,
        'right_gap': 25, 'c_area_unit_seconds': 1950},
    'hard_v2_logic_network': {
        'g1_sources': ['A', 'C'], 'g2_sources': ['B', 'D'],
        'high_input_codes': ['0010', '0101', '0110', '1000', '1100', '1111'],
        'scenario_y': 0, 'fault_y': 1},
    'hard_v2_cube': {
        'option': 'Q', 'opposite_c': 'E', 'final_top': 'F',
        'final_front': 'D', 'final_right': 'C'},
    'hard_v2_resources': {
        'room': 'R2', 'technician': 'Bo', 'start': '10:15', 'end': '11:15'},
    'hard_v2_cross_reference': {
        'node': 'N4', 'probe': 'P7', 'revision': 3,
        'adjusted': 56, 'destination': 'BAY-6'},
}


class ManifestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / 'v2'
        cls.before = {p: hashlib.sha256(p.read_bytes()).hexdigest()
                      for p in V1.iterdir() if p.is_file()}
        cls.tasks = v.build_suite(cls.out, V1)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_tiers_ids_and_baseline_identity(self):
        self.assertEqual(len(self.tasks), 12)
        self.assertEqual(len({t['id'] for t in self.tasks}), 12)
        self.assertEqual([sum(t['difficulty'] == d for t in self.tasks)
                          for d in ('easy', 'medium', 'hard')], [3, 3, 6])
        original = json.loads((V1 / 'manifest.json').read_text())['tasks']
        # Image identity is independent of the checkout's absolute location.
        self.assertEqual(
            [{**t, 'image': Path(t['image']).name} for t in self.tasks[:6]],
            [{**t, 'image': Path(t['image']).name} for t in original[:6]])
        self.assertTrue(set(KNOWN).isdisjoint(t['id'] for t in original))
        self.assertEqual(self.before, {p: hashlib.sha256(p.read_bytes()).hexdigest()
                                      for p in self.before})

    def test_manifests_and_files(self):
        full = json.loads((self.out / 'manifest.json').read_text())
        hard = json.loads((self.out / 'hard-manifest.json').read_text())
        self.assertEqual(full['version'], 'synthetic-vision-v2')
        self.assertEqual(full['tasks'], self.tasks)
        self.assertEqual(hard['tasks'], self.tasks[6:])
        self.assertEqual(hard['version'], 'synthetic-vision-v2-hard')
        self.assertEqual(len(list(self.out.glob('*.png'))), 7)
        for task in self.tasks:
            self.assertEqual(set(task), {'id', 'difficulty', 'image', 'question', 'expected'})
            self.assertTrue(Path(task['image']).is_absolute())
            with Image.open(task['image']) as im:
                self.assertLessEqual(im.width, 1600)
                self.assertLessEqual(im.height, 1400)
                self.assertEqual(im.format, 'PNG')
                self.assertFalse(im.info)  # No answer-bearing PNG metadata.
        with Image.open(self.out / 'contact-sheet.png') as sheet:
            self.assertEqual(sheet.size, (1560, 1380))

    def test_known_answers_and_typed_grading(self):
        for task in self.tasks[6:]:
            self.assertEqual(task['expected'], KNOWN[task['id']])
            expected = task['expected']
            self.assertEqual(grade(json.dumps(expected), expected)['score'], len(expected))
            for key, value in expected.items():
                wrong = dict(expected)
                wrong[key] = str(value) if type(value) is int else None
                self.assertFalse(grade(json.dumps(wrong), expected)['checks'][key])

    def test_prompts_have_only_task_and_schema(self):
        for task in self.tasks[6:]:
            self.assertEqual(task['question'], v.QUESTIONS[task['id']])
            self.assertIn('Return JSON', task['question'])
            self.assertNotIn('expected', task['question'].lower())
        # Guard distinctive answers and numerical inputs against prompt leakage.
        combined = ' '.join(t['question'] for t in self.tasks[6:])
        for value in ('25285', '1950', '10:15', 'BAY-6', '0010', 'E55', 'R2', 'P7'):
            self.assertNotIn(value, combined)

    def test_readable_type_and_deterministic_generation(self):
        with patch.object(v, 'font', wraps=v.font) as fonts:
            again = v.build_suite(self.out, V1)
        self.assertTrue(fonts.call_args_list)
        self.assertTrue(all(c.args[0] >= 18 for c in fonts.call_args_list))
        self.assertEqual(again, self.tasks)
        hashes = {p.name: p.read_bytes() for p in self.out.iterdir()}
        v.build_suite(self.out, V1)
        self.assertEqual(hashes, {p.name: p.read_bytes() for p in self.out.iterdir()})

    def test_missing_baseline_fails_without_regenerating_v1(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                v.build_suite(Path(tmp) / 'v2', Path(tmp) / 'missing-v1')

    def test_v1_cannot_be_output_directory(self):
        with self.assertRaisesRegex(ValueError, 'overwrite v1'):
            v.build_suite(V1, V1)

    def test_generated_artifacts_match_generator(self):
        published = V1.parent / 'vision-v2'
        for filename in ('manifest.json', 'hard-manifest.json'):
            actual = json.loads((published / filename).read_text())
            wanted = json.loads((self.out / filename).read_text())
            for manifest, directory in ((actual, published), (wanted, self.out)):
                for task in manifest['tasks']:
                    image_path = Path(task['image'])
                    self.assertTrue(image_path.is_absolute())
                    # Published manifests retain historical absolute paths.
                    fixture_dir = V1 if task['difficulty'] in ('easy', 'medium') else directory
                    self.assertTrue((fixture_dir / image_path.name).is_file())
                    task['image'] = image_path.name
            self.assertEqual(actual, wanted)
        for generated in self.out.glob('*.png'):
            # Compare decoded pixels, independent of PNG compression versions.
            with Image.open(generated) as a, Image.open(published / generated.name) as b:
                self.assertEqual(a.size, b.size)
                self.assertEqual(a.tobytes(), b.tobytes())


class ReasoningTests(unittest.TestCase):
    def test_revision_order_and_field_semantics(self):
        rows, answer = v.reconcile(v.LEDGER, v.AMENDMENTS)
        by_id = {r['id']: r for r in rows}
        self.assertEqual([(r['qty'], r['rejects']) for r in rows],
                         [(42, 1), (38, 2), (60, 8), (24, 1), (45, 4), (32, 2)])
        # Independent invoice arithmetic after applying the amendments by hand.
        amounts = [41 * 125, 36 * 240, 52 * 80, 23 * 320]
        self.assertEqual(answer['released_value_cents'], sum(amounts))
        self.assertEqual(answer['released_good_units'], 41 + 36 + 52 + 23)
        self.assertEqual(by_id['F66']['state'], 'HOLD')
        self.assertEqual(by_id['E55']['qty'], 45)
        self.assertEqual(v.LEDGER[0]['qty'], 48)  # Oracle must not mutate inputs.
        changed = list(v.AMENDMENTS) + [('A11', 'qty', 'SET', 50), ('A11', 'qty', 'ADD', -2)]
        revised, _ = v.reconcile(v.LEDGER, changed)
        self.assertEqual(revised[0]['qty'], 48)

    def test_plot_conditions_and_exact_interpolation(self):
        candidates, answer = v.analyze_plot(v.SERIES)
        self.assertEqual(candidates, [1, 7])
        self.assertEqual(answer, KNOWN['hard_v2_crossing_plot'])
        # At 70 seconds, A and B both equal 130/3; independent interpolation.
        from fractions import Fraction
        alpha = Fraction(answer['crossing_second'] - 60, 60)
        self.assertEqual(40 + 20 * alpha, 45 - 10 * alpha)
        self.assertEqual(answer['c_area_unit_seconds'], (25 + 40) * 60 // 2)
        upward = [i for i in range(8) if v.SERIES['A'][i] < v.SERIES['B'][i]
                  and v.SERIES['A'][i+1] > v.SERIES['B'][i+1]]
        self.assertEqual(upward, [1, 3, 5, 7])

    def test_geometric_netlist_and_exhaustive_truth_table(self):
        nets = v.circuit_nets(v.WIRES, v.JUNCTIONS)
        self.assertEqual(nets, {
            'G1': ('A', 'C'), 'G2': ('B', 'D'), 'G3': ('G1', 'D'),
            'G4': ('G1', 'G2'), 'G5': ('G3', 'G4')})
        high = []
        for bits in itertools.product((0, 1), repeat=4):
            a, b, c, d = bits
            # Algebraically reduced independent oracle, not gate evaluation.
            expected = (a != c) if not d else (a == c and bool(b))
            got = v.evaluate_circuit(dict(zip('ABCD', bits)), nets)
            self.assertEqual(got, int(expected))
            if got:
                high.append(''.join(map(str, bits)))
        self.assertEqual(high, KNOWN['hard_v2_logic_network']['high_input_codes'])

    def test_junctions_and_nonjunction_crossings_change_topology(self):
        # The C tap must join the vertical trace and C bus.
        with self.assertRaisesRegex(ValueError, 'driver'):
            v.circuit_nets(v.WIRES, [p for p in v.JUNCTIONS if p != (320, 520)])
        # Dot at B-bus/C-trace crossing would short two independent drivers.
        with self.assertRaisesRegex(ValueError, 'driver'):
            v.circuit_nets(v.WIRES, v.JUNCTIONS + [(320, 360)])

    def test_cube_fold_chirality_and_rolls(self):
        normals = v.fold_cube(v.CUBE_NET)
        self.assertEqual(len(set(normals.values())), 6)
        for a, b in [('A', 'F'), ('B', 'D'), ('C', 'E')]:
            self.assertEqual(normals[a], tuple(-x for x in normals[b]))
        valid, answer = v.analyze_cube()
        self.assertEqual(valid, ['Q'])
        self.assertEqual(answer, KNOWN['hard_v2_cube'])
        # Independently move face names across physical positions, three rolls.
        state = dict(top='A', bottom='F', front='C', back='E', right='D', left='B')
        permutations = [dict(top='left', right='top', bottom='right', left='bottom'),
                        dict(top='front', back='top', bottom='back', front='bottom'),
                        dict(top='left', right='top', bottom='right', left='bottom')]
        for perm in permutations:
            state = {k: state[perm.get(k, k)] for k in state}
        self.assertEqual([state[k] for k in ('top', 'front', 'right')], ['F', 'D', 'C'])

    def test_schedule_unique_global_optimum_and_endpoint_semantics(self):
        plans = v.schedule_plans(v.BUSY)
        # Independent discrete occupancy oracle at one-minute resolution.
        blocked = {r: {m for a, b in spans for m in range(a, b)}
                   for r, spans in v.BUSY.items()}
        oracle = []
        for s, room, tech in itertools.product(range(0, 181, 15), ('R1', 'R2'), ('Ada', 'Bo')):
            if room == 'R1' and tech != 'Ada':
                continue
            if (not blocked[room].intersection(range(s, s+60))
                and not blocked[tech].intersection(list(range(s, s+15)) + list(range(s+45, s+60)))
                and not blocked['Scanner'].intersection(range(s+15, s+45))):
                oracle.append((s, room, tech))
        self.assertEqual(plans, oracle)
        best = min(p[0] for p in plans)
        self.assertEqual([p for p in plans if p[0] == best], [(75, 'R2', 'Bo')])
        self.assertFalse(v.overlap((0, 15), (15, 30)))
        self.assertTrue(v.overlap((0, 16), (15, 30)))

    def test_cross_reference_exact_keys_and_distractors(self):
        trace, answer = v.cross_reference()
        self.assertEqual(trace, ['IN', 'H1', 'N4'])
        self.assertEqual(answer, KNOWN['hard_v2_cross_reference'])
        matches = [r for r in v.REGISTRY if r[:3] == ('K2', 'L8', 'LIVE')]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0][3:], ('P7', 3, 'S2'))
        self.assertEqual((17 - 3) * 4, answer['adjusted'])
        self.assertGreater(len([r for r in v.REGISTRY if r[0] == 'K2']), 2)
        self.assertGreater(len([r for r in v.CALIBRATION if r[0] == 'P7']), 2)


if __name__ == '__main__':
    unittest.main()
