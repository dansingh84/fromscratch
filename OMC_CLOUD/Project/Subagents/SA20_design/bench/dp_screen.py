#!/usr/bin/env python3
# dp_screen.py — PROXY screen (entropy, not real code lengths) of SA20P's D-P vs an averaging reference.
# 3 frames of a 4:2:2 10-bit clip: frame 0 intra (cut/ramp), frames 1-2 inter from the arm's OWN reconstruction.
# Both arms: same motion (16x16 luma blocks, +-8 full-pel search of source vs the arm's previous reconstruction,
# chroma vector x halved), vector bits not counted (same for both), fixed step Q for all frames (no rate control).
#  AVG : value-domain; intra = integer 5/3 (2 levels 2-D + 3 horizontal), inter = the same transform of x - P;
#        dead zone 0.35, gain-normalised steps; out = clip(P + e^).   (averaging reference; NOT never-away)
#  DP  : D-P = predict-only coding of e = x - P (P = 0 on intra): non-separable interpolating pyramid on
#        pixel-valued samples, closed loop, every sample written once = clip(P + pred(final) + leaf):
#        never-away and exact by construction. Kept A(ee); B(eo) from horizontal A (DD 4-tap), C(oe) vertical A,
#        D(oo) horizontal C (all FINAL values); 2 such levels, then 3 horizontal 1-D levels; coarsest grid DPCM.
#        Level step ladder s_l = Q * f^(L - l) (f swept: best f per point = favourable to DP).
# Writes decodes out/dp/<tag>_<arm>_<Q>.yuv, prints bits per frame (bpp over all planes / luma samples) + PSNR.
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from d1_screen import l53f, l53i, fwd, inv, ent, dz, gains, read
LO, HI = 0, 1023
path, W, H, tag = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
OUT = os.path.join(os.path.dirname(__file__), '..', 'out', 'dp'); os.makedirs(OUT, exist_ok=True)

def dd4(a, b, c, d): return (-a + 9 * b + 9 * c - d + 8) >> 4
def pred_axis(k, n_odd, axis):  # predict odd positions from kept k along axis (DD 4-tap, edge replicate)
    k = np.moveaxis(k, axis, 0); m = k.shape[0]
    idx = np.arange(n_odd)
    g = lambda i: k[np.clip(i, 0, m - 1)]
    return np.moveaxis(dd4(g(idx - 1), g(idx), g(idx + 1), g(idx + 2)), 0, axis)

def po_code(x, P, Q, f):
    """closed-loop predict-only coding of plane x with prediction P; returns bits, recon y (legal)."""
    H_, W_ = x.shape; bits = 0.0
    # level geometry: 2 non-separable 2-D levels then 3 horizontal levels on the kept grid
    grids = []  # list of (kind, shape of the full grid at this level)
    s = (H_, W_)
    for _ in range(2): grids.append(('2d', s)); s = ((s[0] + 1) // 2, (s[1] + 1) // 2)
    for _ in range(3): grids.append(('h', s)); s = (s[0], (s[1] + 1) // 2)
    L = len(grids)
    # subsample maps from coarse grid to pixel positions
    def sub(a, lvl):  # positions of the kept grid of level lvl (0 = full res)
        r, c = 1, 1
        for kind, _ in grids[:lvl]:
            if kind == '2d': r *= 2; c *= 2
            else: c *= 2
        return a[::r, ::c]
    Pk = sub(P, L); xk = sub(x, L); sc = Q * f ** L
    # coarsest: DPCM along rows from the left final sample (column 0 from mid-grey), closed loop
    y = np.zeros_like(xk); q_all = np.zeros_like(xk)
    for j in range(xk.shape[1]):

        pr = Pk[:, j] + ((y[:, j - 1] - Pk[:, j - 1]) if j else (512 - Pk[:, j]) * 0)
        q = dz(xk[:, j] - pr, sc); q_all[:, j] = q; y[:, j] = np.clip(pr + np.round(q * sc).astype(np.int64), LO, HI)
    bits += ent(q_all)
    cur = y
    for lvl in range(L - 1, -1, -1):
        kind, shp = grids[lvl]; s_l = Q * f ** lvl
        xg = sub(x, lvl)[:shp[0], :shp[1]]; Pg = sub(P, lvl)[:shp[0], :shp[1]]
        full = np.zeros(shp, np.int64)
        e_k = cur - sub(P, lvl + 1)[:cur.shape[0], :cur.shape[1]]   # final kept residual values
        if kind == 'h':
            full[:, 0::2] = cur
            no = shp[1] // 2
            pe = pred_axis(e_k, no, 1)
            pr = Pg[:, 1::2] + pe
            q = dz(xg[:, 1::2] - pr, s_l); bits += ent(q)
            full[:, 1::2] = np.clip(pr + np.round(q * s_l).astype(np.int64), LO, HI)
        else:
            full[0::2, 0::2] = cur
            # B: even rows, odd cols from horizontal kept
            pe = pred_axis(e_k, shp[1] // 2, 1); pr = Pg[0::2, 1::2] + pe
            q = dz(xg[0::2, 1::2] - pr, s_l); bits += ent(q)
            full[0::2, 1::2] = np.clip(pr + np.round(q * s_l).astype(np.int64), LO, HI)
            # C: odd rows, even cols from vertical kept
            pe = pred_axis(e_k, shp[0] // 2, 0); pr = Pg[1::2, 0::2] + pe
            q = dz(xg[1::2, 0::2] - pr, s_l); bits += ent(q)
            full[1::2, 0::2] = np.clip(pr + np.round(q * s_l).astype(np.int64), LO, HI)
            # D: odd/odd from horizontal FINAL C
            eC = full[1::2, 0::2] - Pg[1::2, 0::2]
            pe = pred_axis(eC, shp[1] // 2, 1); pr = Pg[1::2, 1::2] + pe
            q = dz(xg[1::2, 1::2] - pr, s_l); bits += ent(q)
            full[1::2, 1::2] = np.clip(pr + np.round(q * s_l).astype(np.int64), LO, HI)
        cur = full
    return bits, cur

GAINS = {}
def w53_code(x, P, Q):
    if x.shape not in GAINS: GAINS[x.shape] = gains(x.shape)
    ga, gb = GAINS[x.shape]; a, b = fwd(x - P); bits = 0.0
    sa = max(1.0, Q / np.sqrt(ga)); qa = np.round(a / sa); bits += ent(qa); nb = []
    for (k, bb), gg in zip(b, gb):
        m = []
        for c, g in zip(bb, gg):
            s = max(1.0, Q / np.sqrt(g)); qc = dz(c, s); bits += ent(qc); m.append(np.round(qc * s).astype(np.int64))
        nb.append((k, m))
    return bits, np.clip(P + inv(np.round(qa * sa).astype(np.int64), nb), LO, HI)

def motion(src, ref, B=16, R=8):
    Hh, Ww = src.shape; V = np.zeros((Hh // B + 1, Ww // B + 1, 2), int); P = np.zeros_like(ref)
    pad = np.pad(ref, R, mode='edge')
    for by in range(0, Hh, B):
        for bx in range(0, Ww, B):
            blk = src[by:by + B, bx:bx + B]; best = None
            for dy in range(-R, R + 1, 2):
                for dx in range(-R, R + 1, 2):
                    c = pad[by + R + dy:by + R + dy + blk.shape[0], bx + R + dx:bx + R + dx + blk.shape[1]]
                    sad = np.abs(blk - c).sum()
                    if best is None or sad < best[0]: best = (sad, dy, dx)
            _, dy0, dx0 = best
            for dy in (dy0 - 1, dy0, dy0 + 1):
                for dx in (dx0 - 1, dx0, dx0 + 1):
                    if abs(dy) > R or abs(dx) > R: continue
                    c = pad[by + R + dy:by + R + dy + blk.shape[0], bx + R + dx:bx + R + dx + blk.shape[1]]
                    sad = np.abs(blk - c).sum()
                    if sad < best[0]: best = (sad, dy, dx)
            V[by // B, bx // B] = best[1:]
    return V
def apply(ref, V, B, sx):
    Hh, Ww = ref.shape; R = 8; pad = np.pad(ref, R, mode='edge'); P = np.zeros_like(ref); Bx = B // sx
    for i in range(V.shape[0]):
        for j in range(V.shape[1]):
            by, bx = i * B, j * Bx
            if by >= Hh or bx >= Ww: continue
            dy, dx = V[i, j]; dx = int(np.round(dx / sx))
            h = min(B, Hh - by); w = min(Bx, Ww - bx)
            P[by:by + h, bx:bx + w] = pad[by + R + dy:by + R + dy + h, bx + R + dx:bx + R + dx + w]
    return P

def psnr(a, b): return 10 * np.log10(1023.0 ** 2 / max(((a - b).astype(float) ** 2).mean(), 1e-9))
frames = [read(path, W, H, f) for f in range(3)]
ARMS = os.environ.get('ARMS', 'AVG,DP').split(',')
for arm, Qs, fs in [a for a in (('AVG', [2 ** (e / 2) for e in range(4, 14)], [None]),
                    ('DP', [2 ** (e / 2) for e in range(2, 12)], [0.5, 0.7, 1.0]),
                    ('DPI', [2 ** (e / 2) for e in range(2, 12)], [0.5, 0.7, 1.0])) if a[0] in ARMS]:
    for f_ in fs:
        for Q in Qs:
            rec = []; bits = []
            for t, x in enumerate(frames):
                if t == 0: Ps = [np.zeros_like(p) for p in x]
                else:
                    V = motion(x[0], rec[-1][0]); Ps = [apply(rec[-1][0], V, 16, 1), apply(rec[-1][1], V, 16, 2), apply(rec[-1][2], V, 16, 2)]
                out = []; b = 0.0
                for p, Pp in zip(x, Ps):
                    if arm == 'AVG' or (arm == 'DPI' and t == 0): bb, y = w53_code(p, Pp, Q * (1.6 if arm == 'DPI' else 1))
                    else: bb, y = po_code(p, Pp, Q, f_)
                    b += bb; out.append(y)
                rec.append(out); bits.append(b / (W * H))
            name = '%s_%s%s_%.2f' % (tag, arm, '' if f_ is None else 'f%g' % f_, Q)
            fn = os.path.join(OUT, name + '.yuv')
            with open(fn, 'wb') as fo:
                for fr in rec:
                    for p in fr: p.astype('<u2').tofile(fo)
            ps = [psnr(a, b_) for a, b_ in zip(rec[2], frames[2])]
            print('%s bpp f0/f1/f2 %.3f/%.3f/%.3f mean %.3f | f2 PSNR %.2f/%.2f/%.2f | %s' % (name, *bits, np.mean(bits), *ps, fn), flush=True)
