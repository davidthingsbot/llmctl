"""Deterministic, offline v2 fixtures; no model calls or edits to the v1 suite.

Renderers and solvers share input data, never answer annotations. Circuit answers
come from the drawn wire geometry; cube answers come from folding the drawn net.
"""
import argparse
from collections import deque
from copy import deepcopy
from fractions import Fraction
from itertools import product
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
MIN_FONT_SIZE = 18
INK = '#17283a'
MUTED = '#496076'
BLUE = '#1269ad'
ORANGE = '#c45013'
GREEN = '#187843'


def font(size):
    if size < MIN_FONT_SIZE:
        raise ValueError('Fixture text must be at least 18px')
    return ImageFont.truetype(FONT, size)


class Surface:
    """Text bounds checks catch clipping while generating, including table cells."""
    def __init__(self, title, size):
        self.im = Image.new('RGB', size, 'white')
        self.d = ImageDraw.Draw(self.im)
        self.text((28, 20), title, 32)
        self.d.line((28, 68, size[0]-28, 68), fill=BLUE, width=3)

    def text(self, xy, value, size=22, fill=INK, anchor=None, max_width=None):
        value = str(value)
        f = font(size)
        box = self.d.textbbox(xy, value, font=f, anchor=anchor)
        if not (0 <= box[0] <= box[2] <= self.im.width
                and 0 <= box[1] <= box[3] <= self.im.height):
            raise ValueError(f'Text outside canvas: {value!r} {box}')
        if max_width is not None and box[2]-box[0] > max_width:
            raise ValueError(f'Text outside cell: {value!r}')
        self.d.text(xy, value, font=f, fill=fill, anchor=anchor)

    def lines(self, xy, lines, size=22, step=33):
        for i, line in enumerate(lines):
            self.text((xy[0], xy[1]+i*step), line, size)

    def table(self, xy, widths, headers, rows, row_height=44, size=22):
        x, y = xy
        for i, row in enumerate([headers] + list(rows)):
            self.d.rectangle((x, y+i*row_height, x+sum(widths), y+(i+1)*row_height),
                             fill='#dbe8f2' if i == 0 else ('#f0f4f7' if i % 2 else 'white'))
            offset = x
            for width, value in zip(widths, row):
                self.text((offset+10, y+i*row_height+9), value, size, max_width=width-20)
                offset += width


LEDGER = [
    dict(id='A11', qty=48, rejects=3, cents=125, state='RELEASE'),
    dict(id='B22', qty=35, rejects=2, cents=240, state='HOLD'),
    dict(id='C33', qty=60, rejects=5, cents=80, state='RELEASE'),
    dict(id='D44', qty=24, rejects=1, cents=350, state='RELEASE'),
    dict(id='E55', qty=40, rejects=4, cents=150, state='HOLD'),
    dict(id='F66', qty=32, rejects=2, cents=200, state='RELEASE'),
]
AMENDMENTS = [
    ('A11', 'qty', 'ADD', -6), ('C33', 'rejects', 'SET', 8),
    ('B22', 'state', 'SET', 'RELEASE'), ('D44', 'cents', 'SET', 320),
    ('A11', 'rejects', 'SET', 1), ('F66', 'state', 'SET', 'HOLD'),
    ('E55', 'qty', 'ADD', 5), ('B22', 'qty', 'SET', 38),
]


def reconcile(ledger, amendments):
    rows = deepcopy(ledger)
    by_id = {r['id']: r for r in rows}
    for ident, field, op, value in amendments:
        if op == 'SET':
            by_id[ident][field] = value
        elif op == 'ADD':
            by_id[ident][field] += value
        else:
            raise ValueError(f'Unknown amendment: {op}')
    if any(not 0 <= r['rejects'] <= r['qty'] for r in rows):
        raise ValueError('Invalid final quantities')
    released = [r for r in rows if r['state'] == 'RELEASE']
    amounts = {r['id']: (r['qty']-r['rejects'])*r['cents'] for r in released}
    largest = [k for k, n in amounts.items() if n == max(amounts.values())]
    if len(largest) != 1:
        raise ValueError('Largest released line must be unique')
    return rows, dict(released_good_units=sum(r['qty']-r['rejects'] for r in released),
                      released_value_cents=sum(amounts.values()),
                      held_ids=[r['id'] for r in rows if r['state'] == 'HOLD'],
                      largest_value_id=largest[0])


def render_reconciliation():
    s = Surface('REVISED DISPATCH LEDGER', (1420, 1190))
    s.text((30, 88), 'Original document', 26)
    s.table((30, 132), [180, 210, 210, 240, 260],
            ['Line ID', 'qty', 'rejects', 'cents', 'state'],
            [[r[k] for k in ('id', 'qty', 'rejects', 'cents', 'state')] for r in LEDGER])
    s.text((30, 465), 'Amendments: apply in numbered order', 26)
    s.table((30, 509), [120, 160, 220, 170, 430],
            ['Order', 'Line ID', 'Field', 'Operation', 'Value'],
            [(i, *a) for i, a in enumerate(AMENDMENTS, 1)], row_height=42)
    s.lines((30, 910), [
        'Field definitions and reconciliation rules',
        'qty = gross units, including rejects. rejects = absolute rejected-unit count.',
        'cents = price per good unit, in integer cents. Good units = qty minus rejects.',
        'SET replaces the named field. ADD changes only that field by the signed value.',
        'Unmentioned fields stay unchanged; changing qty does not scale rejects.',
        'Only final RELEASE lines contribute good units and value. No tax or rounding.',
        'List final HOLD IDs in original row order. Largest value means one released line.',
    ], step=35)
    return s.im, reconcile(LEDGER, AMENDMENTS)[1]


SERIES = {
    'A': [20, 40, 60, 35, 65, 45, 70, 40, 60],
    'B': [50, 45, 35, 55, 40, 60, 50, 65, 45],
    'C': [15, 25, 40, 30, 45, 35, 55, 30, 40],
}


def analyze_plot(series):
    a, b, c = (series[k] for k in 'ABC')
    candidates = [i for i in range(len(a)-1)
                  if a[i] < b[i] and a[i+1] > b[i+1]
                  and max(c[i], c[i+1]) <= 40 and a[i+1]-a[i] >= 20]
    chosen = min(candidates, key=lambda i: (-(a[i+1]-b[i+1]), i))
    fraction = Fraction(b[chosen]-a[chosen],
                        a[chosen+1]-a[chosen]-b[chosen+1]+b[chosen])
    crossing = 60*(chosen+fraction)
    area = Fraction(c[chosen]+c[chosen+1], 2)*60
    if crossing.denominator != 1 or area.denominator != 1:
        raise ValueError('Integer answer schema requires exact integer results')
    return candidates, dict(start_minute=chosen, end_minute=chosen+1,
                            crossing_second=int(crossing),
                            right_gap=a[chosen+1]-b[chosen+1],
                            c_area_unit_seconds=int(area))


def render_plot():
    s = Surface('THREE TELEMETRY CHANNELS', (1420, 1170))
    s.text((35, 88), 'Value (units)', 24)
    x0, y0, dx, dy = 125, 780, 150, 8
    for value in range(0, 81, 5):
        y = y0-value*dy
        s.d.line((x0, y, x0+8*dx, y), fill='#aebdca' if value % 10 == 0 else '#e0e6eb')
        if value % 10 == 0:
            s.text((92, y), value, 21, anchor='rm')
    for t in range(9):
        x = x0+t*dx
        s.d.line((x, y0, x, y0-640), fill='#d1dae1')
        s.text((x, y0+28), t, 23, anchor='mm')
    s.text((1070, 835), 'Time (minutes)', 24)
    for channel, color, marker in [('A', BLUE, 'circle'), ('B', ORANGE, 'square'), ('C', GREEN, 'triangle')]:
        points = [(x0+i*dx, y0-n*dy) for i, n in enumerate(SERIES[channel])]
        s.d.line(points, fill=color, width=4)
        for x, y in points:
            if marker == 'circle':
                s.d.ellipse((x-7, y-7, x+7, y+7), fill='white', outline=color, width=3)
            elif marker == 'square':
                s.d.rectangle((x-7, y-7, x+7, y+7), fill='white', outline=color, width=3)
            else:
                s.d.polygon([(x, y-9), (x-8, y+7), (x+8, y+7)], fill=color)
        s.text((380+'ABC'.index(channel)*290, 88), f'{channel}: {marker}', 24, color)
    s.lines((30, 895), [
        'Selection rule (only adjacent integer-minute samples define candidate intervals):',
        'A is strictly below B at the left endpoint and strictly above B at the right endpoint.',
        'C is at most 40 at BOTH endpoints. A increases by at least 20 across the interval.',
        'Choose the candidate with largest right-end A minus B; break ties by earliest start.',
        'Straight segments mean linear interpolation. Crossing time: seconds since minute 0.',
        'C area: integral under C across the entire chosen interval, in unit-seconds.',
        'Markers fall on the 5-unit grid. Right gap means A minus B at the chosen right endpoint.',
    ], step=35)
    return s.im, analyze_plot(SERIES)[1]


# Each polyline is a continuous conductor. Intersections connect only at dots;
# polyline bends are inherently continuous. Ports are part of the drawn geometry.
WIRES = [
    [(100, 200), (540, 200)], [(100, 360), (540, 360)],
    [(100, 520), (540, 520)], [(100, 680), (560, 680)],
    [(230, 200), (230, 230), (640, 230)],
    [(320, 520), (320, 290), (640, 290)],
    [(410, 360), (410, 470), (640, 470)],
    [(500, 680), (500, 530), (640, 530)],
    [(560, 680), (560, 380), (1020, 380)],
    [(800, 260), (900, 260), (900, 620), (1020, 620)],
    [(900, 300), (1020, 300)],
    [(800, 500), (940, 500), (940, 700), (1020, 700)],
    [(1180, 340), (1220, 340), (1220, 460), (1280, 460)],
    [(1180, 660), (1240, 660), (1240, 540), (1280, 540)],
    [(1430, 500), (1480, 500)],
]
JUNCTIONS = [(230, 200), (320, 520), (410, 360), (500, 680), (560, 680), (900, 300)]
DRIVERS = {**{k: (100, y) for k, y in zip('ABCD', (200, 360, 520, 680))},
           'G1': (800, 260), 'G2': (800, 500), 'G3': (1180, 340),
           'G4': (1180, 660), 'G5': (1430, 500)}
PORTS = {'G1': [(640, 230), (640, 290)], 'G2': [(640, 470), (640, 530)],
         'G3': [(1020, 300), (1020, 380)], 'G4': [(1020, 620), (1020, 700)],
         'G5': [(1280, 460), (1280, 540)]}
GATES = {'G1': 'XOR', 'G2': 'AND', 'G3': 'XOR', 'G4': 'OR', 'G5': 'AND'}


def on_wire(point, wire):
    x, y = point
    return any((a[0] == b[0] == x and min(a[1], b[1]) <= y <= max(a[1], b[1]))
               or (a[1] == b[1] == y and min(a[0], b[0]) <= x <= max(a[0], b[0]))
               for a, b in zip(wire, wire[1:]))


def circuit_nets(wires, junctions):
    parent = list(range(len(wires)))

    def root(i):
        while i != parent[i]:
            i = parent[i]
        return i

    for dot in junctions:
        touching = [i for i, wire in enumerate(wires) if on_wire(dot, wire)]
        for i in touching[1:]:
            parent[root(i)] = root(touching[0])

    def component(point):
        touching = {root(i) for i, wire in enumerate(wires) if on_wire(point, wire)}
        if len(touching) != 1:
            raise ValueError(f'Ambiguous or missing driver connection at {point}')
        return touching.pop()

    drivers = {}
    for label, point in DRIVERS.items():
        drivers.setdefault(component(point), []).append(label)

    def source(point):
        labels = drivers.get(component(point), [])
        if len(labels) != 1:
            raise ValueError(f'Expected one driver at {point}; got {labels}')
        return labels[0]

    nets = {gate: tuple(source(p) for p in ports) for gate, ports in PORTS.items()}
    if source((1480, 500)) != 'G5':
        raise ValueError('Output driver must be G5')
    return nets


def evaluate_circuit(inputs, nets):
    values = dict(inputs)
    for gate, op in GATES.items():
        a, b = (values[k] for k in nets[gate])
        values[gate] = {'XOR': a ^ b, 'AND': a & b, 'OR': a | b}[op]
    return values['G5']


def render_circuit():
    s = Surface('JUNCTION LOGIC NETWORK', (1540, 1110))
    s.text((30, 91), 'Signals flow from lettered inputs through named gates to Y.', 24)
    for wire in WIRES:
        s.d.line(wire, fill=INK, width=3)
    for x, y in JUNCTIONS:
        s.d.ellipse((x-7, y-7, x+7, y+7), fill=INK)
    for label in 'ABCD':
        x, y = DRIVERS[label]
        s.text((x-35, y), label, 30, anchor='mm')
        s.d.ellipse((x-5, y-5, x+5, y+5), fill=INK)
    for gate, ports in PORTS.items():
        x = ports[0][0]
        y1, y2 = ports[0][1]-30, ports[1][1]+30
        right = DRIVERS[gate][0]
        s.d.rectangle((x, y1, right, y2), fill='#eaf1f7', outline=INK, width=3)
        s.text(((x+right)/2, (y1+y2)/2-19), gate, 23, anchor='mm')
        s.text(((x+right)/2, (y1+y2)/2+18), GATES[gate], 26, anchor='mm')
    s.text((1497, 500), 'Y', 28, anchor='mm')
    s.lines((30, 785), [
        'Wiring legend: filled dot = electrical junction. Crossing without a dot = NOT connected.',
        'A bend in one wire stays connected. Gate boxes have two left inputs and one right output.',
        'XOR = 1 iff inputs differ. AND = 1 iff both are 1. OR = 1 iff at least one is 1.',
        'Input code order is A B C D (A is the leftmost bit). List codes with Y = 1 in ascending order.',
        'g1_sources / g2_sources: the lettered inputs driving each gate, alphabetically sorted.',
        'Scenario: A = 1, B = 1, C = 0, D = 1. scenario_y is Y under this input.',
        'Fault scenario: force C to 1; keep the other scenario inputs. fault_y is the resulting Y.',
    ], step=40)
    nets = circuit_nets(WIRES, JUNCTIONS)
    high = [''.join(map(str, bits)) for bits in product((0, 1), repeat=4)
            if evaluate_circuit(dict(zip('ABCD', bits)), nets)]
    return s.im, dict(g1_sources=sorted(nets['G1']), g2_sources=sorted(nets['G2']),
                      high_input_codes=high,
                      scenario_y=evaluate_circuit(dict(A=1, B=1, C=0, D=1), nets),
                      fault_y=evaluate_circuit(dict(A=1, B=1, C=1, D=1), nets))


CUBE_NET = {'A': (1, 0), 'B': (0, 1), 'C': (1, 1), 'D': (2, 1), 'E': (3, 1), 'F': (1, 2)}
CUBE_OPTIONS = {'P': ('A', 'C', 'B'), 'Q': ('A', 'C', 'D'), 'R': ('A', 'F', 'D'),
                'S': ('C', 'E', 'A'), 'T': ('B', 'D', 'F'), 'U': ('F', 'C', 'D')}
FACE_COLORS = dict(zip('ABCDEF', ['#f1c66c', '#a6c8ed', '#afdbb7', '#eaaaba', '#c6b3e8', '#a5dce2']))


def neg(vector):
    return tuple(-n for n in vector)


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def fold_cube(net):
    # Each face frame is (page-right, page-down, outward normal).
    positions = {p: label for label, p in net.items()}
    frames = {'C': ((1, 0, 0), (0, 1, 0), (0, 0, 1))}
    queue = deque(['C'])
    while queue:
        label = queue.popleft()
        x, y = net[label]
        u, v, n = frames[label]
        neighbors = [((1, 0), (neg(n), v, u)), ((-1, 0), (n, v, neg(u))),
                     ((0, 1), (u, neg(n), v)), ((0, -1), (u, n, neg(v)))]
        for (dx, dy), frame in neighbors:
            other = positions.get((x+dx, y+dy))
            if other is None:
                continue
            if other in frames and frames[other] != frame:
                raise ValueError('Inconsistent fold')
            if other not in frames:
                frames[other] = frame
                queue.append(other)
    normals = {label: frame[2] for label, frame in frames.items()}
    if len(normals) != 6 or len(set(normals.values())) != 6:
        raise ValueError('Net must fold to six distinct cube faces')
    return normals


def analyze_cube():
    normals = fold_cube(CUBE_NET)
    valid = [key for key, (top, front, right) in CUBE_OPTIONS.items()
             if cross(normals[front], normals[top]) == normals[right]]
    if len(valid) != 1:
        raise ValueError('Cube option must be unique')
    top, front, right = (normals[k] for k in CUBE_OPTIONS[valid[0]])
    # Orientations represented by the original normals now occupying each position.
    for direction in ('right', 'away', 'right'):
        if direction == 'right':
            top, right = neg(right), top
        else:
            top, front = front, neg(top)
    labels = {n: label for label, n in normals.items()}
    return valid, dict(option=valid[0], opposite_c=labels[neg(normals['C'])],
                        final_top=labels[top], final_front=labels[front], final_right=labels[right])


def render_cube():
    s = Surface('FOLD, MATCH, THEN ROLL', (1490, 1130))
    s.text((30, 92), 'Printed outside faces; fold edges into a cube.', 24)
    side, x0, y0 = 130, 30, 190
    for label, (x, y) in CUBE_NET.items():
        box = (x0+x*side, y0+y*side, x0+(x+1)*side, y0+(y+1)*side)
        s.d.rectangle(box, fill=FACE_COLORS[label], outline=INK, width=3)
        s.text((box[0]+side/2, box[1]+side/2), label, 46, anchor='mm')
    s.text((650, 92), 'Which candidate is possible without reflection?', 24)
    for i, (option, (top, front, right)) in enumerate(CUBE_OPTIONS.items()):
        cx, y = 745+(i % 3)*285, 200+(i//3)*300
        s.text((cx, y-30), option, 28, anchor='mm')
        polygons = [([(cx, y), (cx+95, y+48), (cx, y+96), (cx-95, y+48)], top),
                    ([(cx-95, y+48), (cx, y+96), (cx, y+200), (cx-95, y+152)], front),
                    ([(cx, y+96), (cx+95, y+48), (cx+95, y+152), (cx, y+200)], right)]
        for polygon, label in polygons:
            s.d.polygon(polygon, fill=FACE_COLORS[label], outline=INK, width=3)
            center = tuple(sum(p[j] for p in polygon)/4 for j in (0, 1))
            s.text(center, label, 38, anchor='mm')
    s.lines((30, 770), [
        'Candidate views: top face above; FRONT is the left visible side; RIGHT is the right visible side.',
        'Letters identify faces; their printed orientation is not part of the match. Colors repeat the labels.',
        'Choose the only physically possible candidate; start the following rolls in that orientation.',
        'Roll sequence on a flat table: RIGHT  ->  AWAY  ->  RIGHT (each roll is 90 degrees).',
        'RIGHT: right face becomes bottom; top becomes right. Front and back stay in place.',
        'AWAY: front face becomes top; top becomes back. Left and right stay in place.',
        'Report the face opposite C in the folded cube, plus final top, front and right face labels.',
    ], step=42)
    return s.im, analyze_cube()[1]


BUSY = {'R1': [(0, 60), (135, 195)], 'R2': [(0, 30), (150, 180), (210, 240)],
        'Ada': [(0, 45), (90, 150), (180, 240)],
        'Bo': [(0, 60), (105, 120), (165, 210)],
        'Scanner': [(0, 30), (60, 90), (150, 180)]}


def overlap(a, b):
    return max(a[0], b[0]) < min(a[1], b[1])


def schedule_plans(busy):
    plans = []
    for start, room, tech in product(range(0, 181, 15), ('R1', 'R2'), ('Ada', 'Bo')):
        if room == 'R1' and tech != 'Ada':
            continue
        needs = {room: [(start, start+60)], tech: [(start, start+15), (start+45, start+60)],
                 'Scanner': [(start+15, start+45)]}
        if all(not overlap(span, occupied) for r, spans in needs.items()
               for span in spans for occupied in busy[r]):
            plans.append((start, room, tech))
    return plans


def hhmm(minutes):
    return f'{9+minutes//60:02}:{minutes%60:02}'


def render_schedule():
    s = Surface('BOOK ONE SCAN APPOINTMENT', (1500, 1150))
    s.text((30, 92), 'Occupied bars: start above end. All unshaded time is free.', 24)
    x0, dx = 200, 5
    for minute in range(0, 241, 15):
        x = x0+minute*dx
        s.d.line((x, 180, x, 680), fill='#bdcbd6' if minute % 30 == 0 else '#e3e8ed')
        if minute % 30 == 0:
            s.text((x, 154), hhmm(minute), 20, anchor='mm')
    for i, (resource, intervals) in enumerate(BUSY.items()):
        y = 210+i*96
        s.text((30, y+10), resource, 25)
        for a, b in intervals:
            s.d.rectangle((x0+a*dx, y, x0+b*dx, y+51), fill=BLUE)
            for when, offset in [(a, 14), (b, 37)]:
                s.text((x0+(a+b)*dx/2, y+offset), hhmm(when), 18, 'white', anchor='mm',
                       max_width=(b-a)*dx-8)
    s.lines((30, 727), [
        'Booking rules',
        'Choose one room (R1 or R2) and one technician (Ada or Bo) for the whole appointment.',
        'R1 permits Ada only. R2 permits either technician. There is one shared Scanner.',
        'An appointment lasts 60 minutes: setup 15, scan 30, finish 15, with no gaps.',
        'Room: occupied for all 60 minutes. Technician: setup AND finish; free during scan.',
        'Scanner: occupied only during the middle 30 minutes. All required resources must be free.',
        'Start on a 15-minute tick; the entire appointment must lie within 09:00-13:00.',
        'Touching endpoints do not overlap. Ignore travel; no resource substitutions mid-appointment.',
        'Objective: earliest completion time. The displayed instance has a unique optimal plan.',
    ], step=41)
    plans = schedule_plans(BUSY)
    first = min(p[0] for p in plans)
    best = [p for p in plans if p[0] == first]
    if len(best) != 1:
        raise ValueError('Schedule optimum must be unique')
    start, room, technician = best[0]
    return s.im, dict(room=room, technician=technician, start=hhmm(start), end=hhmm(start+60))


ROUTES = [('IN', 'H1', 'triangle', True), ('IN', 'H2', 'triangle', False),
          ('IN', 'H3', 'circle', True), ('H1', 'N4', 'square', True),
          ('H1', 'N7', 'diamond', True), ('H2', 'N2', 'square', True),
          ('H3', 'N9', 'square', True)]
NODES = {'N4': ('K2', 'L8', 17), 'N7': ('K2', 'L3', 17),
         'N2': ('K8', 'L8', 19), 'N9': ('K2', 'L8', 21)}
REGISTRY = [('K2', 'L3', 'LIVE', 'P7', 2, 'S2'), ('K8', 'L8', 'LIVE', 'P7', 4, 'S5'),
            ('K2', 'L8', 'OLD', 'P9', 5, 'S2'), ('K2', 'L8', 'LIVE', 'P7', 3, 'S2'),
            ('K3', 'L8', 'LIVE', 'P9', 3, 'S5')]
CALIBRATION = [('P7', 1, -4, 2), ('P7', 2, 3, 2), ('P9', 3, 1, 5),
               ('P7', 3, -3, 4), ('P7', 4, 2, 3), ('P9', 5, -2, 3)]
DISPATCH = [('S2', 0, 49, 'BAY-1'), ('S5', 50, 59, 'BAY-9'),
            ('S2', 60, 99, 'BAY-3'), ('S2', 50, 59, 'BAY-6')]


def only(values):
    values = list(values)
    if len(values) != 1:
        raise ValueError(f'Lookup must be unique: {values}')
    return values[0]


def cross_reference():
    trace = ['IN']
    for shape in ('triangle', 'square'):
        trace.append(only(dst for src, dst, mark, active in ROUTES
                          if src == trace[-1] and mark == shape and active))
    unit, lot, raw = NODES[trace[-1]]
    _, _, _, probe, rev, rack = only(r for r in REGISTRY if r[:3] == (unit, lot, 'LIVE'))
    _, _, offset, gain = only(r for r in CALIBRATION if r[:2] == (probe, rev))
    adjusted = gain*(raw+offset)
    destination = only(r[3] for r in DISPATCH if r[0] == rack and r[1] <= adjusted <= r[2])
    return trace, dict(node=trace[-1], probe=probe, revision=rev,
                       adjusted=adjusted, destination=destination)


def route_arrow(s, a, b, active):
    import math
    if active:
        s.d.line((a, b), fill=INK, width=3)
    else:
        length = math.dist(a, b)
        for pos in range(0, int(length), 18):
            points = [tuple(a[j]+(b[j]-a[j])*min(t/length, 1) for j in (0, 1))
                      for t in (pos, pos+10)]
            s.d.line(points, fill=MUTED, width=3)
    angle = math.atan2(b[1]-a[1], b[0]-a[0])
    s.d.polygon([b]+[(b[0]-14*math.cos(angle+d), b[1]-14*math.sin(angle+d))
                    for d in (-0.5, 0.5)], fill=INK)


def route_symbol(s, center, shape):
    x, y = center
    s.d.ellipse((x-18, y-18, x+18, y+18), fill='white')
    if shape == 'triangle':
        s.d.polygon([(x, y-13), (x-13, y+12), (x+13, y+12)], fill=BLUE)
    elif shape == 'square':
        s.d.rectangle((x-11, y-11, x+11, y+11), fill=ORANGE)
    elif shape == 'circle':
        s.d.ellipse((x-12, y-12, x+12, y+12), fill=GREEN)
    else:
        s.d.polygon([(x, y-15), (x+13, y), (x, y+15), (x-13, y)], fill='#8150a5')


def render_cross_reference():
    s = Surface('ROUTE -> REGISTRY -> CALIBRATION -> DISPATCH', (1560, 1350))
    s.text((30, 89), 'A. Routing diagram', 25)
    positions = {'IN': (90, 375), 'H1': (350, 220), 'H2': (350, 380), 'H3': (350, 535),
                 'N4': (660, 185), 'N7': (660, 315), 'N2': (660, 445), 'N9': (660, 575)}
    for src, dst, shape, active in ROUTES:
        a = (positions[src][0]+35, positions[src][1])
        b = (positions[dst][0]-(0 if dst.startswith('N') else 35), positions[dst][1])
        route_arrow(s, a, b, active)
        route_symbol(s, tuple((a[j]+b[j])/2 for j in (0, 1)), shape)
    for name, (x, y) in positions.items():
        if name.startswith('N'):
            unit, lot, raw = NODES[name]
            s.d.rectangle((x, y-40, x+215, y+46), fill='#eef3f7', outline=INK, width=2)
            s.text((x+10, y-32), f'{name}   {unit} / {lot}', 23)
            s.text((x+10, y+4), f'raw = {raw}', 22)
        else:
            s.d.ellipse((x-35, y-28, x+35, y+28), fill='#dbe8f2', outline=INK, width=2)
            s.text((x, y), name, 22, anchor='mm')
    s.text((925, 89), 'B. Device registry', 25)
    s.table((920, 135), [90, 80, 100, 100, 80, 90],
            ['Unit', 'Lot', 'State', 'Probe', 'Rev', 'Rack'], REGISTRY, row_height=63, size=20)
    s.text((925, 550), 'Rev = calibration revision', 21)
    s.text((30, 675), 'C. Calibration table', 25)
    s.table((30, 719), [170, 170, 170, 170], ['Probe', 'Revision', 'Offset', 'Gain'],
            CALIBRATION, row_height=43)
    s.text((815, 675), 'D. Dispatch bands (inclusive)', 25)
    s.table((810, 719), [150, 160, 150, 240], ['Rack', 'Minimum', 'Maximum', 'Destination'],
            DISPATCH, row_height=55)
    s.lines((30, 1060), [
        'Procedure: begin at IN. Follow a TRIANGLE edge, then a SQUARE edge; use solid arrows only.',
        'Dashed arrows are archived. Symbols label edges; crossings do not create new routes.',
        'At the reached node, read Unit / Lot and raw. Match BOTH Unit and Lot to the LIVE registry row.',
        'Use that row\'s exact Probe AND Rev in the calibration table; do not pick the latest revision.',
        'Compute adjusted = Gain x (raw + Offset), then match the registry Rack and the adjusted band.',
        'Return the reached node, selected probe and revision, adjusted reading, and dispatch destination.',
    ], step=41)
    return s.im, cross_reference()[1]


QUESTIONS = {
    'hard_v2_reconciliation': 'Reconcile the document using its displayed rules. Return JSON: '
        'released_good_units (integer), released_value_cents (integer), held_ids (ordered list of strings), '
        'largest_value_id (string).',
    'hard_v2_crossing_plot': 'Apply the plot selection rule and calculate the requested quantities. Return JSON: '
        'start_minute (integer), end_minute (integer), crossing_second (integer), right_gap (integer), '
        'c_area_unit_seconds (integer).',
    'hard_v2_logic_network': 'Trace and evaluate the displayed logic network. Return JSON: '
        'g1_sources (list of strings), g2_sources (list of strings), high_input_codes (list of strings), '
        'scenario_y (integer), fault_y (integer).',
    'hard_v2_cube': 'Solve the displayed fold, candidate match, and roll sequence. Return JSON: '
        'option (string), opposite_c (string), final_top (string), final_front (string), final_right (string).',
    'hard_v2_resources': 'Find the optimal appointment under all displayed constraints. Return JSON: '
        'room (string), technician (string), start (HH:MM string), end (HH:MM string).',
    'hard_v2_cross_reference': 'Follow the displayed cross-reference procedure. Return JSON: '
        'node (string), probe (string), revision (integer), adjusted (integer), destination (string).',
}
RENDERERS = [render_reconciliation, render_plot, render_circuit,
             render_cube, render_schedule, render_cross_reference]


def build_suite(directory, v1_directory=None):
    directory = Path(directory).resolve()
    v1_directory = Path(v1_directory or Path(__file__).parent / 'fixtures' / 'vision-v1').resolve()
    if directory == v1_directory:
        raise ValueError('v2 output must not overwrite v1')
    original = json.loads((v1_directory / 'manifest.json').read_text())['tasks']
    baseline = deepcopy([t for t in original if t['difficulty'] in ('easy', 'medium')])
    if [sum(t['difficulty'] == d for t in baseline) for d in ('easy', 'medium')] != [3, 3]:
        raise ValueError('v1 must supply exactly three easy and three medium tasks')
    for task in baseline:
        # Resolve against the supplied v1 directory for portability after checkout.
        image = v1_directory / Path(task['image']).name
        if not image.is_file():
            raise FileNotFoundError(image)
        task['image'] = str(image.resolve())
    directory.mkdir(parents=True, exist_ok=True)
    hard = []
    for (ident, question), renderer in zip(QUESTIONS.items(), RENDERERS):
        im, expected = renderer()
        path = directory / f'{ident}.png'
        im.save(path)
        hard.append(dict(id=ident, difficulty='hard', image=str(path), question=question, expected=expected))
    tasks = baseline+hard
    if len({t['id'] for t in tasks}) != len(tasks):
        raise ValueError('Task IDs must be unique')
    for filename, version, subset in [('manifest.json', 'synthetic-vision-v2', tasks),
                                      ('hard-manifest.json', 'synthetic-vision-v2-hard', hard)]:
        (directory / filename).write_text(json.dumps(dict(version=version, tasks=subset), indent=2)+'\n')
    # Overview only. Judge readability on original PNGs, not downscaled thumbnails.
    sheet = Surface('VISION V2: SIX CANDIDATE HARD TASKS', (1560, 1380))
    for i, task in enumerate(hard):
        x, y = 20+(i % 3)*515, 90+(i//3)*635
        sheet.text((x, y), task['id'].removeprefix('hard_v2_'), 23)
        with Image.open(task['image']) as source:
            source.thumbnail((495, 575), Image.Resampling.LANCZOS)
            sheet.im.paste(source, (x, y+40))
    sheet.im.save(directory / 'contact-sheet.png')
    return tasks


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).parent / 'fixtures' / 'vision-v2')
    parser.add_argument('--v1', type=Path, default=Path(__file__).parent / 'fixtures' / 'vision-v1')
    args = parser.parse_args()
    built = build_suite(args.output, args.v1)
    print(f'Built {len(built)} tasks (6 reused, 6 hard) in {args.output.resolve()}')
