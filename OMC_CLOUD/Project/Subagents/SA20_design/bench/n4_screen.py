#!/usr/bin/env python3
# n4_screen.py — PROXY screen (entropy): SA20's N4 = private-last-write interpolating pyramid (form i) whose
# ENCODER aims the samples that later serve as prediction sources at a low-passed target at their own scale
# (anti-aliasing by an encoder-only choice; decoder, syntax, legality and exactness unchanged: every sample is still
# written once as clip(pred(final) + leaf) and read back as y - pred(final)).
# Target of a sample first coded at grid level l: MIX: blur_l(x) where |x - blur_l(x)| <= T * s_l (its detail would
# die in the dead zone anyway), else raw x. blur_l = l passes of separable [1,2,1]/4 at stride 2^(l-1) (a-trous).
# Arms: PO (T = 0: raw targets = plain predict-only) and N4 (T in {1, 2, inf}), each best of ladders f in {0.5,0.7,1};
# reference W53 (integer 5/3). Intra frame 0, all planes, zeroth-order entropy + 1-bit context per band class.
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from d1_screen import ent, dz, read, w53, gains
import d1_screen
LO, HI = 0, 1023
path, W, H = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])

def dd4(a, b, c, d): return (-a + 9 * b + 9 * c - d + 8) >> 4
def pred_axis(k, n_odd, axis):
    k = np.moveaxis(k, axis, 0); m = k.shape[0]; idx = np.arange(n_odd); g = lambda i: k[np.clip(i, 0, m - 1)]
    return np.moveaxis(dd4(g(idx - 1), g(idx), g(idx + 1), g(idx + 2)), 0, axis)
def blur(x, l):
    y = x.astype(float)
    for i in range(l):
        st = 2 ** i
        for ax in (0, 1):
            y = (np.roll(y, st, ax) + 2 * y + np.roll(y, -st, ax)) / 4  # wrap at edges: screen only
    return np.round(y).astype(np.int64)

def po(x, Q, f, T):
    grids = []; s = x.shape
    for _ in range(2): grids.append(('2d', s)); s = ((s[0] + 1) // 2, (s[1] + 1) // 2)
    for _ in range(3): grids.append(('h', s)); s = (s[0], (s[1] + 1) // 2)
    L = len(grids)
    def strides(l):
        r = c = 1
        for k, _ in grids[:l]:
            if k == '2d': r *= 2; c *= 2
            else: c *= 2
        return r, c
    def target(l):  # full-res target map for samples first coded at grid level l
        if T == 0 or l == 0: return x
        bl = blur(x, min(l, 4)); s_l = Q * f ** l
        return bl if T == np.inf else np.where(np.abs(x - bl) <= T * s_l, bl, x)
    tg = {l: target(l) for l in range(L + 1)}
    r, c = strides(L); xk = tg[L][::r, ::c]; sc = Q * f ** L; bits = 0.0
    y = np.zeros_like(xk); qa = np.zeros_like(xk)
    for j in range(xk.shape[1]):
        pr = y[:, j - 1] if j else np.full(xk.shape[0], 512)
        q = dz(xk[:, j] - pr, sc); qa[:, j] = q; y[:, j] = np.clip(pr + np.round(q * sc).astype(np.int64), LO, HI)
    bits += ent(qa); cur = y
    for lvl in range(L - 1, -1, -1):
        kind, shp = grids[lvl]; s_l = Q * f ** lvl; r, c = strides(lvl)
        xg = tg[lvl][::r, ::c][:shp[0], :shp[1]]; full = np.zeros(shp, np.int64)
        if kind == 'h':
            full[:, 0::2] = cur; pr = pred_axis(cur, shp[1] // 2, 1)
            q = dz(xg[:, 1::2] - pr, s_l); bits += ent(q); full[:, 1::2] = np.clip(pr + np.round(q * s_l).astype(np.int64), LO, HI)
        else:
            full[0::2, 0::2] = cur
            pr = pred_axis(cur, shp[1] // 2, 1); q = dz(xg[0::2, 1::2] - pr, s_l); bits += ent(q)
            full[0::2, 1::2] = np.clip(pr + np.round(q * s_l).astype(np.int64), LO, HI)
            pr = pred_axis(cur, shp[0] // 2, 0); q = dz(xg[1::2, 0::2] - pr, s_l); bits += ent(q)
            full[1::2, 0::2] = np.clip(pr + np.round(q * s_l).astype(np.int64), LO, HI)
            pr = pred_axis(full[1::2, 0::2], shp[1] // 2, 1); q = dz(xg[1::2, 1::2] - pr, s_l); bits += ent(q)
            full[1::2, 1::2] = np.clip(pr + np.round(q * s_l).astype(np.int64), LO, HI)
        cur = full
    return bits, cur

def psnr(a, b): return 10 * np.log10(1023.0 ** 2 / max(((a - b).astype(float) ** 2).mean(), 1e-9))
planes = read(path, W, H, 0)
d1_screen.GAINS = {p.shape: gains(p.shape) for p in planes}
res = {'W53': []}
for Q in [2 ** (e / 2) for e in range(2, 14)]:
    b, outs = w53(planes, Q); res['W53'].append((b / (W * H), [psnr(o, p) for o, p in zip(outs, planes)]))
for name, T in (('PO', 0), ('N4t1', 1), ('N4t2', 2), ('N4inf', np.inf)):
    res[name] = []
    for f in (0.5, 0.7, 1.0):
        for Q in [2 ** (e / 2) for e in range(2, 12)]:
            b = 0; outs = []
            for p in planes:
                bb, y = po(p, Q, f, T); b += bb; outs.append(y)
            res[name].append((b / (W * H), [psnr(o, p) for o, p in zip(outs, planes)]))
            print('%s f=%g Q=%.2f bpp %.3f PSNR %.2f/%.2f/%.2f' % (name, f, Q, res[name][-1][0], *res[name][-1][1]), flush=True)
def at(pts, r, k):
    p = sorted(pts); x = np.log2([a for a, _ in p]); y = np.maximum.accumulate([b[k] for _, b in p]); return float(np.interp(np.log2(r), x, y))
for r in (0.25, 0.5, 1.0):
    a = [at(res['W53'], r, k) for k in range(3)]
    print('@%.2f W53 %.2f/%.2f/%.2f' % (r, *a) + ''.join(' | %s %+.2f/%+.2f/%+.2f' % (n, *[at(res[n], r, k) - a[k] for k in range(3)]) for n in res if n != 'W53'))
