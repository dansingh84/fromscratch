# SA19 screen S1 (PROXY): does a two-past fused prediction reduce the fine-band inter residual?
# References = real bench decodes (SA17 EV-F 'final' decodes, 12 frames) -> they carry real quantisation noise.
# P1 = OBMC(D(t-1), V1); P2 = OBMC(D(t-2), V2); fused = (P1 + P2 + 1) >> 1.
# vectors: 'src' = searched with the SOURCE of frame t (oracle ceiling), 'hist' = D(t-1) vs D(t-2) history field
# (V2 = 2*V1 constant velocity, refined +-2 on the source as a ceiling).
# Output: per plane, per band group, residual energy sum (T(x) - T(P))^2 for P1 and fused, frames 3..11.
import numpy as np, sys, yuv, pyr, motion
cell, bpp = sys.argv[1], sys.argv[2]
p, W, H = yuv.CELLS[cell]
dp = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA17_design/out/dec/final_%s_b%s.d.yuv' % (cell, bpp)
N = 12
src = [yuv.read_frame(p, W, H, f) for f in range(N)]
dec = [yuv.read_frame(dp, W, H, f) for f in range(N)]
BX = 64; motion.BX = BX
grp = lambda b: 'L1' if b.endswith('1') else ('L2' if b.endswith('2') else 'coarse')
acc = {}
def add(key, v): acc[key] = acc.get(key, 0.0) + v
for t in range(3, N):
    x = src[t]; d1 = dec[t - 1]; d2 = dec[t - 2]
    V1 = motion.derive(d1[0], d2[0], bx=BX, lam=4)                     # history field (as TPP)
    nby, nbx = V1.shape[:2]; cy = (np.arange(nby) * 8 + 4)[:, None] + V1[..., 0]; cx = (np.arange(nbx) * BX + BX // 2)[None, :] + V1[..., 1]; V2 = V1 + V1[np.clip(cy // 8, 0, nby - 1), np.clip(cx // BX, 0, nbx - 1)]
    for pl in range(3):
        sx = 1 if pl == 0 else 2
        P1 = motion.predict(d1[pl], V1, sx); P2 = motion.predict(d2[pl], V2, sx); F = (P1 + P2 + 1) >> 1
        Tx = pyr.analysis(x[pl]); T1 = pyr.analysis(P1); T2 = pyr.analysis(P2); TF = pyr.analysis(F)
        for b in Tx:
            g = grp(b)
            add((pl, g, 'P1'), float(((Tx[b] - T1[b]) ** 2).sum()))
            add((pl, g, 'P2'), float(((Tx[b] - T2[b]) ** 2).sum()))
            add((pl, g, 'FU'), float(((Tx[b] - TF[b]) ** 2).sum()))
            # energy of the prediction itself in the band (blur check: a blurrier prediction has less fine energy)
            add((pl, g, 'E1'), float((T1[b] ** 2).sum())); add((pl, g, 'EF'), float((TF[b] ** 2).sum())); add((pl, g, 'EX'), float((Tx[b] ** 2).sum()))
print(cell, bpp)
for pl in range(3):
    for g in ('coarse', 'L2', 'L1'):
        r1, r2, rf = acc[(pl, g, 'P1')], acc[(pl, g, 'P2')], acc[(pl, g, 'FU')]
        print('  plane %d %-6s resid P1 %.3g  P2 %.3g  fused %.3g  (fused/P1 %.3f)  pred energy P1/src %.3f fused/src %.3f' % (
            pl, g, r1, r2, rf, rf / r1, acc[(pl, g, 'E1')] / acc[(pl, g, 'EX')], acc[(pl, g, 'EF')] / acc[(pl, g, 'EX')]))
