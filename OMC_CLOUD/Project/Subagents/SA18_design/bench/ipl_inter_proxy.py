# PROXY screen, INTER: residual of the MC prediction from SA17's real decoded references (history vectors, OBMC),
# coded by AVG vs IPL transform in the residual domain (gain-normalised dead-zone, in-sample zeroth-order entropy per
# band; identical advantage for both arms). Frames 4..7. Reports bpp and PSNR of P + synth(q) per plane.
import numpy as np, sys, yuv, pyr, pyr_ipl, codec, motion
def ent_bits(q):
    a = np.abs(q); c = np.minimum(a, 64); v, n = np.unique(c, return_counts=True); p = n / n.sum()
    b = -(n * np.log2(p)).sum() + (a > 0).sum(); big = a[a >= 64]
    return b + ((2 * np.log2(big / 32.0)).sum() if big.size else 0)
DEC = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA17_design/out/dec/final_%s_b0.5.d.yuv'
motion.BX = 64
for cell in sys.argv[1].split(','):
    p_, W, H = yuv.CELLS[cell]
    rows = {}
    for f in range(4, 8):
        x = yuv.read_frame(p_, W, H, f); d1 = yuv.read_frame(DEC % cell, W, H, f - 1); d2 = yuv.read_frame(DEC % cell, W, H, f - 2)
        V = motion.derive(d1[0], d2[0], bx=64, lam=4)
        P = [motion.predict(d1[i], V, 1 if i == 0 else 2) for i in range(3)]
        for name, X in (('AVG', pyr), ('IPL', pyr_ipl)):
            codec.XF = X
            G = [codec.gains('pair', x[0].shape), codec.gains('pair', x[1].shape)]
            for D0 in (24, 34, 48, 68, 96):
                tot = 0; se = []
                for i in range(3):
                    r = x[i] - P[i]; T = X.analysis(r); g = G[0 if i == 0 else 1]; Vq = {}
                    for b, c in T.items():
                        D = max(1.0, D0 / np.sqrt(g[b]))
                        q = np.sign(c) * np.floor(np.abs(c) / D + 0.35); tot += ent_bits(q.astype(np.int64)); Vq[b] = np.round(q * D).astype(np.int64)
                    y, _, _ = X.synthesis(Vq, -10 ** 9, 10 ** 9, legal=False); rec = np.clip(P[i] + y, 4, 1019)
                    se.append(np.mean((rec - x[i]) ** 2.0))
                k = (name, D0); a = rows.setdefault(k, [0.0, np.zeros(3)]); a[0] += tot / (W * H); a[1] += np.array(se)
    for (name, D0), (bpp, se) in sorted(rows.items()):
        ps = 10 * np.log10(1023 ** 2 / (se / 4))
        print('%-7s %s D0=%3d bpp %.3f PSNR %.2f/%.2f/%.2f' % (cell, name, D0, bpp / 4, *ps), flush=True)
