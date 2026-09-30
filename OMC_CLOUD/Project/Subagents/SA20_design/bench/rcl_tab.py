#!/usr/bin/env python3
# rcl_tab.py CLIP — table-count screen. Today ships 60 static tANS tables (L 1024, 1.1 Mbit); a 720-table set
# (26.5 Mbit) was ruled not implementable. Our real-code figures so far used one table set PER quarter-octave step.
# Here: intra frame 0, cm1, form-(i) PO; histograms per step Q from the held-out training clips; test-clip cost when
# tables are POOLED over step buckets of width B quarter-octaves (B = 1 per-Q, 4 = octave, 8, 16, all), for the base
# model (1-bit neighbour context) and the activity model (neighbour bit x 5 activity classes).
# Prints bpp per Q per scheme, and the table count per scheme (tables = keys x contexts x buckets actually used).
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from d1_screen import read
from n4_core import po
W, H = 1280, 720
A = '/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/'
TRAIN = [('cine_4k_A006', 2), ('cine_A005C021', 2), ('gfx444_F003C012', 3)]
TEST = sys.argv[1]; ES = list(range(-2, 25)); TH = np.array([0.5, 1.5, 4.0, 10.0])
def nzc(q):
    nz = q != 0; c = np.zeros_like(nz); c[:, 1:] |= nz[:, :-1]; c[1:, :] |= nz[:-1, :]; return c.astype(int)
def ctxs(q, a, rich): return nzc(q) * 5 + np.searchsorted(TH, a[:q.shape[0], :q.shape[1]]) if rich else nzc(q)
def syms(planes, Q):
    out = []
    for pl, p in enumerate(planes):
        SY = []; AC = []; po(p, Q, 0.7, 0, SY, ACT=AC); out.append((min(pl, 1), SY, AC))
    return out
def hist(S, rich, tab):
    for pl, SY, AC in S:
        for (key, q), a in zip(SY, AC):
            c = ctxs(q, a, rich); v = np.clip(q.astype(np.int64), -64, 64) + 64
            for cc in np.unique(c): np.add.at(tab.setdefault((pl,) + key + (cc,), np.zeros(129)), v[c == cc], 1)
def cost(S, rich, tab):
    b = 0.0
    for pl, SY, AC in S:
        for (key, q), a in zip(SY, AC):
            c = ctxs(q, a, rich); q = q.astype(np.int64)
            for cc in np.unique(c):
                v = q[c == cc]; h = tab.get((pl,) + key + (cc,), np.zeros(129)) + 1; p = h / h.sum()
                b += -np.log2(p[np.clip(v, -64, 64) + 64]).sum() + (12 + 2 * np.log2(np.abs(v[np.abs(v) > 63]))).sum()
    return b
TR = [read(A + c + '_1280x720_422_10.yuv', W, H, f) for c, nf in TRAIN for f in range(nf)]
X = read(A + TEST + '_1280x720_422_10.yuv', W, H, 0)
HQ = {}
for e in ES:
    Q = 2 ** (e / 4); HQ[e] = ({}, {})
    for fr in TR:
        S = syms(fr, Q)
        for r in (0, 1): hist(S, r, HQ[e][r])
def pooled(e, B, r):
    b0 = (e - ES[0]) // B; t = {}
    for e2 in ES:
        if (e2 - ES[0]) // B == b0:
            for k, h in HQ[e2][r].items(): t[k] = t.get(k, 0) + h
    return t
BS = (1, 4, 8, 16, 99)
for r, nm in ((0, 'base'), (1, 'ctx')):
    nkeys = len(set(k for e in ES for k in HQ[e][r]))
    print('%s: tables per bucket %d; buckets over the %d steps: %s' % (nm, nkeys, len(ES), ' '.join('B%d=%d' % (B, -(-len(ES) // B)) for B in BS)), flush=True)
for e in ES:
    Q = 2 ** (e / 4); S = syms(X, Q)
    row = []
    for r in (0, 1):
        for B in BS: row.append(cost(S, r, pooled(e, B, r)) / (W * H))
    print('%s Q=%.3f base %s | ctx %s' % (TEST, Q, ' '.join('%.4f' % v for v in row[:5]), ' '.join('%.4f' % v for v in row[5:])), flush=True)
