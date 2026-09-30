#!/usr/bin/env python3
# diag_inter.py CLIP ARM R — frame-1 bit split of the form-(i) engine under exact per-frame CBR (rcl_cbr.py tables):
# bits per plane x pyramid level (coarsest DPCM grid = 'kept', finer levels = leaves) x region (still / moving).
# still = source |x1 - x0| <= 2 codes over the 2x2 support at that grid position AND zero motion vector.
# Also verifies the exact-copy property: with every leaf forced to 0 an inter frame equals P sample by sample.
import sys, os, pickle, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
sys.argv, ARGS = sys.argv[:3], sys.argv
import importlib.util
from d1_screen import read
from n4_core import po
from dp_screen_core import motion, apply
CLIP, ARM, R = ARGS[1], ARGS[2], float(ARGS[3]); W, H = 1280, 720
A = '/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/'
OUT = os.path.join(os.path.dirname(__file__), '..', 'out', 'rcl_cbr')
TABS = pickle.load(open(os.path.join(OUT, 'tables_%s.pkl' % ARM), 'rb')); GRID = sorted(TABS)
TOK = ARM.split('_'); cm = float(TOK[0][2:]); FI = float([t[2:] for t in TOK if t.startswith('fi')][0]) if any(t.startswith('fi') for t in TOK) else 0.7
def ctx(q):
    nz = q != 0; c = np.zeros_like(nz); c[:, 1:] |= nz[:, :-1]; c[1:, :] |= nz[:-1, :]; return c
def costmap(q, key, tab):
    c = ctx(q); out = np.zeros(q.shape)
    for cc in (0, 1):
        m = c == cc; v = q[m].astype(np.int64); h = tab.get(key + (cc,), np.zeros(129)) + 1; p = h / h.sum()
        out[m] = -np.log2(p[np.clip(v, -64, 64) + 64]) + np.where(np.abs(v) > 63, 12 + 2 * np.log2(np.maximum(np.abs(v), 1)), 0)
    return out
def code(x, ref, Q, intra):
    if intra: Ps = [np.zeros_like(p) for p in x]; V = None
    else: V = motion(x[0], ref[0]); Ps = [apply(ref[0], V, 16, 1), apply(ref[1], V, 16, 2), apply(ref[2], V, 16, 2)]
    res = []
    for pl, (p, P) in enumerate(zip(x, Ps)):
        SY = []; y = po(p, Q * (cm if pl else 1), 0.7 if intra else FI, 0, SY, P=P)[1]; res.append((SY, y, P))
    return res, V
def bits(res, Q, mode):
    return sum(costmap(q, (min(pl, 1), mode) + key, TABS[Q]).sum() for pl, (SY, _, _) in enumerate(res) for key, q in SY)
X = [read(A + CLIP + '_1280x720_422_10.yuv', W, H, f) for f in range(2)]; budget = R * W * H; ref = None
for t in range(2):
    best = None
    for Q in GRID:
        res, V = code(X[t], ref, Q, t == 0); b = bits(res, Q, 'intra' if t == 0 else 'inter') + (10 * 3600 if t else 0)
        if b <= budget: best = (Q, res, V, b); break
    Q, res, V, b = best; ref = [y for _, y, _ in res]
    print('frame %d Q %.2f bpp %.3f' % (t, Q, b / (W * H)))
# frame-1 split
stillY = (np.abs(X[1][0] - X[0][0]) <= 2)
vz = np.zeros((H, W), bool)
for i in range(V.shape[0]):
    for j in range(V.shape[1]): vz[i*16:(i+1)*16, j*16:(j+1)*16] = (V[i, j] == 0).all()
still = stillY & vz
print('still share of luma samples: %.1f %%' % (100 * still.mean()))
tot = 0
for pl, (SY, y, P) in enumerate(res):
    st = still if pl == 0 else (still[:, 0::2] & still[:, 1::2])
    for key, q in SY:
        cm_ = costmap(q, (min(pl, 1), 'inter') + key, TABS[Q])
        # stride of this grid: find the step mapping q positions to plane positions
        rs = max(1, round(st.shape[0] / q.shape[0])); cs = max(1, round(st.shape[1] / q.shape[1]))
        m = st[::rs, ::cs][:q.shape[0], :q.shape[1]]
        tot += cm_.sum()
        print('plane %d level %-12s n %7d bits %9.0f (%.2f b/sym) | still n %7d bits %8.0f | moving bits %8.0f | nonzero %.1f %%' % (
            pl, key, q.size, cm_.sum(), cm_.mean(), m.sum(), cm_[m].sum(), cm_[~m].sum(), 100 * (q != 0).mean()))
# exact-copy check: all leaves zero -> out == P
p0, P0 = X[1][0], res[0][2]
print('exact copy check (zero residual input): max |po(P) - P| =', int(np.abs(po(P0, Q, FI, 0, [], P=P0)[1] - P0).max()))
