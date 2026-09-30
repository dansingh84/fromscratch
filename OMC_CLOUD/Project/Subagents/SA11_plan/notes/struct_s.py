#!/usr/bin/env python3
"""[SA11 S] offline RD of transform structures (numpy only; no codec).  Slice-based 2V x 5H structure as
CORE/review/cgain2d.py (V1,H1,V2,H2,H3,H4,H5), whole-sample symmetric extension per slice, float lifting.
Quantiser: dead zone 9/16 (q = sign*floor(|c|/D + 7/16), recon q*D), D = 2^round(Qf - log2 sqrt(w_b)) per band
(w_b = synthesis energy of a band impulse).  Rate = zeroth-order entropy of the quantised symbols per band
(per-frame histogram per band; DPCM residual symbols one histogram per plane).  bpp = all planes / luma pixels.
usage: struct_s.py <tag> <path> W H frame sh"""
import numpy as np, sys, math, json
LO, HI = 0.0, 1023.0
P53 = [(0, .5), (1, .5)]; U53 = [(-1, .25), (0, .25)]
P40 = [(-1, -1/16), (0, 9/16), (1, 9/16), (2, -1/16)]
P60 = [(-2, 3/256), (-1, -25/256), (0, 150/256), (1, 150/256), (2, -25/256), (3, 3/256)]
STAGES = ['V1', 'H1', 'V2', 'H2', 'H3', 'H4', 'H5']
def refl(pos, N):
    pos = np.where(pos < 0, -pos, pos); return np.where(pos > N - 1, 2 * (N - 1) - pos, pos)
def fwd1(x, ax, P, U):
    x = np.moveaxis(x, ax, -1); N = x.shape[-1]; k = np.arange(N // 2)
    e = x[..., 0::2]; o = x[..., 1::2]; h = o.copy()
    for off, w in P: h -= w * e[..., refl(2 * (k + off), N) // 2]
    l = e.copy()
    for off, w in U: l += w * h[..., refl(2 * (k + off) + 1, N) // 2]
    return np.moveaxis(np.concatenate([l, h], -1), -1, ax)
def inv1(y, ax, P, U, clamp=False, crow=None):
    y = np.moveaxis(y, ax, -1); N = y.shape[-1]; m = N // 2; k = np.arange(m)
    l = y[..., :m]; h = y[..., m:]; e = l.copy()
    for off, w in U: e -= w * h[..., refl(2 * (k + off) + 1, N) // 2]
    o = h.copy()
    for off, w in P: o += w * e[..., refl(2 * (k + off), N) // 2]
    if clamp:
        if crow is None: o = np.clip(o, LO, HI)
        else: o[:, :crow] = np.clip(o[:, :crow], LO, HI)   # horizontal stage: only the vertical-lowpass rows are pixels
    x = np.empty_like(y); x[..., 0::2] = e; x[..., 1::2] = o
    return np.moveaxis(x, -1, ax)
def geo(R, C):  # (stage, rows, cols)
    return [('V1', R, C), ('H1', R, C), ('V2', R // 2, C // 2), ('H2', R // 2, C // 2),
            ('H3', R // 4, C // 4), ('H4', R // 4, C // 8), ('H5', R // 4, C // 16)]
def fwd(x, cfg, nst):  # x: (ns, R, C)
    x = x.copy(); R, C = x.shape[1:]
    for nm, nr, nc in geo(R, C)[:nst]:
        P, U = cfg[nm]; x[:, :nr, :nc] = fwd1(x[:, :nr, :nc], 1 if nm[0] == 'V' else 2, P, U)
    return x
def inv(x, cfg, nst, clamp=False):
    x = x.copy(); R, C = x.shape[1:]
    for nm, nr, nc in reversed(geo(R, C)[:nst]):
        P, U = cfg[nm]
        crow = nr // 2 if nm in ('H1', 'H2') else None
        x[:, :nr, :nc] = inv1(x[:, :nr, :nc], 1 if nm[0] == 'V' else 2, P, U, clamp, crow)
    return x
def bands(R, C, nst):
    b = [(R // 2, R, 0, C // 2), (0, R // 2, C // 2, C), (R // 2, R, C // 2, C)]
    if nst >= 4: b += [(R // 4, R // 2, 0, C // 4), (0, R // 4, C // 4, C // 2), (R // 4, R // 2, C // 4, C // 2)]
    if nst >= 7: b += [(0, R // 4, C // 8, C // 4), (0, R // 4, C // 16, C // 8), (0, R // 4, C // 32, C // 16)]
    if nst == 2: ll = (0, R // 2, 0, C // 2)
    elif nst == 4: ll = (0, R // 4, 0, C // 4)
    else: ll = (0, R // 4, 0, C // 32)
    return b, ll
def weights(R, C, cfg, nst):
    bl, ll = bands(R, C, nst); out = []
    for (r0, r1, c0, c1) in bl + [ll]:
        z = np.zeros((1, R, C)); z[0, (r0 + r1) // 2, (c0 + c1) // 2] = 1.0
        out.append(float((inv(z, cfg, nst) ** 2).sum()))
    return out
def ent(q):
    if q.size == 0: return 0.0
    _, c = np.unique(q, return_counts=True); p = c / q.size
    return float(-(c * np.log2(p)).sum())
def quant(c, D): return np.sign(c) * np.floor(np.abs(c) / D + 7 / 16)
def dpcm(img, D, pred):
    """closed-loop causal DPCM on img (R x C, pixel domain), wavefront over anti-diagonals"""
    R, C = img.shape; rec = np.zeros((R, C)); qs = np.zeros((R, C))
    for d in range(R + C - 1):
        r = np.arange(max(0, d - C + 1), min(R, d + 1)); c = d - r
        a = np.where(c > 0, rec[r, np.maximum(c - 1, 0)], np.nan)
        b = np.where(r > 0, rec[np.maximum(r - 1, 0), c], np.nan)
        t = np.where((r > 0) & (c > 0), rec[np.maximum(r - 1, 0), np.maximum(c - 1, 0)], np.nan)
        aa = np.where(np.isnan(a), np.where(np.isnan(b), 512.0, b), a)
        bb = np.where(np.isnan(b), aa, b); tt = np.where(np.isnan(t), bb, t)
        if pred == 'left': p = aa
        elif pred == 'top': p = bb
        elif pred == 'avg': p = np.floor((aa + bb) / 2)
        elif pred == 'plane': p = np.clip(aa + bb - tt, LO, HI)
        else:  # gsel: vertical smoothness at the left column -> take top, else left
            p = np.where(np.abs(aa - tt) < np.abs(bb - tt), bb, aa)
        q = quant(img[r, c] - p, D); qs[r, c] = q
        rec[r, c] = np.clip(p + q * D, LO, HI)
    return rec, qs
def run(planes, sh, cfg, nst, Qfs, mode, pred=None, clamp=False, kll=0):
    """mode 'tx': full nst-stage transform, LL quantised; 'dp': nst-stage predict-only + DPCM on LL"""
    res = []
    prep = []
    for P in planes:
        H, W = P.shape; Hp = -(-H // sh) * sh
        X = np.vstack([P, np.repeat(P[-1:], Hp - H, 0)]).astype(float).reshape(Hp // sh, sh, W)
        Y = fwd(X, cfg, nst); w = weights(sh, W, cfg, nst); w[-1] *= 4.0 ** (-kll); bl, ll = bands(sh, W, nst)
        prep.append((P, H, W, Hp, Y, w, bl, ll))
    for Qf in Qfs:
        bits = 0.0; ps = []; oor = 0
        for (P, H, W, Hp, Y, w, bl, ll) in prep:
            Z = np.zeros_like(Y)
            for i, (r0, r1, c0, c1) in enumerate(bl):
                D = 2.0 ** round(Qf - 0.5 * math.log2(w[i]))
                q = quant(Y[:, r0:r1, c0:c1], D); bits += ent(q.ravel()); Z[:, r0:r1, c0:c1] = q * D
            r0, r1, c0, c1 = ll; D = 2.0 ** round(Qf - 0.5 * math.log2(w[-1]))
            if mode == 'tx':
                q = quant(Y[:, r0:r1, c0:c1], D); bits += ent(q.ravel()); Z[:, r0:r1, c0:c1] = q * D
            else:
                L = Y[:, r0:r1, c0:c1]; ns, lr, lc = L.shape
                rec, qs = dpcm(L.reshape(ns * lr, lc), D, pred)
                bits += ent(qs.ravel()); Z[:, r0:r1, c0:c1] = rec.reshape(ns, lr, lc)
            Rc = inv(Z, cfg, nst, clamp).reshape(Hp, W)[:H]
            Ri = np.rint(Rc); oor += int(((Ri < LO) | (Ri > HI)).sum())
            mse = float(((np.clip(Ri, LO, HI) - P) ** 2).mean())
            ps.append(99.0 if mse == 0 else 10 * math.log10(HI * HI / mse))
        res.append((Qf, bits / (planes[0].size), ps, oor))
    return res
def load(path, W, H, fr):
    fs = W * H * 2; d = np.fromfile(path, dtype='<u2', count=fs, offset=fr * fs * 2).astype(float)
    return [d[:W * H].reshape(H, W), d[W * H:W * H + W * H // 2].reshape(H, W // 2), d[W * H + W * H // 2:].reshape(H, W // 2)]
TODAY = dict(V1=(P53, U53), V2=(P53, U53), H1=(P40, U53), H2=(P40, U53), H3=(P53, U53), H4=(P53, U53), H5=(P53, U53))
def po(cfg, levels):  # remove the update at the named stages
    c = dict(cfg)
    for s in levels: c[s] = (c[s][0], [])
    return c

# ---------------- S5: vertical causal row prediction + horizontal transform of the residual row -------------
import ctypes, os
_lib = ctypes.CDLL(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dpcm1.so'))
_dp = ctypes.POINTER(ctypes.c_double)
def dpcm_rows(C, D):
    C = np.ascontiguousarray(C, dtype=float); rec = np.zeros_like(C); q = np.zeros_like(C)
    _lib.dpcm_rows(C.ctypes.data_as(_dp), C.shape[0], C.shape[1], ctypes.c_double(D), rec.ctypes.data_as(_dp), q.ctypes.data_as(_dp))
    return rec, q
def rowpred(r1, r2, pred):
    if r1 is None: return np.full(0, 0.0)
    if pred == 'up': return r1
    a = np.concatenate([r1[:1], r1[:-1]]); b = np.concatenate([r1[1:], r1[-1:]])
    if pred == 'up3': return np.floor((a + 2 * r1 + b + 2) / 4)
    if pred == 'lin2': return r1 if r2 is None else np.clip(2 * r1 - r2, LO, HI)
    # gsel: horizontal activity in the row above: edge -> co-located, smooth -> 3-tap average
    return np.where(np.abs(b - a) > 16, r1, np.floor((a + 2 * r1 + b + 2) / 4))
def h_stages(C, nlev): return [(C >> l) for l in range(nlev)]
def hfwd(x, P, U, nlev):
    x = x.copy()
    for n in h_stages(x.shape[-1], nlev): x[..., :n] = fwd1(x[..., :n], x.ndim - 1, P, U)
    return x
def hinv(x, P, U, nlev):
    x = x.copy()
    for n in reversed(h_stages(x.shape[-1], nlev)): x[..., :n] = inv1(x[..., :n], x.ndim - 1, P, U)
    return x
def hbands(C, nlev):
    b = [(C >> (l + 1), C >> l) for l in range(nlev)]; return b, (0, C >> nlev)
def hweights(C, P, U, nlev):
    bl, ll = hbands(C, nlev); out = []
    for (c0, c1) in bl + [ll]:
        z = np.zeros((1, C)); z[0, (c0 + c1) // 2] = 1.0; out.append(float((hinv(z, P, U, nlev) ** 2).sum()))
    return out
def run_s5(planes, sh, variant, pred, Qfs, kll=0, want_phase=None):
    """variant 'a': 5-level horizontal 5/3 with update, all bands quantised; 'b1'/'b2': 1/2 levels horizontal
    predict-only (2-tap), coarse band closed-loop left-DPCM; reconstruction clamped per sample in 'b'."""
    res = []
    for Qf in Qfs:
        bits = 0.0; ps = []; oor = 0; phase = []
        for Pl in planes:
            H, W = Pl.shape
            if variant in ('a', 'aC'): P, U, nlev = P53, U53, 5
            else: P, U, nlev = P53, [], (1 if variant == 'b1' else 2)
            w = hweights(W, P, U, nlev); w[-1] *= 4.0 ** (-kll); bl, ll = hbands(W, nlev)
            Ds = [2.0 ** round(Qf - 0.5 * math.log2(x)) for x in w]
            rec = np.zeros((H, W)); qb = [[] for _ in range(len(bl) + 1)]; nbad = 0
            for r in range(H):
                r1 = rec[r - 1] if r >= 1 else None; r2 = rec[r - 2] if r >= 2 else None
                p = np.full(W, 512.0) if r1 is None else rowpred(r1, r2, pred)
                y = hfwd((Pl[r] - p)[None, :], P, U, nlev)
                z = np.zeros_like(y)
                for i, (c0, c1) in enumerate(bl):
                    q = quant(y[:, c0:c1], Ds[i]); qb[i].append(q.ravel()); z[:, c0:c1] = q * Ds[i]
                c0, c1 = ll
                if variant in ('a', 'aC'):
                    q = quant(y[:, c0:c1], Ds[-1]); qb[-1].append(q.ravel()); z[:, c0:c1] = q * Ds[-1]
                else:
                    rr, q = dpcm_rows(y[:, c0:c1], Ds[-1]); qb[-1].append(q.ravel()); z[:, c0:c1] = rr
                v = p + hinv(z, P, U, nlev)[0]
                vi = np.rint(v); nbad += int(((vi < LO) | (vi > HI)).sum())
                rec[r] = np.clip(vi, LO, HI) if variant != 'a' else vi
            for qq in qb: bits += ent(np.concatenate(qq))
            oor += nbad
            Rc = np.clip(rec, LO, HI); err = np.abs(Rc - Pl)
            mse = float((err ** 2).mean()); ps.append(99.0 if mse == 0 else 10 * math.log10(HI * HI / mse))
            phase.append([float(err[k::sh].mean()) for k in range(sh)])
        res.append((Qf, bits / planes[0].size, ps, oor, phase))
    return res
def phase_tx(planes, sh, cfg, nst, Qf, kll=0):
    """row-phase mean |error| for the transform baseline at one Qf"""
    out = []
    for P in planes:
        H, W = P.shape; Hp = -(-H // sh) * sh
        X = np.vstack([P, np.repeat(P[-1:], Hp - H, 0)]).astype(float).reshape(Hp // sh, sh, W)
        Y = fwd(X, cfg, nst); w = weights(sh, W, cfg, nst); w[-1] *= 4.0 ** (-kll); bl, ll = bands(sh, W, nst)
        Z = np.zeros_like(Y)
        for i, (r0, r1, c0, c1) in enumerate(bl + [ll]):
            D = 2.0 ** round(Qf - 0.5 * math.log2(w[i])); Z[:, r0:r1, c0:c1] = quant(Y[:, r0:r1, c0:c1], D) * D
        Rc = np.clip(np.rint(inv(Z, cfg, nst).reshape(Hp, W)[:H]), LO, HI); err = np.abs(Rc - P)
        out.append([float(err[k::sh].mean()) for k in range(sh)])
    return out
if __name__ == '__main__':
    tag, path, W, H, fr, sh = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6])
    part = sys.argv[7] if len(sys.argv) > 7 else 'all'
    planes = load(path, W, H, fr)
    Qfs = [x / 2 for x in range(3, 23)]
    KS = (-3, -2, -1, 0)
    arms = {}
    def put(name, fn):
        arms[name] = {str(k): fn(k) for k in KS}; sys.stdout.flush()
    if part in ('all', 'tx'):
        put('base', lambda k: run(planes, sh, TODAY, 7, Qfs, 'tx', kll=k))
        for nm, lv in [('po_L1', ['V1', 'H1']), ('po_L2', ['V2', 'H2']), ('po_H3', ['H3']), ('po_H4', ['H4']), ('po_H5', ['H5']),
                       ('po_all', STAGES)]:
            put(nm, lambda k, lv=lv: run(planes, sh, po(TODAY, lv), 7, Qfs, 'tx', kll=k))
        PO2 = dict(V1=(P53, []), H1=(P53, []), V2=(P53, []), H2=(P53, []))
        PO4 = dict(V1=(P40, []), H1=(P40, []), V2=(P40, []), H2=(P40, []))
        PO6 = dict(V1=(P60, []), H1=(P60, []), V2=(P40, []), H2=(P40, []))
        for nl, nst in ((1, 2), (2, 4)):
            for pr in ('left', 'top', 'avg', 'plane', 'gsel'):
                put('S2_L%d_%s' % (nl, pr), lambda k, nst=nst, pr=pr: run(planes, sh, PO2, nst, Qfs, 'dp', pr, True, k))
            for pr in ('avg', 'gsel'):
                put('S3_40_L%d_%s' % (nl, pr), lambda k, nst=nst, pr=pr: run(planes, sh, PO4, nst, Qfs, 'dp', pr, True, k))
                put('S3_60_L%d_%s' % (nl, pr), lambda k, nst=nst, pr=pr: run(planes, sh, PO6, nst, Qfs, 'dp', pr, True, k))
        json.dump({'tag': tag, 'arms': arms}, open(tag + '.json', 'w'))
    if part in ('all', 's5'):
        arms5 = {}
        for var in ('a', 'b1', 'b2'):
            for pr in ('up', 'up3', 'lin2', 'gsel'):
                arms5['S5%s_%s' % (var, pr)] = {str(k): run_s5(planes, sh, var, pr, Qfs, k) for k in (-2, -1, 0)}
                sys.stdout.flush()
        json.dump({'tag': tag, 'arms': arms5}, open(tag + '.s5.json', 'w'))
    print('done', tag, part)
