"""Independent oracles for the ten extra candidates; no model calls."""
import ast
import hashlib
import itertools
import json
import re
from pathlib import Path
import tempfile
import unittest

from PIL import Image
import vision_extra_fixtures as fixtures
from vision_suite import grade


class ExtraFixturesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).parent / 'fixtures' / 'vision-candidates-extra10'
        root.mkdir(parents=True, exist_ok=True)
        cls.tmp = tempfile.TemporaryDirectory(dir=root)
        cls.directory = Path(cls.tmp.name)
        cls.tasks = fixtures.build_suite(cls.directory)
        cls.answers = [t['expected'] for t in cls.tasks]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_manifest_contract_and_counts(self):
        manifest = json.loads((self.directory / 'manifest.json').read_text())
        self.assertEqual(manifest['tasks'], self.tasks)
        self.assertEqual(len(self.tasks), 10)
        self.assertEqual(len(list(self.directory.glob('*.png'))), 11)
        self.assertEqual(len({t['id'] for t in self.tasks}), 10)
        for i, task in enumerate(self.tasks, 1):
            self.assertTrue(task['id'].startswith(f'extra{i:02}_'))
            self.assertEqual(task['difficulty'], 'hard')
            self.assertTrue(Path(task['image']).is_absolute())
            self.assertEqual(set(task), {'id', 'difficulty', 'image', 'question', 'expected'})
            self.assertIsInstance(task['expected'], dict)

    def test_image_limits_and_text_audit(self):
        for path in self.directory.glob('*.png'):
            with Image.open(path) as im:
                self.assertLessEqual(im.width, 1600)
                self.assertLessEqual(im.height, 1400)
        for audit in fixtures.RENDER_AUDIT:
            self.assertGreaterEqual(audit['font_size'], 18)
            x0, y0, x1, y1 = audit['bbox']
            self.assertGreaterEqual(min(x0, y0), 0)
            self.assertLessEqual(x1, audit['canvas'][0])
            self.assertLessEqual(y1, audit['canvas'][1])
        self.assertGreater(len(fixtures.RENDER_AUDIT), 200)

    def test_exact_typed_grading(self):
        for task in self.tasks:
            expected = task['expected']
            self.assertEqual(grade(json.dumps(expected), expected)['score'], len(expected))
            wrong = {k: None for k in expected}
            self.assertEqual(grade(json.dumps(wrong), expected)['score'], 0)
            for key, value in expected.items():
                if type(value) is int:
                    wrong = dict(expected, **{key: str(value)})
                    self.assertFalse(grade(json.dumps(wrong), expected)['checks'][key])

    def test_mechanical_dimensions(self):
        m = fixtures.MECHANICAL
        ax, ay = m['a_left'], m['a_bottom']
        bx, by = m['width'] - m['b_right'], m['height'] - m['b_top']
        self.assertTrue(0 < ax < bx < m['width'])
        self.assertTrue(0 < ay < by < m['height'])
        self.assertEqual(self.answers[0], {'du_mm': 65, 'dv_mm': 33, 'distance_squared_mm2': 5314})
        self.assertEqual((bx-ax)**2 + (by-ay)**2, 5314)
        # A rigid rotation must preserve the actual depicted center distance.
        a, b = fixtures.mechanical_point(ax, ay), fixtures.mechanical_point(bx, by)
        self.assertAlmostEqual(sum((u-v)**2 for u,v in zip(a,b)), 5314 * fixtures.MECHANICAL_SCALE**2)

    def test_geometry_by_cell_enumeration(self):
        g = fixtures.GEOMETRY
        cells = {(x,y) for x in range(12) for y in range(9) if not (x >= 8 and y >= 5)}
        holes = set()
        for x,y,w,h in g['holes']:
            hole = {(i,j) for i in range(x,x+w) for j in range(y,y+h)}
            self.assertFalse(holes & hole)
            self.assertTrue(hole < cells)
            holes |= hole
        cells -= holes
        perimeter = sum((x+dx,y+dy) not in cells for x,y in cells for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)])
        self.assertEqual(self.answers[1], {'area_cm2': len(cells)*4, 'all_boundary_cm': perimeter*2, 'hole_count': 2})
        self.assertEqual((len(cells)*4, perimeter*2), (328,120))

    def test_map_unique_optimum_by_exhaustive_simple_paths(self):
        roads = fixtures.ROADS
        adj = {n: [] for n in 'ABCDEFGHIJKL'}
        for a,b,cost,blocked in roads:
            self.assertGreater(cost, 0)
            if not blocked:
                adj[a].append((b,cost)); adj[b].append((a,cost))
        paths = []
        def walk(route, cost):
            if route[-1] == 'L':
                if 'F' in route: paths.append((cost, route))
                return
            for node, weight in adj[route[-1]]:
                if node not in route: walk(route+[node], cost+weight)
        walk(['A'], 0)
        paths.sort()
        self.assertGreater(len(paths), 1)
        self.assertLess(paths[0][0], paths[1][0])
        self.assertEqual(self.answers[2], {'route': paths[0][1], 'cost': paths[0][0]})
        self.assertEqual(len(roads), 17)
        for a,b,_,_ in roads:
            p,q = fixtures.map_point(a), fixtures.map_point(b)
            self.assertTrue((p[0] == q[0]) != (p[1] == q[1]))

    def test_chart_legend_and_segment_counts(self):
        self.assertEqual(len(fixtures.STACKS), 4)
        totals = {}
        quarantine = 0
        for site, segments in fixtures.STACKS.items():
            self.assertEqual({s for s,_ in segments}, {'allocated','ready','quarantine','rejected'})
            totals[site] = sum(v for k,v in segments if k in ('allocated','ready'))
            quarantine += dict(segments)['quarantine']
        winner = max(totals, key=totals.get)
        self.assertEqual(sum(v == totals[winner] for v in totals.values()), 1)
        self.assertEqual(self.answers[3], {'highest_usable': winner, 'total_usable': sum(totals.values()), 'quarantine_total': quarantine})
        self.assertEqual(self.answers[3], {'highest_usable': 'West', 'total_usable': 146, 'quarantine_total': 43})

    def test_spreadsheet_independent_arithmetic(self):
        # Explicit arithmetic oracle, independent of formula evaluation/rendering.
        self.assertEqual(self.answers[4], {'D4': 2*17, 'E5': 3*12+5*9+2*17-3*4, 'C6': 103-9*3})
        self.assertEqual(fixtures.CELLS['C6'], '=E5-C3*B2')
        self.assertEqual(fixtures.CELLS['E4'], '=D4-$B$6')

    def test_rendered_spreadsheet_formulas_match_answers(self):
        # Evaluate the actual displayed formulas with a separate small parser.
        # This catches edits to formula text even when the numeric inputs stay fixed.
        def cell(ref):
            value = fixtures.CELLS[ref]
            if type(value) is int: return value
            expression = value.removeprefix('=').replace('$','')
            match = re.fullmatch(r'SUM\(([A-E])(\d):([A-E])(\d)\)', expression)
            if match:
                c1,r1,c2,r2 = match.groups()
                self.assertEqual(c1,c2)
                return sum(cell(c1+str(r)) for r in range(int(r1),int(r2)+1))
            return evaluate(ast.parse(expression,mode='eval').body)
        def evaluate(node):
            if isinstance(node,ast.Name): return cell(node.id)
            if isinstance(node,ast.Constant): return node.value
            if isinstance(node,ast.BinOp):
                a,b = evaluate(node.left),evaluate(node.right)
                if isinstance(node.op,ast.Mult): return a*b
                if isinstance(node.op,ast.Sub): return a-b
                if isinstance(node.op,ast.Add): return a+b
            raise AssertionError(f'Unsupported pictured formula: {ast.dump(node)}')
        self.assertEqual(self.answers[4], {ref:cell(ref) for ref in ('D4','E5','C6')})

    def test_network_reachability_and_failed_links(self):
        edges = {(a,b) for a,b,failed in fixtures.NETWORK if not failed}
        reached = {'A'}; distances = {'A':0}
        for distance in range(1,9):
            next_nodes = {b for a,b in edges if a in reached} - reached
            distances.update({n:distance for n in next_nodes}); reached |= next_nodes
        self.assertEqual(reached, set('ABEFG'))
        self.assertEqual(self.answers[5], {'reachable': sorted(reached-{'A'}), 'min_edges_to_G': distances['G']})
        self.assertEqual(len(fixtures.NETWORK), 10)

    def test_waveform_post_transition_sampling(self):
        # Inclusive left/exclusive right intervals explicitly test coincident edges.
        q = 1; bits = []; rises = 0
        for t in [2,6,10,14,18,22]:
            reset = (0 <= t < 3) or (14 <= t < 15)
            enabled = (0 <= t < 7) or (13 <= t < 19)
            data = (4 <= t < 10) or (16 <= t < 22)
            prev = q
            if reset: q = 0
            elif enabled: q = int(data)
            bits.append(str(q)); rises += int(prev == 0 and q == 1)
        self.assertEqual(self.answers[6], {'q_after_edges': ''.join(bits), 'q_rises': rises, 'final_q': q})
        self.assertEqual(''.join(bits), '011011')

    def test_connector_reflection_is_bijection(self):
        rear = fixtures.REAR_CODES
        self.assertEqual(len({v for row in rear for v in row}), 8)
        mapping = {4*r+c+1: rear[r][3-c] for r in range(2) for c in range(4)}
        self.assertEqual(self.answers[7], {'TX_wire': mapping[2], 'RX_wire': mapping[7], 'GND_wire': mapping[5], 'rear_top_left_pin': 4})
        self.assertEqual(self.answers[7]['TX_wire'], 'T')

    def test_document_exclusions_before_caps(self):
        rows = fixtures.DOCUMENT
        accepted = []; total = 0
        for ident, project, kind, amount, status in rows:
            if status != 'APPROVED': continue
            if kind == 'Travel' and project != 'Beta': value = amount*3//4
            elif kind == 'Meals' and project != 'Delta': value = min(amount,30)
            elif kind == 'Equipment' and project == 'Gamma': value = amount//2
            else: continue
            accepted.append(ident); total += value
        self.assertEqual(self.answers[8], {'eligible_rows': accepted, 'reimbursement_usd': total, 'excluded_count': len(rows)-len(accepted)})
        self.assertEqual((accepted,total), (['R1','R2','R7'],175))

    def test_tracking_unique_assignments_and_counts(self):
        frames = fixtures.TRACKING
        for frame in frames:
            self.assertEqual(len(set(frame)), 5)
            self.assertTrue(all(1 <= x <= 5 and 1 <= y <= 5 for x,y in frame))
        for old,new in zip(frames, frames[1:]):
            solutions = [p for p in itertools.permutations(new) if all(abs(a[0]-b[0])+abs(a[1]-b[1]) == 1 for a,b in zip(old,p))]
            self.assertEqual(solutions, [tuple(new)])
            self.assertGreaterEqual(sum(sum(abs(a[0]-b[0])+abs(a[1]-b[1])==1 for b in new)>1 for a in old), 2)
        self.assertEqual(self.answers[9], {'P_cell':'C3','R_cell':'D4','T_cell':'E2','token_at_B3':'S'})

    def test_rebuild_is_deterministic(self):
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.directory.iterdir()}
        fixtures.build_suite(self.directory)
        after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in self.directory.iterdir()}
        self.assertEqual(before, after)


if __name__ == '__main__':
    unittest.main(verbosity=2)
