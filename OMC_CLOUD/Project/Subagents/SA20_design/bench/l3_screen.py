#!/usr/bin/env python3
# l3_screen.py — PROXY screen (entropy) of SA20Q's order-statistic ("inner") pair pyramid vs integer 5/3, intra f0.
# Pair step (horizontal then vertical, 2 levels 2-D + 3 horizontal): c = the pair member nearer mid-code (the
# "inner"), o = the other; coded: c (to the coarser level), d = o - c (leaf), pos = which member is inner (1 bit,
# entropy-coded; counted everywhere = pessimistic only by the ambiguous-free share). Closed loop coarse -> fine:
# o^ = clip(c^ + q*s), c^ from the coarser level (clipped there). Per-sample private last write, never-away.
# Coarsest band: DPCM from the left final value. Steps: s_l = Q * f^(L-l), best f of {0.5, 0.7, 1.0}.
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from d1_screen import ent, dz, read, w53, gains
import d1_screen
LO, HI, MID = 0, 1023, 512
path, W, H = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])

def split(x, axis):
    x = np.moveaxis(x, axis, 0); n = x.shape[0] // 2 * 2
    a, b = x[0:n:2], x[1:n:2]
    ain = np.abs(a - MID) <= np.abs(b - MID)
    c = np.where(ain, a, b); o = np.where(ain, b, a)
    return np.moveaxis(c, 0, axis), np.moveaxis(o, 0, axis), np.moveaxis(ain, 0, axis)
def merge(c, o, ain, axis):
    c = np.moveaxis(c, axis, 0); o = np.moveaxis(o, axis, 0); ain = np.moveaxis(ain, axis, 0)
    x = np.empty((2 * c.shape[0],) + c.shape[1:], np.int64)
    x[0::2] = np.where(ain, c, o); x[1::2] = np.where(ain, o, c)
    return np.moveaxis(x, 0, axis)

def l3(x, Q, f):
    steps = []  # analysis, fine -> coarse; each 1-D split records (axis, o, ain)
    c = x
    for _ in range(2):
        for ax in (1, 0):
            c, o, ain = split(c, ax); steps.append((ax, o, ain))
    for _ in range(3):
        c, o, ain = split(c, 1); steps.append((1, o, ain))
    L = len(steps); bits = 0.0
    # coarsest: DPCM from left final, closed loop
    s0 = Q * f ** L; y = np.zeros_like(c); qa = np.zeros_like(c)
    for j in range(c.shape[1]):
        pr = y[:, j - 1] if j else np.full(c.shape[0], MID)
        q = dz(c[:, j] - pr, s0); qa[:, j] = q; y[:, j] = np.clip(pr + np.round(q * s0).astype(np.int64), LO, HI)
    bits += ent(qa)
    for lvl in range(L - 1, -1, -1):
        ax, o, ain = steps[lvl]; s = Q * f ** lvl
        q = dz(o - y, s); bits += ent(q) + ent(ain.astype(np.int64))
        oh = np.clip(y + np.round(q * s).astype(np.int64), LO, HI)
        y = merge(y, oh, ain, ax)
    return bits, y

def psnr(a, b): return 10 * np.log10(1023.0 ** 2 / max(((a - b).astype(float) ** 2).mean(), 1e-9))
planes = read(path, W, H, 0)
d1_screen.GAINS = {p.shape: gains(p.shape) for p in planes}
res = {'W53': [], 'L3': []}
for Q in [2 ** (e / 2) for e in range(2, 14)]:
    b, outs = w53(planes, Q); res['W53'].append((b / (W * H), [psnr(o, p) for o, p in zip(outs, planes)]))
for f in (0.5, 0.7, 1.0):
    for Q in [2 ** (e / 2) for e in range(0, 12)]:
        b = 0; outs = []
        for p in planes:
            bb, y = l3(p, Q, f); b += bb; outs.append(y)
        res['L3'].append((b / (W * H), [psnr(o, p) for o, p in zip(outs, planes)]))
        cast = [float((o - p).mean()) for o, p in zip(outs, planes)]
        print('L3 f=%g Q=%.2f bpp %.3f PSNR %.2f/%.2f/%.2f cast %+.2f/%+.2f/%+.2f' % (f, Q, res['L3'][-1][0], *res['L3'][-1][1], *cast), flush=True)
def at(pts, r, k):
    p = sorted(pts); x = np.log2([a for a, _ in p]); y = np.maximum.accumulate([b[k] for _, b in p]); return float(np.interp(np.log2(r), x, y))
for r in (0.25, 0.5, 1.0):
    a = [at(res['W53'], r, k) for k in range(3)]; d = [at(res['L3'], r, k) for k in range(3)]
    print('@%.2f W53 %.2f/%.2f/%.2f | L3-W53 %+.2f/%+.2f/%+.2f' % (r, *a, *[d[k] - a[k] for k in range(3)]))
