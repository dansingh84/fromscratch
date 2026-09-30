# D5 (screen): which in-slice context variables reduce the class-symbol entropy? empirical conditional entropy of
# the emitted class symbols (frames 2..N-1) under: A = SA17 key+nb ctx; B = A + still (block vector 0); C = A + parent
# class>0; D = A + still + parent; plus a zero-group layer (groups of 4 in a row: flag + classes of nonzero groups).
import numpy as np, sys, yuv, ent, seq, codec
from collections import defaultdict
cell, bpp = sys.argv[1], float(sys.argv[2]); N = int(sys.argv[3]) if len(sys.argv) > 3 else 6; HOLD = int(sys.argv[4]) if len(sys.argv) > 4 else 1
p_, W, H = yuv.CELLS[cell] if cell in yuv.CELLS else yuv.TRAIN[cell]
tabs = ent.Tables(sys.argv[5] if len(sys.argv) > 5 else '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA17_design/out/tab_eb_r2.pkl')
S = 4 if H == 720 else 8
s = seq.Seq(W, H, bpp, tabs, tilt=0.25, rho=0.35, bx=64, lam=4, refresh=False, still_hold=HOLD, S=S)
PAR = {'HL1': 'HL2', 'LH1': 'LH2', 'HH1': 'HH2', 'HL2': 'H3', 'LH2': 'H3', 'HH2': 'H3', 'H3': 'H4', 'H4': 'H5', 'H5': None, 'LL': None}
cnt = defaultdict(lambda: defaultdict(lambda: np.zeros(ent.NC)))
gcnt = defaultdict(lambda: np.zeros(2)); gcls = defaultdict(lambda: np.zeros(ent.NC)); tabbits = 0.0
def H_(d):
    t = 0.0
    for a in d.values():
        n = a.sum(); t -= (a[a > 0] * np.log2(a[a > 0] / n)).sum()
    return t
for f in range(N):
    x = yuv.read_frame(p_, W, H, f); o, b, info = s.encode(x)
    if f < 2 or info['intra']: continue
    zero = (np.abs(info['V']).sum(-1) == 0)
    for p in range(3):
        Q = info['Q'][p]
        for bn in codec.BANDSP[p]:
            q = Q[bn]; c = ent.cls(q); cc = np.minimum(c, ent.NC - 1)
            nb = s.c.slice_ctx(c, bn, p)
            rpb = S // codec.ROWDIV[(p, bn)]
            e_s = np.array([s.c.E[info['plans'][k]][(p, bn)] for k in range(len(info['plans']))]); eb = np.repeat(ent.ebucket(e_s), rpb)[:, None] * np.ones((1, q.shape[1]), int)
            im = info['im'][p][bn]; st = s.zero_mask(zero, p, bn, q.shape) & im
            pb = PAR[bn]
            if pb is not None:
                cp = ent.cls(Q[pb]); fy = q.shape[0] // cp.shape[0]; fx = q.shape[1] // cp.shape[1]
                par = (cp[np.arange(q.shape[0]) // fy][:, np.arange(q.shape[1]) // fx] > 0).astype(int)
            else: par = np.zeros_like(q)
            key = (0 if p == 0 else 1, ent.GROUP[bn])
            for name, feats in (('A', (eb, im, nb)), ('B', (eb, im, nb, st)), ('C', (eb, im, nb, par)), ('D', (eb, im, nb, st, par))):
                F = np.stack([f_.ravel() for f_ in feats], 1); ks = [tuple(r) for r in np.unique(F, axis=0)]
                for kk in ks:
                    m = np.all(F == np.array(kk), 1)
                    cnt[name][(key,) + kk] += np.bincount(cc.ravel()[m], minlength=ent.NC)
            # zero groups of 4 (row-wise), context = (key, eb-bucket, im, still, left group nz, above group nz)
            w4 = q.shape[1] // 4 * 4
            g = (c[:, :w4].reshape(q.shape[0], -1, 4) > 0).any(-1).astype(int)
            gl = np.zeros_like(g); gl[:, 1:] = g[:, :-1]; ga = np.zeros_like(g); ga[1:] = g[:-1]; ga[::rpb] = 0
            gst = st[:, :w4:4]; geb = eb[:, :w4:4]; gim = im[:, :w4:4]
            GF = np.stack([geb.ravel(), gim.ravel(), gst.ravel(), gl.ravel() + ga.ravel()], 1)
            for kk in [tuple(r) for r in np.unique(GF, axis=0)]:
                m = np.all(GF == np.array(kk), 1); gcnt[(key,) + kk] += np.bincount(g.ravel()[m], minlength=2)
                # classes inside nonzero groups, with the SA17 nb context
                rows_ = np.repeat(m.reshape(g.shape) & (g > 0), 4, axis=1)
                ccg = cc[:, :w4][rows_]; nbg = nb[:, :w4][rows_]
                for v in range(ent.NCTX):
                    gcls[(key,) + kk + (v,)] += np.bincount(ccg[nbg == v], minlength=ent.NC)
res = {k: H_(v) for k, v in cnt.items()}
print(cell, bpp, 'hold', HOLD, 'empirical class bits:', ' '.join('%s %.0f' % (k, res[k]) for k in sorted(res)),
      '| groups: flags %.0f + classes %.0f = %.0f' % (H_(gcnt), H_(gcls), H_(gcnt) + H_(gcls)))
