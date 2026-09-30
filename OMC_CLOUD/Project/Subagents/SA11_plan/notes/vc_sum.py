#!/usr/bin/env python3
"""[SA11 V] summary.  Arms with an LL offset k: best k per rate by mean plane PSNR (same rule as struct_sum)."""
import json, glob, math, sys, re
import numpy as np
SD = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA11_plan/struct'
VD = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA11_plan/vc'
T = (0.5, 1.0, 2.0)
order = ['gfx_f0', 'gfx_f5', 'dng720_f0', 'dng720_f5', 'dng1080_f0', 'dng1080_f5', 'city_f0', 'city_f5', 'spot_f0', 'spot_f5']
def at1(pts, b):
    P = sorted([p for p in pts if p[1] > 0], key=lambda p: p[1]); xs = [math.log2(p[1]) for p in P]; x = math.log2(b)
    if not P or x < xs[0] or x > xs[-1]: return None
    return [float(np.interp(x, xs, [p[2][k] for p in P])) for k in range(3)]
def best(ptsets, b):
    bb = None
    for pts in ptsets:
        v = at1(pts, b)
        if v is not None and (bb is None or np.mean(v) > np.mean(bb)): bb = v
    return bb
cells = {}
for t in order:
    try: base = json.load(open('%s/%s.json' % (SD, t)))['arms']['base']
    except Exception: continue
    c = {'base': list(base.values())}
    for part in ('A', 'C'):
        try: j = json.load(open('%s/%s.%s.json' % (VD, t, part)))
        except Exception: continue
        for k, v in j.items():
            arm = re.sub(r'_k-?\d+$', '', k); c.setdefault(arm, []).append(v)
    cells[t] = c
tags = [t for t in order if t in cells]
arms = []
for t in tags:
    for a in cells[t]:
        if a not in arms: arms.append(a)
def row(a, ref='base'):
    s = '  %-14s' % a
    for b in T:
        ds = []
        for t in tags:
            if a in cells[t] and ref in cells[t]:
                x = best(cells[t][a], b); r = best(cells[t][ref], b)
                if x is not None and r is not None: ds.append([x[k] - r[k] for k in range(3)])
        if not ds: s += ' | %.1f n/a' % b; continue
        m = np.mean(ds, 0); w = np.min(ds, 0)
        s += ' | %.1f: %+.2f/%+.2f/%+.2f worst %+.2f/%+.2f/%+.2f n=%d' % (b, m[0], m[1], m[2], w[0], w[1], w[2], len(ds))
    oo = [p[3] for t in tags if a in cells[t] for pts in cells[t][a] for p in pts]
    return s + ' | max out-of-range %d' % (max(oo) if oo else -1)
print('cells:', ', '.join(tags))
print('DELTA vs baseline (dB Y/Cb/Cr, mean over cells / worst cell):')
for a in arms:
    if a != 'base': print(row(a))
print('\nV4: clamped S5a vs unclamped S5a:')
for pr in ('up3', 'gsel'):
    print(row('S5aC_' + pr, 'S5a_' + pr))
print('\nPER CELL (dB Y/Cb/Cr at 0.5 | 1.0 | 2.0):')
for t in tags:
    for a in arms:
        if a == 'base' or a not in cells[t]: continue
        v = []
        for b in T:
            x = best(cells[t][a], b); r = best(cells[t]['base'], b)
            v.append('n/a' if x is None or r is None else '/'.join('%+.2f' % (x[k] - r[k]) for k in range(3)))
        print('  %-11s %-14s %s' % (t, a, ' | '.join(v)))
# V5 inter
print('\nV5 INTER (frame 5 as residual vs reconstructed frame 4, zero motion; frame-5 bits only): dB vs baseline inter')
for t in tags:
    try: j = json.load(open('%s/%s.D.json' % (VD, t)))
    except Exception: continue
    for a in j:
        if a == 'base': continue
        v = []
        for b in T:
            x = at1(j[a], b); r = at1(j['base'], b)
            v.append('n/a' if x is None or r is None else '/'.join('%+.2f' % (x[k] - r[k]) for k in range(3)))
        print('  %-11s %-10s %s' % (t, a, ' | '.join(v)))
    rb = [at1(j['base'], b) for b in T]
    print('  %-11s base abs    %s' % (t, ' | '.join('n/a' if r is None else '/'.join('%.2f' % x for x in r) for r in rb)))
# V3
print('\nV3 step search (coordinate descent, per-band power-of-two offsets -2..+2 on the step, 2 passes, objective = mean of')
print('   the three plane PSNRs at the target bpp); tuned vs default and vs baseline default (dB Y/Cb/Cr):')
for f in sorted(glob.glob(VD + '/*.B*.json')):
    t = f.split('/')[-1].split('.')[0]; j = json.load(open(f)); nm = f.split('.')[-2]
    s = []
    for b in T:
        e = j.get('%.1f' % b)
        if not e or e['psnr'] is None: s.append('n/a'); continue
        r = best(cells[t]['base'], b) if t in cells else None
        s.append('%s offs %s%s' % ('/'.join('%.2f' % x for x in e['psnr']), e['offs'],
                                   '' if r is None else ' (vs base default %s)' % '/'.join('%+.2f' % (e['psnr'][k] - r[k]) for k in range(3))))
    print('  %-11s %-10s %s' % (t, nm, ' || '.join(s)))
