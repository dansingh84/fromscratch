#!/usr/bin/env python3
"""[SA11 SM] offline TEMPORAL coding for the smudge test (zero motion).  Slices of sh rows; slice s is intra on frame f
when f == 0 or f % 8 == s % 8 (staggered refresh, period 8, as today); other slices code the residual against the
reconstructed previous frame (co-located, zero motion).
 arm 'vc'  : vertical-causal integer pipeline of exact_e.py, E2qK4 (4 in-cell rounds, own-decode requantisation);
             intra row predictor = up3 of the reconstructed row above (frame row 0: 512); inter row predictor = the
             co-located reconstructed row of the previous frame; clamp to [0,1023].
 arm 'base': the float 2-D baseline of struct_s.py (today's structure) per slice on pixels (intra) or on the residual
             (inter), recon clamped and rounded.
Rate = zeroth-order entropy per band per frame (both arms).  Writes the decode (uint16 4:2:2 planar) and a json.
usage: temporal_sm.py arm src W H sh nframes Qf outprefix"""
import numpy as np, sys, json, math, os
sys.path.insert(0, os.path.dirname(__file__))
import exact_e as E, struct_s as S
arm, src, W, H, sh, NF, Qf, outp = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]), float(sys.argv[7]), sys.argv[8]
K = int(os.environ.get('SM_K', '4'))
def intra(f, s): return f == 0 or (f % 8) == (s % 8)
def code_vc(X, prev, f):
    Hh, Wd = X.shape; D, bl = E.steps(Wd, Qf, 'E'); Qs = np.zeros((Hh, Wd), dtype=np.int64); R = np.zeros_like(X)
    for r in range(Hh):
        s = r // sh
        if intra(f, s): p = np.full(Wd, 512, dtype=np.int64) if r == 0 else E.up3(R[r - 1])
        else: p = prev[r]
        q = E.quant(E.hfwd(X[r] - p), D); v = E.decode_row(p, q, D, 'E', K)
        q = E.quant(E.hfwd(v - p), D); v = E.decode_row(p, q, D, 'E', K)
        Qs[r] = q; R[r] = v
    bits = sum(E.ent(Qs[:, c0:c1].ravel()) for c0, c1 in bl)
    return bits, R
def code_base(X, prev, f):
    Hh, Wd = X.shape; Hp = -(-Hh // sh) * sh; ns = Hp // sh
    Xp = np.vstack([X, np.repeat(X[-1:], Hp - Hh, 0)]).astype(float)
    Pp = None if prev is None else np.vstack([prev, np.repeat(prev[-1:], Hp - Hh, 0)]).astype(float)
    it = np.array([intra(f, s) for s in range(ns)])
    inp = Xp.reshape(ns, sh, Wd).copy()
    if Pp is not None: inp[~it] -= Pp.reshape(ns, sh, Wd)[~it]
    Y = S.fwd(inp, S.TODAY, 7); w = S.weights(sh, Wd, S.TODAY, 7); w[-1] *= 4.0 ** 1; bl, ll = S.bands(sh, Wd, 7)
    Z = np.zeros_like(Y); bits = 0.0
    for i, (r0, r1, c0, c1) in enumerate(bl + [ll]):
        D = 2.0 ** round(Qf - 0.5 * math.log2(w[i])); q = S.quant(Y[:, r0:r1, c0:c1], D)
        bits += S.ent(q.ravel()); Z[:, r0:r1, c0:c1] = q * D
    V = S.inv(Z, S.TODAY, 7)
    if Pp is not None: V[~it] += Pp.reshape(ns, sh, Wd)[~it]
    return bits, np.clip(np.rint(V.reshape(Hp, Wd)[:Hh]), 0, 1023).astype(np.int64)
prev = [None, None, None]; out = open(outp + '.yuv', 'wb'); log = []
for f in range(NF):
    P = E.load(src, W, H, f); fb = 0.0; ps = []
    for k in range(3):
        if arm == 'vc':
            pv = prev[k] if prev[k] is not None else np.zeros_like(P[k])
            b, R = code_vc(P[k], pv, f)
        else:
            b, R = code_base(P[k], prev[k], f)
        prev[k] = R; fb += b; ps.append(E.psnr(R, P[k]))
    for k in range(3): out.write(prev[k].astype('<u2').tobytes())
    log.append((f, fb / (W * H), ps)); print(f, '%.3f' % (fb / (W * H)), ps, flush=True)
out.close()
json.dump({'arm': arm, 'Qf': Qf, 'frames': log}, open(outp + '.json', 'w'))
