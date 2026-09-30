# n4_core.py: N4/PO coder returning symbol arrays (from n4_screen.py)
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


def alpha_map(ck, yk, shp, BS):
    """per BSxBS block (in the grid of the kept samples): slope of chroma vs luma deviations, from FINAL kept data,
    quantised to eighths in [-1, 1] (shift-add); returns an alpha value per grid sample of shape shp."""
    a = np.zeros(shp)
    for i in range(0, ck.shape[0], BS):
        for j in range(0, ck.shape[1], BS):
            c = ck[i:i+BS, j:j+BS].astype(float); y = yk[i:i+BS, j:j+BS].astype(float)
            c = c - c.mean(); y = y - y.mean(); v = (y * y).sum()
            al = 0.0 if v < 1e-6 else np.clip(np.round(8 * (c * y).sum() / v) / 8, -1, 1)
            a[2*i:2*i+2*BS, 2*j:2*j+2*BS] = al
    return a

def po(x, Q, f, T, SY, Yd=None, BS=16, P=None, ACT=None):
    # ACT (optional list): per symbol array, the decoder-side activity of its prediction support / step (final data only)
    if P is None: P = np.zeros_like(x)
    x = x - P   # residual domain; every clip is done in the PIXEL domain: clip(P + v) - P
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
    r, c = strides(L); xk = tg[L][::r, ::c]; Pk = P[::r, ::c]; sc = Q * f ** L; bits = 0.0
    y = np.zeros_like(xk); qa = np.zeros_like(xk)
    for j in range(xk.shape[1]):
        pr = y[:, j - 1] if j else np.full(xk.shape[0], 512)
        q = dz(xk[:, j] - pr, sc); qa[:, j] = q; y[:, j] = np.clip(Pk[:, j] + pr + np.round(q * sc).astype(np.int64), LO, HI) - Pk[:, j]
    SY.append((('c', L), qa)); cur = y
    def ad(a, b, s_): return np.abs(a - b) / s_
    if ACT is not None:
        a = np.zeros(y.shape); a[:, 2:] = ad(y[:, 1:-1], y[:, :-2], sc); ACT.append(a)
    def sup(k, n, axis, s_):   # |difference of the two inner taps| of the DD4 support along axis
        k = np.moveaxis(k, axis, 0); m = k.shape[0]; i = np.arange(n); g = lambda t: k[np.clip(t, 0, m - 1)]
        return np.moveaxis(ad(g(i + 1), g(i), s_), 0, axis)
    for lvl in range(L - 1, -1, -1):
        kind, shp = grids[lvl]; s_l = Q * f ** lvl; r, c = strides(lvl)
        xg = tg[lvl][::r, ::c][:shp[0], :shp[1]]; full = np.zeros(shp, np.int64); Pg = P[::r, ::c][:shp[0], :shp[1]]
        if Yd is not None:
            yg = Yd[::r, ::c][:shp[0], :shp[1]]
            AL = alpha_map(cur, yg[0::2, 0::2] if kind == '2d' else yg[:, 0::2], shp, BS)
            def lt(sl, pd): return np.round(AL[sl] * (yg[sl] - pd)).astype(np.int64)
        else:
            yg = np.zeros(shp, np.int64)
            def lt(sl, pd): return 0
        if kind == 'h':
            full[:, 0::2] = cur; pr = pred_axis(cur, shp[1] // 2, 1)
            if Yd is not None: pr = pr + lt((slice(None), slice(1, None, 2)), pred_axis(yg[:, 0::2], shp[1] // 2, 1))
            q = dz(xg[:, 1::2] - pr, s_l); SY.append(((kind, lvl), q)); ACT is None or ACT.append(sup(cur, shp[1] // 2, 1, s_l)); full[:, 1::2] = np.clip(Pg[:, 1::2] + pr + np.round(q * s_l).astype(np.int64), LO, HI) - Pg[:, 1::2]
        else:
            full[0::2, 0::2] = cur
            pr = pred_axis(cur, shp[1] // 2, 1); pr = pr + lt((slice(0, None, 2), slice(1, None, 2)), pred_axis(yg[0::2, 0::2], shp[1] // 2, 1)); q = dz(xg[0::2, 1::2] - pr, s_l); SY.append(((kind, lvl), q)); ACT is None or ACT.append(sup(cur, shp[1] // 2, 1, s_l))
            full[0::2, 1::2] = np.clip(Pg[0::2, 1::2] + pr + np.round(q * s_l).astype(np.int64), LO, HI) - Pg[0::2, 1::2]
            pr = pred_axis(cur, shp[0] // 2, 0); pr = pr + lt((slice(1, None, 2), slice(0, None, 2)), pred_axis(yg[0::2, 0::2], shp[0] // 2, 0)); q = dz(xg[1::2, 0::2] - pr, s_l); SY.append(((kind, lvl), q)); ACT is None or ACT.append(sup(cur, shp[0] // 2, 0, s_l))
            full[1::2, 0::2] = np.clip(Pg[1::2, 0::2] + pr + np.round(q * s_l).astype(np.int64), LO, HI) - Pg[1::2, 0::2]
            pr = pred_axis(full[1::2, 0::2], shp[1] // 2, 1); pr = pr + lt((slice(1, None, 2), slice(1, None, 2)), pred_axis(yg[1::2, 0::2], shp[1] // 2, 1)); q = dz(xg[1::2, 1::2] - pr, s_l); SY.append(((kind, lvl), q)); ACT is None or ACT.append(sup(full[1::2, 0::2], shp[1] // 2, 1, s_l))
            full[1::2, 1::2] = np.clip(Pg[1::2, 1::2] + pr + np.round(q * s_l).astype(np.int64), LO, HI) - Pg[1::2, 1::2]
        cur = full
    return bits, cur + P

