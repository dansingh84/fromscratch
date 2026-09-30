# D14: vectors chosen on the decoded QUARTER-res LL2(t) (available before level-2 bands): candidates {Vh + d, d in
# [-2..2]^2} scored by block SAD of the block-shifted reference's LL2 vs LL2(t). Compare with LL1-scored (blk18).
import numpy as np, sys, yuv, motion, pyr
from d13c_ccv import rule
DEC = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA17_design/out/dec/final_%s_b0.5.d.yuv'
motion.BX = 64
def rule2(d1, ll2, Vh, R=2):
    H, W = d1.shape; nby, nbx = H // 8, W // 64
    best = np.full((nby, nbx), np.iinfo(np.int64).max); Vb = Vh.copy()
    for dy in [0] + [v for k in range(1, R + 1) for v in (-k, k)]:
        for dx in [0] + [v for k in range(1, R + 1) for v in (-k, k)]:
            V = Vh + np.array([dy, dx])
            ys = np.clip(np.arange(H)[:, None] + np.repeat(V[..., 0], 8, 0).repeat(64, 1), 0, H - 1)
            xs = np.clip(np.arange(W)[None, :] + np.repeat(V[..., 1], 8, 0).repeat(64, 1), 0, W - 1)
            P = d1[ys, xs]; l2 = pyr.analysis(pyr.analysis(P, 1, 1)['LL'], 1, 1)['LL']
            e = np.abs(l2 - ll2).reshape(nby, 2, nbx, 16).sum(axis=(1, 3))
            take = e < best; best = np.where(take, e, best); Vb[take] = V[take]
    return Vb
for cell in sys.argv[1].split(','):
    p_, W, H = yuv.CELLS[cell]; acc = {}
    for f in range(4, 8):
        S0 = yuv.read_frame(p_, W, H, f); Pt = yuv.read_frame(DEC % cell, W, H, f)[0]
        D1 = yuv.read_frame(DEC % cell, W, H, f - 1); D2 = yuv.read_frame(DEC % cell, W, H, f - 2)
        Vh = motion.derive(D1[0], D2[0], bx=64, lam=4); ll1 = pyr.analysis(Pt, 1, 1)['LL']; ll2 = pyr.analysis(ll1, 1, 1)['LL']
        F = {'hist': Vh, 'll1_blk18': rule(D1[0], D2[0], ll1, Vh, 'hc', False), 'll2_r2': rule2(D1[0], ll2, Vh, 2), 'll2_r1': rule2(D1[0], ll2, Vh, 1)}
        for k, V in F.items():
            mse = [np.mean((motion.predict(D1[i], V, 1 if i == 0 else 2) - S0[i]) ** 2.0) for i in range(3)]
            acc.setdefault(k, np.zeros(3)); acc[k] += mse
    for k, m in acc.items():
        print('%-7s %-10s pred PSNR %.2f/%.2f/%.2f' % (cell, k, *(10 * np.log10(1023 ** 2 / (m / 4)))), flush=True)
