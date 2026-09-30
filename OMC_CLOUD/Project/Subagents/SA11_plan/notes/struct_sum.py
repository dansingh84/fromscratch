#!/usr/bin/env python3
"""[SA11 S] summary: PSNR per plane at 0.5/1.0/2.0 bpp (linear interpolation in log2 bpp between sweep points);
per arm and rate the LL/coarse step offset k (x2^k on that band's step) is the one maximising the mean of the three
plane PSNRs; deltas vs the baseline (same envelope rule)."""
import json, glob, sys, math
import numpy as np
D = sys.argv[1]
T = (0.5, 1.0, 2.0)
def at1(pts, b):
    P = sorted([p for p in pts if p[1] > 0], key=lambda p: p[1]); xs = [math.log2(p[1]) for p in P]; x = math.log2(b)
    if not P or x < xs[0] or x > xs[-1]: return None
    return [float(np.interp(x, xs, [p[2][k] for p in P])) for k in range(3)]
def at(armk, b):
    best = None
    for k, pts in armk.items():
        v = at1(pts, b)
        if v is not None and (best is None or np.mean(v) > np.mean(best[0])): best = (v, k)
    return best
cells = {}
for f in sorted(glob.glob(D + '/*.json')):
    j = json.load(open(f)); cells.setdefault(j['tag'], {}).update(j['arms'])
order = ['gfx_f0', 'gfx_f5', 'dng720_f0', 'dng720_f5', 'dng1080_f0', 'dng1080_f5', 'city_f0', 'city_f5', 'spot_f0', 'spot_f5']
tags = [t for t in order if t in cells and 'base' in cells[t]]
print('cells:', ', '.join(tags))
print('\nBASELINE absolute PSNR Y/Cb/Cr at 0.5 | 1.0 | 2.0 bpp (k chosen):')
for t in tags:
    s = []
    for b in T:
        v = at(cells[t]['base'], b); s.append('n/a' if v is None else '%s (k%s)' % ('/'.join('%.2f' % x for x in v[0]), v[1]))
    print('  %-11s ' % t + ' | '.join(s))
arms = []
for t in tags:
    for a in cells[t]:
        if a not in arms: arms.append(a)
def deltas(a, t, b):
    if a not in cells[t]: return None
    x = at(cells[t][a], b); r = at(cells[t]['base'], b)
    if x is None or r is None: return None
    return [x[0][k] - r[0][k] for k in range(3)]
print('\nDELTA vs baseline, dB Y/Cb/Cr: mean over cells / worst cell (n = cells with the rate inside both sweeps)')
for a in arms:
    if a == 'base': continue
    s = '  %-16s' % a
    for b in T:
        ds = [d for d in (deltas(a, t, b) for t in tags) if d is not None]
        if not ds: s += ' | %.1f n/a' % b; continue
        m = np.mean(ds, 0); w = np.min(ds, 0)
        s += ' | %.1f: %+.2f/%+.2f/%+.2f worst %+.2f/%+.2f/%+.2f n=%d' % (b, m[0], m[1], m[2], w[0], w[1], w[2], len(ds))
    oor = max(max(p[3] for pts in cells[t][a].values() for p in pts) for t in tags if a in cells[t])
    s += ' | max out-of-range %d' % oor
    print(s)
print('\nPER CELL deltas (Y/Cb/Cr at 0.5 | 1.0 | 2.0):')
for t in tags:
    for a in arms:
        if a == 'base' or a not in cells[t]: continue
        s = []
        for b in T:
            d = deltas(a, t, b); s.append('n/a' if d is None else '/'.join('%+.2f' % x for x in d))
        print('  %-11s %-16s %s' % (t, a, ' | '.join(s)))
    print('  %-11s base max out-of-range over the sweep: %d' % (t, max(p[3] for pts in cells[t]['base'].values() for p in pts)))
