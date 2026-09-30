#!/usr/bin/env python3
"""[SA11 E] offline: legality + generation exactness of the vertical-causal pipeline (S5a family).
INTEGER pipeline: row predictor up3 = (a + 2b + c + 2) >> 2 on the reconstructed row above (row 0: mid-grey 512);
residual row e = x - p (integers); horizontal INTEGER 5/3 lifting, 5 levels (predict h = o - floor((e0+e1)/2),
update l = e + floor((h_-1 + h + 2)/4)), whole-sample symmetric extension; dead-zone quantiser 9/16 with power-of-two
steps D >= 1 per band from the 1-D synthesis weights, coarse-band step x 2^-1; recon coefficient q*D.
Variants: E1 per-pixel clamp after the inverse; E2 E1 + K rounds of 1-D in-cell projection (clamp -> forward ->
clamp each coefficient into its quantiser cell -> inverse -> clamp), K = 2 and 4; E2q E2 (K=4) with the one-step
requantisation q* = Q(F(r - p)) at the encoder (emitted indices are q*, the decoder is E2); E3 S5b: 1 level of
horizontal predict-only (h = o - floor((e0+e1)/2)) + closed-loop left DPCM on the coarse half, final pixel clamp.
Gen 1 encodes the source, gen 2 encodes the gen-1 decode with identical rules and the same Qf (carried in the
stream); indices and decodes compared.  usage: exact_e.py tag path W H frame"""
import numpy as np, sys, math, json
LO, HI = 0, 1023
NL = 5
def refl(pos, N):
    pos = np.where(pos < 0, -pos, pos); return np.where(pos > N - 1, 2 * (N - 1) - pos, pos)
def fwd1(x, upd=True):
    N = x.shape[-1]; k = np.arange(N // 2); e = x[..., 0::2]; o = x[..., 1::2]
    h = o - ((e[..., refl(2 * k, N) // 2] + e[..., refl(2 * k + 2, N) // 2]) >> 1)
    l = e + ((h[..., refl(2 * k - 1, N) // 2] + h[..., refl(2 * k + 1, N) // 2] + 2) >> 2) if upd else e.copy()
    return np.concatenate([l, h], -1)
def inv1(y, upd=True):
    N = y.shape[-1]; m = N // 2; k = np.arange(m); l = y[..., :m]; h = y[..., m:]
    e = l - ((h[..., refl(2 * k - 1, N) // 2] + h[..., refl(2 * k + 1, N) // 2] + 2) >> 2) if upd else l.copy()
    o = h + ((e[..., refl(2 * k, N) // 2] + e[..., refl(2 * k + 2, N) // 2]) >> 1)
    x = np.empty_like(y); x[..., 0::2] = e; x[..., 1::2] = o; return x
def hfwd(x):
    x = x.copy(); C = x.shape[-1]
    for l in range(NL): n = C >> l; x[..., :n] = fwd1(x[..., :n])
    return x
def hinv(x):
    x = x.copy(); C = x.shape[-1]
    for l in reversed(range(NL)): n = C >> l; x[..., :n] = inv1(x[..., :n])
    return x
def hbands(C): return [(C >> (l + 1), C >> l) for l in range(NL)] + [(0, C >> NL)]
def steps(C, Qf, variant):
    if variant == 'E3':
        bl = [(C // 2, C), (0, C // 2)]; w = [1.0, 2.5]      # predict-only 1 level: detail weight 1, even ~(1+2*.25*... )
    else:
        bl = hbands(C); w = []
        for c0, c1 in bl:   # float synthesis energy of a band impulse (float 5/3)
            z = np.zeros(C); z[(c0 + c1) // 2] = 1.0
            w.append(float((hinv_f(z) ** 2).sum()))
    D = np.empty(C, dtype=np.int64)
    for i, (c0, c1) in enumerate(bl):
        e = round(Qf - 0.5 * math.log2(w[i]) - (1 if i == len(bl) - 1 else 0)); D[c0:c1] = 1 << max(e, 0)
    return D, bl
def hinv_f(x):   # float 5/3 inverse, only for the synthesis weights
    x = x.astype(float).copy(); C = x.shape[-1]
    for l in reversed(range(NL)):
        n = C >> l; y = x[:n]; m = n // 2; k = np.arange(m); L = y[:m].copy(); Hh = y[m:].copy()
        e = L - 0.25 * (Hh[refl(2 * k - 1, n) // 2] + Hh[refl(2 * k + 1, n) // 2])
        o = Hh + 0.5 * (e[refl(2 * k, n) // 2] + e[refl(2 * k + 2, n) // 2])
        xx = np.empty(n); xx[0::2] = e; xx[1::2] = o; x[:n] = xx
    return x
def quant(c, D): a = (np.abs(c) * 16 + 7 * D) // (16 * D); return np.where(c < 0, -a, a)
def up3(r1):
    a = np.concatenate([r1[:1], r1[:-1]]); b = np.concatenate([r1[1:], r1[-1:]]); return (a + 2 * r1 + b + 2) >> 2
def cellclip(y, q, D):
    aq = np.abs(q); lo = aq * D - (7 * D) // 16; hi = aq * D + (9 * D + 15) // 16 - 1
    h0 = (9 * D + 15) // 16 - 1
    lo = np.where(q == 0, -h0, np.where(q > 0, lo, -hi)); hi2 = np.where(q == 0, h0, np.where(q > 0, hi, -(aq * D - (7 * D) // 16)))
    return np.clip(y, lo, hi2)
NCL = [0]
def decode_row(p, q, D, variant, K):
    if variant == 'E3':
        C = q.shape[-1]; m = C // 2
        z = np.concatenate([q[:m], q[m:] * D[m:]])   # coarse half holds already-reconstructed DPCM values
        v = p + inv1(z, upd=False); NCL[0] += int(((v < LO) | (v > HI)).sum())
        return np.clip(v, LO, HI)
    v0 = p + hinv(q * D); NCL[0] += int(((v0 < LO) | (v0 > HI)).sum()); v = np.clip(v0, LO, HI)
    for _ in range(K):
        y = hfwd(v - p); y = cellclip(y, q, D); v = np.clip(p + hinv(y), LO, HI)
    return v
R0 = __import__('os').environ.get('E_R0', 'mid')
def encode(X, Qf, variant, K=0, requant=False):
    Hh, W = X.shape; D, bl = steps(W, Qf, variant); Qs = np.zeros((Hh, W), dtype=np.int64); R = np.zeros_like(X)
    for r in range(Hh):
        p = (np.full(W, 512 if R0 == 'mid' else (0 if R0 == 'zero' else int(X[0, 0])), dtype=np.int64)) if r == 0 else up3(R[r - 1])
        e = X[r] - p
        if variant == 'E3':
            y = fwd1(e, upd=False); m = W // 2; q = np.empty(W, dtype=np.int64)
            q[m:] = quant(y[m:], D[m:])
            prev = 0; Dc = int(D[0])
            for i in range(m):   # closed-loop left DPCM of the coarse half
                qq = int(quant(np.array([y[i] - prev]), np.array([Dc]))[0]); prev = prev + qq * Dc; q[i] = prev
            Qs[r] = q; R[r] = decode_row(p, q, D, variant, 0)
            continue
        q = quant(hfwd(e), D)
        v = decode_row(p, q, D, variant, K)
        if requant:
            q2 = quant(hfwd(v - p), D); v2 = decode_row(p, q2, D, variant, K); q, v = q2, v2
        Qs[r] = q; R[r] = v
    return Qs, R, D, bl
def ent(q):
    _, c = np.unique(q, return_counts=True); p = c / q.size; return float(-(c * np.log2(p)).sum())
def bits(Qs, bl, variant, W):
    if variant == 'E3':   # coarse half: DPCM residual symbols = differences of the reconstructed coarse values / D
        m = W // 2; return ent(Qs[:, m:].ravel()) + ent(np.diff(np.concatenate([np.zeros((Qs.shape[0], 1), dtype=np.int64), Qs[:, :m]], 1), axis=1).ravel())
    return sum(ent(Qs[:, c0:c1].ravel()) for c0, c1 in bl)
def load(path, W, H, fr):
    fs = W * H * 2; d = np.fromfile(path, dtype='<u2', count=fs, offset=fr * fs * 2).astype(np.int64)
    return [d[:W * H].reshape(H, W), d[W * H:W * H + W * H // 2].reshape(H, W // 2), d[W * H + W * H // 2:].reshape(H, W // 2)]
def psnr(R, P):
    m = float(((R - P) ** 2).mean()); return 99.0 if m == 0 else 10 * math.log10(HI * HI / m)
if __name__ == '__main__':
    tag, path, W, H, fr = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
    targets = [float(x) for x in sys.argv[6].split(',')] if len(sys.argv) > 6 else [0.5, 1.0, 2.0]
    planes = load(path, W, H, fr); npx = planes[0].size
    VARS = [('E1', 0, False), ('E2K2', 2, False), ('E2K4', 4, False), ('E2qK4', 4, True), ('E3', 0, False)]
    if __import__('os').environ.get('E_VARS'): VARS = [v for v in [('E1q', 0, True), ('E2qK1', 1, True)] + VARS if v[0] in __import__('os').environ['E_VARS'].split(',')]
    out = {}
    for vn, K, rq in VARS:
        var = 'E3' if vn == 'E3' else 'E'
        # rate sweep (gen 1) to find the Qf for each target
        sw = []
        for Qf in [x / 2 for x in range(0, 24)]:
            b = 0.0; ps = []
            for P in planes:
                Qs, R, D, bl = encode(P, Qf, var, K, rq); b += bits(Qs, bl, var, P.shape[1]); ps.append(psnr(R, P))
            sw.append((Qf, b / npx, ps))
            if b / npx < min(targets) * 0.7: break
        res = {'sweep': sw, 'points': {}}
        for t in targets:
            Qf = min(sw, key=lambda s: abs(math.log2(max(s[1], 1e-9)) - math.log2(t)))[0]
            row = {'Qf': Qf, 'planes': []}
            for P in planes:
                NCL[0] = 0; Q1, R1, D, bl = encode(P, Qf, var, K, rq); b1 = bits(Q1, bl, var, P.shape[1]); ncl = NCL[0]
                Q2, R2, _, _ = encode(R1, Qf, var, K, rq)
                Q3, R3, _, _ = encode(R2, Qf, var, K, rq)
                row['planes'].append({'bits1': b1, 'psnr1': psnr(R1, P),
                                      'oor1': int(((R1 < LO) | (R1 > HI)).sum()), 'clamp_fired1': ncl,
                                      'idx_mis12': int((Q1 != Q2).sum()), 'pix_chg12': int((R1 != R2).sum()),
                                      'idx_mis23': int((Q2 != Q3).sum()), 'pix_chg23': int((R2 != R3).sum()),
                                      'rows_first_mis': int(np.argmax((Q1 != Q2).any(1))) if (Q1 != Q2).any() else -1})
            row['bpp'] = sum(x['bits1'] for x in row['planes']) / npx
            res['points']['%.1f' % t] = row
        out[vn] = res
        sys.stdout.flush()
    json.dump(out, open(tag + __import__('os').environ.get('E_SUFFIX', '') + '.E.json', 'w'))
    print('done', tag)
