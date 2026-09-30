# D13b: per block choose among candidates C = {hist+d, ccv2+d : d in {-1,0,1}^2} by SAD of the candidate prediction's
# 2x2 means against the CURRENT decoded half-res coarse band LL1(t) (exact: data gen 2 and the encoder both have).
import numpy as np, sys, yuv, motion
from d13_ccv import mean, cv
DEC = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA17_design/out/dec/final_%s_b0.5.d.yuv'
for cell in sys.argv[1].split(','):
    p_, W, H = yuv.CELLS[cell]; acc = {}
    for f in range(4, 8):
        S0 = yuv.read_frame(p_, W, H, f); Pt = yuv.read_frame(DEC % cell, W, H, f)[0]
        D1 = yuv.read_frame(DEC % cell, W, H, f - 1); D2 = yuv.read_frame(DEC % cell, W, H, f - 2)
        motion.BX = 64
        Vh = motion.derive(D1[0], D2[0], bx=64, lam=4); Vc = cv(Pt, D1[0], 2)
        L1 = mean(Pt, 2); nby, nbx = H // 8, W // 64
        best = np.full((nby, nbx), np.inf); Vb = Vh.copy()
        for base in (Vh, Vc):
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    V = base + np.array([dy, dx])
                    # block-wise (non-OBMC) shifted reference, compared at half resolution per block
                    P = np.zeros((H, W))
                    for by in range(nby):
                        for bxi in range(nbx):
                            pass
                    Pv = motion.predict(D1[0], V)          # OBMC prediction with this candidate everywhere
                    e = np.abs(mean(Pv, 2) - L1).reshape(nby, 4, nbx, 32).sum(axis=(1, 3))
                    take = e < best; best = np.where(take, e, best); Vb[take] = V[take]
        for k, V in (('hist', Vh), ('ccv2', Vc), ('ccv2r', Vb)):
            mse = [np.mean((motion.predict(D1[i], V, 1 if i == 0 else 2) - S0[i]) ** 2.0) for i in range(3)]
            acc.setdefault(k, np.zeros(3)); acc[k] += mse
    for k, m in acc.items():
        print('%-7s %-9s pred PSNR %.2f/%.2f/%.2f' % (cell, k, *(10 * np.log10(1023 ** 2 / (m / 4)))), flush=True)
