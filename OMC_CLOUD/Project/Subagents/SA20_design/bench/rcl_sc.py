#!/usr/bin/env python3
# rcl_sc.py CLIP — STEP-INVARIANT entropy model under today's table budget (60 static tables, 1.1 Mbit).
# Context = class of an estimated local scale of q, from decoded data only:
#   m = |q_left| + |q_up| (+ |q_upleft| + |q_upright| halved; causal, same symbol array)  +  act (inner-tap
#   difference / level step, from final coarser samples) ; class = digitize(log2(1 + m)), K classes.
# Tables are POOLED over every step (one set for all Q). Variants (table count):
#   S16   : 16 classes, shared by all levels and planes               (16 tables)
#   S16p  : x plane class (luma/chroma)                               (32)
#   S16pk : x plane class x {kept DPCM, leaf}                          (64 -> reported against the 60 cap)
#   S12pk : 12 classes x plane x {kept, leaf}                          (48)
# Reference: base per-Q (1-bit context, one set per quarter-octave step = the optimistic figure used so far).
# Intra frame 0, cm1, test clip held out from training. Prints bpp per Q per variant.
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from d1_screen import read
from n4_core import po
W, H = 1280, 720
A = '/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/'
TRAIN = [('cine_4k_A006', 2), ('cine_A005C021', 2), ('gfx444_F003C012', 3)]
TEST = sys.argv[1]; CM = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0; ES = list(range(-2, 25))
def nzc(q):
    nz = q != 0; c = np.zeros_like(nz); c[:, 1:] |= nz[:, :-1]; c[1:, :] |= nz[:-1, :]; return c.astype(int)
def mag(q, a, ua=True):
    q = np.abs(q.astype(float)); m = np.zeros_like(q)
    m[:, 1:] += q[:, :-1]; m[1:, :] += q[:-1, :]; m[1:, 1:] += 0.5 * q[:-1, :-1]; m[1:, :-1] += 0.5 * q[:-1, 1:]
    return m + a[:q.shape[0], :q.shape[1]] if ua else m
def cls(q, a, K, ua=True): return np.minimum((np.log2(1 + mag(q, a, ua)) * K / 7).astype(int), K - 1)
VAR = {'S16': (16, 0, 0), 'S16p': (16, 1, 0), 'S16pk': (16, 1, 1), 'S12pk': (12, 1, 1), 'S16i': (16, 0, 0, 0)}
if os.environ.get('ONLY'): VAR = {k: VAR[k] for k in os.environ['ONLY'].split(',')}
def keys(pl, key, q, a, v):
    K, P_, Kp = VAR[v][:3]; c = cls(q, a, K, VAR[v][3] if len(VAR[v]) > 3 else True)
    return c + K * ((pl if P_ else 0) * 2 + ((key[0] == 'c') if Kp else 0))
def syms(planes, Q):
    out = []
    for pl, p in enumerate(planes):
        SY = []; AC = []; po(p, Q * (CM if pl else 1), 0.7, 0, SY, ACT=AC); out.append((min(pl, 1), SY, AC))
    return out
def acc(S, v, tab):
    for pl, SY, AC in S:
        for (key, q), a in zip(SY, AC):
            k = keys(pl, key, q, a, v) if v != 'base' else nzc(q); vq = np.clip(q.astype(np.int64), -64, 64) + 64
            for kk in np.unique(k):
                np.add.at(tab.setdefault(((pl,) + key if v == 'base' else ()) + (kk,), np.zeros(129)), vq[k == kk], 1)
def cost(S, v, tab):
    b = 0.0
    for pl, SY, AC in S:
        for (key, q), a in zip(SY, AC):
            k = keys(pl, key, q, a, v) if v != 'base' else nzc(q); q = q.astype(np.int64)
            for kk in np.unique(k):
                x = q[k == kk]; h = tab.get(((pl,) + key if v == 'base' else ()) + (kk,), np.zeros(129)) + 1; p = h / h.sum()
                b += -np.log2(p[np.clip(x, -64, 64) + 64]).sum() + (12 + 2 * np.log2(np.abs(x[np.abs(x) > 63]))).sum()
    return b
TR = [read(A + c + '_1280x720_422_10.yuv', W, H, f) for c, nf in TRAIN for f in range(nf)]
X = read(A + TEST + '_1280x720_422_10.yuv', W, H, 0)
PQ = {}; POOL = {v: {} for v in VAR}
for e in ES:
    Q = 2 ** (e / 4); PQ[e] = {}
    for fr in TR:
        S = syms(fr, Q); acc(S, 'base', PQ[e])
        for v in VAR: acc(S, v, POOL[v])
print('tables: ' + ' '.join('%s=%d' % (v, len(POOL[v])) for v in VAR) + ' | base per-Q = %d x %d steps' % (len(PQ[ES[0]]), len(ES)), flush=True)
for e in ES:
    Q = 2 ** (e / 4); S = syms(X, Q)
    esc = sum(int((np.abs(q) > 63).sum()) for _, SY, _ in S for _, q in SY); nsym = sum(q.size for _, SY, _ in S for _, q in SY)
    print('%s Q=%.3f base-perQ %.4f | ' % (TEST, Q, cost(S, 'base', PQ[e]) / (W * H)) + ' '.join('%s %.4f' % (v, cost(S, v, POOL[v]) / (W * H)) for v in VAR) + ' | escapes %.4f %%' % (100 * esc / nsym), flush=True)
