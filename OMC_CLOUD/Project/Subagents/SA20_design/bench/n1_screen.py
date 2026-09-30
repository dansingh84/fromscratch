#!/usr/bin/env python3
# n1_screen.py — PROXY screen (entropy) of SA20P's N1 intra: causal 2-D prediction from FINAL pixels + private
# per-sample leaves (form i), vs integer 5/3 (averaging, W53). Intra frame 0, all planes.
# Blocks B x B in raster order, closed loop. Prediction per block from final pixels only (0 bits):
#   mode chosen from final data: the mode (DC / horizontal / vertical / planar) that best predicts the causal
#   L-template (the 2 rows above / 2 columns left) from the rows/columns beyond it; ties -> planar.
# Residual e = x - P coded by a block-local interpolating (predict-only) pyramid (2-D DD levels to 2x2, then
# DPCM of the 2x2 kept samples from P), leaves quantised with dead zone, out = clip(P + pred + leaf) per sample.
# Symbols pooled per band class over the frame (zeroth order + 1-bit context), step ladder s_l = Q f^l.
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from d1_screen import ent, dz, read, w53, gains
import d1_screen
LO, HI, MID = 0, 1023, 512
path, W, H = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]); B = int(os.environ.get('B', 8))

def dd(k):  # predict midpoints of a 1-D kept vector (edge replicate), 4-tap DD
    n = k.shape[-1]; g = lambda i: k[..., np.clip(i, 0, n - 1)]; i = np.arange(n - 1)
    return (-g(i - 1) + 9 * g(i) + 9 * g(i + 1) - g(i + 2) + 8) >> 4

def predict(y, by, bx, B, Hh, Ww):
    top = y[by - 1, bx:bx + B] if by else None; left = y[by:by + B, bx - 1] if bx else None
    if top is None and left is None: return np.full((B, B), MID, np.int64)
    if top is None: return np.repeat(left[:, None], B, 1)
    if left is None: return np.repeat(top[None, :], B, 0)
    tl = y[by - 1, bx - 1]
    cand = {}
    cand['dc'] = np.full((B, B), (top.sum() + left.sum() + B) // (2 * B), np.int64)
    cand['h'] = np.repeat(left[:, None], B, 1); cand['v'] = np.repeat(top[None, :], B, 0)
    r = np.arange(1, B + 1)[:, None]; c = np.arange(1, B + 1)[None, :]
    cand['pl'] = ((B - c) * left[:, None] + c * top[-1] + (B - r) * top[None, :] + r * left[-1] + B) // (2 * B)
    # mode from final data: predict the row above (from row by-2) and column left (from col bx-2)
    if by >= 2 and bx >= 2:
        t2 = y[by - 2, bx:bx + B]; l2 = y[by:by + B, bx - 2]
        err = {'dc': np.abs(top - (t2.sum() + l2.sum()) // (2 * B)).sum() + np.abs(left - (t2.sum() + l2.sum()) // (2 * B)).sum(),
               'h': np.abs(left - l2).sum() * 2, 'v': np.abs(top - t2).sum() * 2,
               'pl': np.abs(top - t2).sum() + np.abs(left - l2).sum()}
        m = min(err, key=lambda k: (err[k], k != 'pl'))
    else: m = 'pl'
    return cand[m]

def n1(x, Q, f, SYM):
    Hh, Ww = x.shape; y = np.zeros_like(x)
    for by in range(0, Hh, B):
        for bx in range(0, Ww, B):
            xb = x[by:by + B, bx:bx + B]; P = predict(y, by, bx, B, Hh, Ww)[:xb.shape[0], :xb.shape[1]]
            # levels: stride s = B/2 ... 1 ; kept grid at stride B/2 coded by DPCM-from-P, then refine
            full = np.zeros_like(xb); s = B // 2; lv = int(np.log2(B))
            kp = xb[::s, ::s]; Pk = P[::s, ::s]; sq = Q * f ** lv
            q = dz(kp - Pk, sq); SYM.setdefault(('k',), []).append(q.ravel())
            full[::s, ::s] = np.clip(Pk + np.round(q * sq).astype(np.int64), LO, HI)
            while s > 1:
                h = s // 2; lv -= 1; sl = Q * f ** lv
                e = full - P
                # horizontal midpoints on kept rows
                kr = e[::s, ::s]; pm = dd(kr)
                if pm.shape[1] < xb[::s, h::s].shape[1]: pm = np.concatenate([pm, kr[:, -1:]], 1)
                pr = P[::s, h::s] + pm[:, :xb[::s, h::s].shape[1]]
                q = dz(xb[::s, h::s] - pr, sl); SYM.setdefault(('b', lv), []).append(q.ravel())
                full[::s, h::s] = np.clip(pr + np.round(q * sl).astype(np.int64), LO, HI)
                # vertical midpoints on all columns at stride h
                e = full - P; kc = e[::s, ::h].T; pm = dd(kc).T
                if pm.shape[0] < xb[h::s, ::h].shape[0]: pm = np.concatenate([pm, kc.T[-1:]], 0)
                pr = P[h::s, ::h] + pm[:xb[h::s, ::h].shape[0]]
                q = dz(xb[h::s, ::h] - pr, sl); SYM.setdefault(('c', lv), []).append(q.ravel())
                full[h::s, ::h] = np.clip(pr + np.round(q * sl).astype(np.int64), LO, HI)
                s = h
            y[by:by + B, bx:bx + B] = full
    return y

def ent1(v):
    _, n = np.unique(v, return_counts=True); p = n / v.size; return -(n * np.log2(p)).sum()
def psnr(a, b): return 10 * np.log10(1023.0 ** 2 / max(((a - b).astype(float) ** 2).mean(), 1e-9))
planes = read(path, W, H, 0)
d1_screen.GAINS = {p.shape: gains(p.shape) for p in planes}
res = {'W53': [], 'N1': []}
for Q in [2 ** (e / 2) for e in range(2, 14)]:
    b, outs = w53(planes, Q); res['W53'].append((b / (W * H), [psnr(o, p) for o, p in zip(outs, planes)]))
for f in (0.5, 0.7, 1.0):
    for Q in [2 ** (e / 2) for e in range(1, 12)]:
        bits = 0.0; outs = []
        for p in planes:
            SYM = {}; y = n1(p, Q, f, SYM); outs.append(y)
            bits += sum(ent1(np.concatenate(v)) for v in SYM.values())
        res['N1'].append((bits / (W * H), [psnr(o, p) for o, p in zip(outs, planes)]))
        print('N1 B=%d f=%g Q=%.2f bpp %.3f PSNR %.2f/%.2f/%.2f' % (B, f, Q, res['N1'][-1][0], *res['N1'][-1][1]), flush=True)
def at(pts, r, k):
    p = sorted(pts); x = np.log2([a for a, _ in p]); y = np.maximum.accumulate([b[k] for _, b in p]); return float(np.interp(np.log2(r), x, y))
for r in (0.25, 0.5, 1.0):
    a = [at(res['W53'], r, k) for k in range(3)]; d = [at(res['N1'], r, k) for k in range(3)]
    print('@%.2f W53 %.2f/%.2f/%.2f | N1-W53 %+.2f/%+.2f/%+.2f' % (r, *a, *[d[k] - a[k] for k in range(3)]))
