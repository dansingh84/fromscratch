#!/usr/bin/env python3
"""Round-6 oracle (float, no legality): does starting each slice on a PREDICTED row remove the intra slice-boundary step?
Separable 5/3 lifting, per 16/8-row slice, sequential closed loop (context = previous slice's DECODED rows at each level).
 phase 'std'  : level rows split even/odd from row 0 (row 0 = low); predict of the last odd row one-sided (extrapolated);
                update of the first low row reads the previous slice's last detail at that level (causal context).
 phase 'shift': row 0 = PREDICTED (odd) from the previous slice's final low row (context) and row 1; update of the LAST
                low row one-sided (its lower detail belongs to the next slice).
Levels: V1,H1,V2,H2,V3,H3,H4,H5 (3 vertical, 5 horizontal).  Dead-zone quantiser (9/16), steps from synthesis weights,
zeroth-order entropy per band.  Reports per plane: bpp, PSNR, boundary excess (step at slice boundary minus step at
half-slice, rel. to other rows).  usage: phase.py path W H frame sh Qf"""
import sys, math, numpy as np
path, W, H, fr, sh, Qf = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), float(sys.argv[6])
def load():
    fs = W * H * 2; d = np.fromfile(path, dtype='<u2', count=fs, offset=fr * fs * 2).astype(float)
    return [d[:W * H].reshape(H, W), d[W * H:W * H + W * H // 2].reshape(H, W // 2), d[W * H + W * H // 2:].reshape(H, W // 2)]
def h53f(x):   # horizontal 5/3 on last axis, symmetric ext
    e, o = x[..., 0::2].copy(), x[..., 1::2].copy()
    er = np.concatenate([e[..., 1:], e[..., -1:]], -1); o -= (e + er) / 2
    ol = np.concatenate([o[..., :1], o[..., :-1]], -1); e += (ol + o) / 4
    return e, o
def h53i(e, o):
    ol = np.concatenate([o[..., :1], o[..., :-1]], -1); e = e - (ol + o) / 4
    er = np.concatenate([e[..., 1:], e[..., -1:]], -1); o = o + (e + er) / 2
    x = np.empty(e.shape[:-1] + (2 * e.shape[-1],)); x[..., 0::2] = e; x[..., 1::2] = o; return x
def v53f(x, ctx, phase):
    """x (n, w) rows of this level; ctx = dict(low=row, det=row) from the previous slice at this level (or None)."""
    n = x.shape[0]
    if phase == 'shift':
        o, e = x[0::2].copy(), x[1::2].copy()             # rows 0,2,.. predicted; 1,3,.. low
        up = np.vstack([ctx['low'][None] if ctx else e[:1], e[:-1]])
        d = o - (up + e) / 2
        dn = np.vstack([d[1:], d[-1:] * 0])                 # last low row: no lower detail (next slice) -> one-sided
        w = np.full((e.shape[0], 1), 0.25); w[-1] = 0.5
        low = e + w * (d + np.where(np.arange(e.shape[0])[:, None] == e.shape[0] - 1, 0, dn))
        return low, d
    e, o = x[0::2].copy(), x[1::2].copy()
    dn_e = np.vstack([e[1:], e[-1:] + (e[-1:] - e[-2:-1] if e.shape[0] > 1 else 0)])   # extrapolate below
    d = o - (e + dn_e) / 2
    up_d = np.vstack([ctx['det'][None] if ctx else d[:1], d[:-1]])
    low = e + (up_d + d) / 4
    return low, d
def v53i(low, d, ctx, phase):
    if phase == 'shift':
        n2 = low.shape[0]; dn = np.vstack([d[1:], d[-1:] * 0]); w = np.full((n2, 1), 0.25); w[-1] = 0.5
        e = low - w * (d + np.where(np.arange(n2)[:, None] == n2 - 1, 0, dn))
        up = np.vstack([ctx['low'][None] if ctx else e[:1], e[:-1]]); o = d + (up + e) / 2
        x = np.empty((2 * n2, low.shape[1])); x[0::2] = o; x[1::2] = e; return x
    up_d = np.vstack([ctx['det'][None] if ctx else d[:1], d[:-1]]); e = low - (up_d + d) / 4
    dn_e = np.vstack([e[1:], e[-1:] + (e[-1:] - e[-2:-1] if e.shape[0] > 1 else 0)]); o = d + (e + dn_e) / 2
    x = np.empty((2 * e.shape[0], low.shape[1])); x[0::2] = e; x[1::2] = o; return x
NV, NH = 3, 5
def fwd(X, ctxs, phase):
    """X slice (sh, w). returns band dict and per-level vertical inputs (for context of the next slice)."""
    bands = {}; A = X; vin = []
    for l in range(NH):
        if l < NV:
            vin.append(A.copy()); low, d = v53f(A, ctxs[l] if ctxs else None, phase)
            Ll, Lh = h53f(low); Dl, Dh = h53f(d)
            bands[(l, 'HL')] = Lh; bands[(l, 'LH')] = Dl; bands[(l, 'HH')] = Dh; A = Ll
        else:
            Ll, Lh = h53f(A); bands[(l, 'H')] = Lh; A = Ll
    bands['LL'] = A; return bands
def inv(bands, ctxs, phase):
    A = bands['LL']
    for l in range(NH - 1, -1, -1):
        if l < NV:
            low = h53i(A, bands[(l, 'HL')]); d = h53i(bands[(l, 'LH')], bands[(l, 'HH')])
            A = v53i(low, d, ctxs[l] if ctxs else None, phase)
        else:
            A = h53i(A, bands[(l, 'H')])
    return A
def ctx_from(rec, phase):
    """context for the next slice from the DECODED previous slice: per level, its last low row and last detail row."""
    out = []; A = rec
    for l in range(NV):
        low, d = v53f(A, None, phase)     # no context needed for the last rows' values here (approximation-free for 'shift': last low one-sided)
        out.append(dict(low=A[-1].copy(), det=d[-1].copy()))   # shift: the raw even row (final decoded row at this level)
        A, _ = h53f(low)
    return out
def weights(w, phase):
    X = np.zeros((sh, w)); b0 = fwd(X, None, phase); out = {}
    for k in b0:
        z = {kk: np.zeros_like(v) for kk, v in b0.items()}; a = z[k]; a[a.shape[0] // 2, a.shape[1] // 2] = 1.0
        out[k] = float((inv(z, None, phase) ** 2).sum())
    return out
def ent(q):
    _, c = np.unique(q, return_counts=True); p = c / c.sum(); return float(-(c * np.log2(p)).sum())
res = {}
import os
DUMP = os.environ.get('PH_DUMP')
for phase in ('std', 'shift'):
    recs_out = []
    line = []; tb = 0
    for pi, P in enumerate(load()):
        Hh, w = P.shape; ns = Hh // sh; wt = weights(w, phase); rec = np.zeros((ns * sh, w)); Qs = {}
        steps = {k: 2.0 ** round(Qf - 0.5 * math.log2(v)) * (0.5 if k == 'LL' else 1) for k, v in wt.items()}
        ctx = None
        for s in range(ns):
            b = fwd(P[s * sh:(s + 1) * sh], ctx, phase)
            bq = {}
            for k, v in b.items():
                D = steps[k]; q = np.sign(v) * np.floor(np.abs(v) / D + 7 / 16); Qs.setdefault(k, []).append(q.ravel()); bq[k] = q * D
            rec[s * sh:(s + 1) * sh] = inv(bq, ctx, phase)
            ctx = ctx_from(rec[s * sh:(s + 1) * sh], phase)
        tb += sum(ent(np.concatenate(v)) for v in Qs.values())
        recs_out.append(np.clip(np.rint(np.vstack([rec, P[ns * sh:]])), 0, 1023))
        e = np.clip(np.rint(rec), 0, 1023) - P[:ns * sh]; dy = np.abs(np.diff(e, axis=0)); ys = np.arange(1, ns * sh)
        oth = dy[(ys % sh != 0) & (ys % sh != sh // 2)].mean()
        line.append('%s PSNR %.2f excess %+.2f' % ('Y Cb Cr'.split()[pi], 10 * math.log10(1023 ** 2 / (e ** 2).mean()), (dy[ys % sh == 0].mean() - dy[ys % sh == sh // 2].mean()) / oth))
    if DUMP: np.concatenate([r.astype('<u2').ravel() for r in recs_out]).tofile(DUMP + '_' + phase + '.yuv')
    print('%-6s sh%d Qf %.1f bpp(ent) %.3f | %s' % (phase, sh, Qf, tb / (W * (H // sh) * sh), ' | '.join(line)), flush=True)
