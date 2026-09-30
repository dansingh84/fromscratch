#!/usr/bin/env python3
"""[SA11 V] offline: vertical-causal family.  Rows transformed horizontally (5 levels: (4,0)+5/3 update at the two
finest levels, 5/3 at H3-H5), each coefficient predicted from the SAME band's reconstructed row above (closed loop in the
coefficient domain), residual quantised per band.  Same quantiser / rate / PSNR rules as struct_s.py.
usage: vcausal.py tag path W H frame sh part"""
import numpy as np, sys, math, json
sys.path.insert(0, __import__('os').path.dirname(__file__))
import struct_s as S
LO, HI = S.LO, S.HI
HF = [(S.P40, S.U53), (S.P40, S.U53), (S.P53, S.U53), (S.P53, S.U53), (S.P53, S.U53)]
NL = 5
def hfwd(x):
    x = x.copy(); C = x.shape[-1]
    for l in range(NL):
        n = C >> l; P, U = HF[l]; x[..., :n] = S.fwd1(x[..., :n], x.ndim - 1, P, U)
    return x
def hinv(x):
    x = x.copy(); C = x.shape[-1]
    for l in reversed(range(NL)):
        n = C >> l; P, U = HF[l]; x[..., :n] = S.inv1(x[..., :n], x.ndim - 1, P, U)
    return x
def hbands(C): return [(C >> (l + 1), C >> l) for l in range(NL)] + [(0, C >> NL)]
_wc = {}
def hweights(C):
    if C not in _wc:
        out = []
        for c0, c1 in hbands(C):
            z = np.zeros((1, C)); z[0, (c0 + c1) // 2] = 1.0; out.append(float((hinv(z) ** 2).sum()))
        _wc[C] = out
    return _wc[C]
_nb = {}
def nbr(C):
    if C not in _nb:
        L = np.arange(C); R = np.arange(C)
        for c0, c1 in hbands(C):
            idx = np.arange(c0, c1); L[c0:c1] = np.maximum(idx - 1, c0); R[c0:c1] = np.minimum(idx + 1, c1 - 1)
        _nb[C] = (L, R)
    return _nb[C]
PREDS = ('co', 'avg3', 'zero')
def pred(prev, p, C):
    if p == 'co': return prev
    if p == 'zero': return np.zeros_like(prev)
    L, R = nbr(C); return (prev[L] + 2 * prev + prev[R]) / 4
def code_v(X, sh, Qf, mode, offs=None, kll=-1):
    """X: plane (H, W) (pixels or temporal residual).  mode: fixed predictor name, 'canS' (per band per slice from the
    previous two reconstructed rows), 'canR' (per band per row, same rule), 'sig' (per band per slice, open-loop best on
    the source, 2 bits signalled).  returns bits, reconstruction (H, W)"""
    H, W = X.shape; bl = hbands(W); w = hweights(W)
    ex = [0.0] * len(bl) if offs is None else list(offs)
    ex[-1] += kll
    Ds = np.empty(W)
    for i, (c0, c1) in enumerate(bl): Ds[c0:c1] = 2.0 ** round(Qf - 0.5 * math.log2(w[i]) + ex[i])
    Y = hfwd(X.astype(float)); rc = np.zeros_like(Y); qs = np.zeros_like(Y); side = 0.0
    choice = ['co'] * len(bl)
    for r in range(H):
        if mode in PREDS: ch = [mode] * len(bl)
        elif r % sh == 0 or mode == 'canR':
            if mode in ('canS', 'canR'):
                if r >= 2:
                    for i, (c0, c1) in enumerate(bl):
                        errs = [np.abs(rc[r - 1, c0:c1] - pred(rc[r - 2], p, W)[c0:c1]).sum() for p in PREDS]
                        choice[i] = PREDS[int(np.argmin(errs))]
            else:   # 'sig': open-loop on the source over this slice's rows
                r1 = min(r + sh, H)
                for i, (c0, c1) in enumerate(bl):
                    errs = []
                    for p in PREDS:
                        e = 0.0
                        for rr in range(r, r1):
                            pv = pred(Y[rr - 1], p, W) if rr >= 1 else np.zeros(W)
                            e += np.abs(Y[rr, c0:c1] - pv[c0:c1]).sum()
                        errs.append(e)
                    choice[i] = PREDS[int(np.argmin(errs))]
                side += 2 * len(bl)
            ch = choice
        prev = rc[r - 1] if r >= 1 else np.zeros(W)
        pv = np.empty(W)
        for i, (c0, c1) in enumerate(bl): pv[c0:c1] = pred(prev, ch[i], W)[c0:c1]
        q = S.quant(Y[r] - pv, Ds); qs[r] = q; rc[r] = pv + q * Ds
    bits = side + sum(S.ent(qs[:, c0:c1].ravel()) for c0, c1 in bl)
    return bits, hinv(rc)
def code_base(X, sh, Qf, kll=-1):
    """today's 2-D structure (struct_s TODAY), returns bits, reconstruction"""
    H, W = X.shape; Hp = -(-H // sh) * sh
    Xs = np.vstack([X, np.repeat(X[-1:], Hp - H, 0)]).astype(float).reshape(Hp // sh, sh, W)
    Y = S.fwd(Xs, S.TODAY, 7); w = S.weights(sh, W, S.TODAY, 7); w[-1] *= 4.0 ** (-kll); bl, ll = S.bands(sh, W, 7)
    Z = np.zeros_like(Y); bits = 0.0
    for i, (r0, r1, c0, c1) in enumerate(bl + [ll]):
        D = 2.0 ** round(Qf - 0.5 * math.log2(w[i])); q = S.quant(Y[:, r0:r1, c0:c1], D)
        bits += S.ent(q.ravel()); Z[:, r0:r1, c0:c1] = q * D
    return bits, S.inv(Z, S.TODAY, 7).reshape(Hp, W)[:H]
def psnr(R, P):
    e = np.clip(np.rint(R), LO, HI) - P; m = float((e ** 2).mean()); return 99.0 if m == 0 else 10 * math.log10(HI * HI / m)
def oor(R): Ri = np.rint(R); return int(((Ri < LO) | (Ri > HI)).sum())
def sweep(planes, fn, Qfs):
    out = []
    for Qf in Qfs:
        b = 0.0; ps = []; o = 0
        for P in planes:
            bb, R = fn(P, Qf); b += bb; ps.append(psnr(R, P)); o += oor(R)
        out.append((Qf, b / planes[0].size, ps, o))
    return out
def at(pts, bpp):
    P = sorted([p for p in pts if p[1] > 0], key=lambda p: p[1]); xs = [math.log2(p[1]) for p in P]; x = math.log2(bpp)
    if not P or x < xs[0] or x > xs[-1]: return None
    return [float(np.interp(x, xs, [p[2][k] for p in P])) for k in range(3)]
def code_base_off(X, sh, Qf, offs):
    H, W = X.shape; Hp = -(-H // sh) * sh
    Xs = np.vstack([X, np.repeat(X[-1:], Hp - H, 0)]).astype(float).reshape(Hp // sh, sh, W)
    Y = S.fwd(Xs, S.TODAY, 7); w = S.weights(sh, W, S.TODAY, 7); bl, ll = S.bands(sh, W, 7)
    Z = np.zeros_like(Y); bits = 0.0
    for i, (r0, r1, c0, c1) in enumerate(bl + [ll]):
        e = offs[i] if i < len(offs) else -1
        D = 2.0 ** round(Qf - 0.5 * math.log2(w[i]) + e); q = S.quant(Y[:, r0:r1, c0:c1], D)
        bits += S.ent(q.ravel()); Z[:, r0:r1, c0:c1] = q * D
    return bits, S.inv(Z, S.TODAY, 7).reshape(Hp, W)[:H]

if __name__ == '__main__':
    tag, path, W, H, fr, sh, part = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]), sys.argv[7]
    Qfs = [x / 2 for x in range(3, 23)]
    res = {}
    planes = S.load(path, W, H, fr)
    if part == 'A':   # V1, V2, V4
        for k in (-2, -1, 0):
            for m in PREDS + ('canS', 'canR', 'sig'):
                res['V_%s_k%d' % (m, k)] = sweep(planes, lambda P, Qf, m=m, k=k: code_v(P, sh, Qf, m, kll=k), Qfs)
        json.dump(res, open(tag + '.A.json', 'w'))
    elif part == 'C':   # V4: S5a with and without the per-sample clamp
        for pr in ('up3', 'gsel'):
            for k in (-2, -1, 0):
                res['S5a_%s_k%d' % (pr, k)] = S.run_s5(planes, sh, 'a', pr, Qfs, k)
                res['S5aC_%s_k%d' % (pr, k)] = S.run_s5(planes, sh, 'aC', pr, Qfs, k)
        json.dump(res, open(tag + '.C.json', 'w'))
    elif part in ('B', 'Bbase'):   # V3 step search at 0.5/1.0/2.0 for mode sys.argv[8] (or the baseline)
        mode = sys.argv[8] if part == 'B' else None
        nb = 6 if part == 'B' else 10
        for tgt in (0.5, 1.0, 2.0):
            offs = [0] * nb if part == 'B' else [0] * 9 + [-1]; kll = -1
            def ev(o):
                if part == 'B':
                    pts = sweep(planes, lambda P, Qf: code_v(P, sh, Qf, mode, offs=o, kll=kll), Qfs)
                else:
                    pts = sweep(planes, lambda P, Qf: code_base_off(P, sh, Qf, o), Qfs)
                v = at(pts, tgt); return (-99 if v is None else float(np.mean(v))), v
            best, bv = ev(offs)
            for _ in range(2):
                for b in range(nb):
                    for d in (-2, -1, 1, 2):
                        o = list(offs); o[b] += d; s, v = ev(o)
                        if s > best + 1e-6: best, bv, offs = s, v, o
            res['%.1f' % tgt] = {'offs': offs, 'psnr': bv}
        json.dump(res, open('%s.%s%s.json' % (tag, part, ('_' + mode) if mode else ''), 'w'))
    elif part == 'D':   # V5 inter: frame fr coded as residual vs the reconstruction of frame fr-1 (zero motion)
        prevp = S.load(path, W, H, fr - 1)
        for nm, fn in (('base', lambda P, Qf: code_base(P, sh, Qf)),) + tuple(
                ('V_%s' % m, (lambda P, Qf, m=m: code_v(P, sh, Qf, m))) for m in ('co', 'zero', 'canS', 'canR')):
            out = []
            for Qf in Qfs:
                b = 0.0; ps = []
                for P0, P1 in zip(prevp, planes):
                    _, R0 = fn(P0, Qf); R0 = np.clip(np.rint(R0), LO, HI)
                    bb, Rr = fn(P1 - R0, Qf); b += bb; ps.append(psnr(R0 + Rr, P1))
                out.append((Qf, b / planes[0].size, ps, 0))
            res[nm] = out
        json.dump(res, open(tag + '.D.json', 'w'))
    print('done', tag, part)
