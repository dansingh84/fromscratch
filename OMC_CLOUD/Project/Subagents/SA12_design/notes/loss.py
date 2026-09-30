"""A5 probe: intra frame, B7 (s10a vertical with context from the decoded rows above). Slice k lost and concealed
(a) by the co-located rows of a DIFFERENT frame (f7, as a stand-in for temporal concealment), (b) by flat mid-grey
(worst case). Decode the rest normally from their indices; report mean |extra error| per following slice."""
import sys, os, math, numpy as np
os.environ['HF_FAST'] = '1'; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hf
A = '/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/long/spotrobotL_1920x1080_422_10.yuv'
P = hf.load(A, 1920, 1080, 8, '422')[0][:1072]; Pc = hf.load(A, 1920, 1080, 7, '422')[0][:1072]
sh, W = 16, 1920; ns = P.shape[0] // sh; L, nv, kH, kV = 5, 3, 's10', 's10a'
w = hf.weights(sh, W, L, nv, kH, kV); ks = hf.keys(L, nv); w[ks[-1]] *= 4.0
for Qf in (5.0, 7.0):
    st = {k: max(1, int(round(2.0 ** round(Qf - 0.5 * math.log2(w[k]))))) for k in ks}
    def run(Qs=None, lost=None, conceal=None):
        rec = np.zeros((ns * sh, W), np.int64); Q = []
        for k in range(ns):
            X = P[k * sh:(k + 1) * sh][None].astype(np.int64); LO = np.zeros(X.shape, np.int64); HI = np.full(X.shape, 1023, np.int64)
            hf._slice0[0] = k - 1; ctx = hf.ctx_of(rec[(k - 1) * sh:k * sh][None], L, nv, kH) if k else None
            hf._slice0[0] = k
            if lost == k: rec[k * sh:(k + 1) * sh] = conceal[k * sh:(k + 1) * sh]; Q.append(None); continue
            C = hf.Coder('enc', st) if Qs is None else hf.Coder('dec', st, Qs[k])
            rec[k * sh:(k + 1) * sh] = hf.rec_level(C, 1, L, nv, X if Qs is None else 0 * X, LO, HI, kH, kV, ctx)[0]; Q.append(C.Q)
        return rec, Q
    R0, Q0 = run()
    k0 = 30
    for nm, conc in (('other-frame', Pc.astype(np.int64)), ('grey', np.full(P.shape, 512, np.int64))):
        R1, _ = run(Q0, k0, conc)
        d = np.abs(R1 - R0).astype(float)
        per_slice = [d[(k0 + j) * sh:(k0 + j + 1) * sh].mean() for j in range(0, 5)]
        rows = d[(k0 + 1) * sh:(k0 + 2) * sh].mean(1)
        print('Qf %.1f conceal=%-11s mean|extra err| lost slice %.2f | next slices +1..+4: %s | rows of slice+1 with extra>0.05: %d/16' %
              (Qf, nm, per_slice[0], ' '.join('%.3f' % x for x in per_slice[1:]), int((rows > 0.05).sum())), flush=True)
