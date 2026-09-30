# D13c: cheap variant of the coarse-first vector rule: candidates scored by SAD between LL1(t) and the 2x2 means of the
# BLOCK-shifted reference (no OBMC in the scoring), then OBMC prediction with the chosen vectors. Also 9-candidate sets.
import numpy as np, sys, yuv, motion, pyr
DEC = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA17_design/out/dec/final_%s_b0.5.d.yuv'
motion.BX = 64
def rule(d1, d2, ll1, Vh, cand_sets, obmc):
    H, W = d1.shape; nby, nbx = H // 8, W // 64
    ref1 = pyr.analysis(d1, 1, 1)['LL']
    Vc2 = motion.derive(ll1, ref1, bx=32, by=4, rx=8, ry=2, lam=4) * 2
    best = np.full((nby, nbx), np.iinfo(np.int64).max); Vb = Vh.copy()
    for name in cand_sets:
        base = Vh if name == 'h' else Vc2
        for dy in (0, -1, 1):
            for dx in (0, -1, 1):
                V = base + np.array([dy, dx])
                if obmc: P = motion.predict(d1, V)
                else:
                    ys = np.clip(np.arange(H)[:, None] + np.repeat(V[..., 0], 8, 0).repeat(64, 1), 0, H - 1)
                    xs = np.clip(np.arange(W)[None, :] + np.repeat(V[..., 1], 8, 0).repeat(64, 1), 0, W - 1)
                    P = d1[ys, xs]
                e = np.abs(pyr.analysis(P, 1, 1)['LL'] - ll1).reshape(nby, 4, nbx, 32).sum(axis=(1, 3))
                take = e < best; best = np.where(take, e, best); Vb[take] = V[take]
    return Vb
for cell in sys.argv[1].split(','):
    p_, W, H = yuv.CELLS[cell]; acc = {}
    for f in range(4, 8):
        S0 = yuv.read_frame(p_, W, H, f); Pt = yuv.read_frame(DEC % cell, W, H, f)[0]
        D1 = yuv.read_frame(DEC % cell, W, H, f - 1); D2 = yuv.read_frame(DEC % cell, W, H, f - 2)
        Vh = motion.derive(D1[0], D2[0], bx=64, lam=4); ll1 = pyr.analysis(Pt, 1, 1)['LL']
        F = {'hist': Vh, 'obmc18': rule(D1[0], D2[0], ll1, Vh, 'hc', True), 'blk18': rule(D1[0], D2[0], ll1, Vh, 'hc', False),
             'blk9h': rule(D1[0], D2[0], ll1, Vh, 'h', False), 'blk9c': rule(D1[0], D2[0], ll1, Vh, 'c', False)}
        for k, V in F.items():
            mse = [np.mean((motion.predict(D1[i], V, 1 if i == 0 else 2) - S0[i]) ** 2.0) for i in range(3)]
            acc.setdefault(k, [np.zeros(3), 0]); acc[k][0] += mse; acc[k][1] += motion.vec_bits(V - Vh)
    for k, (m, vb) in acc.items():
        print('%-7s %-7s pred PSNR %.2f/%.2f/%.2f  extra vec bits/frame %d' % (cell, k, *(10 * np.log10(1023 ** 2 / (m / 4))), vb // 4), flush=True)
