# PROXY screen (in-sample zeroth-order entropy per band, both transforms get the same advantage): IPL vs AVG intra.
import numpy as np, sys, yuv, pyr, pyr_ipl, codec
def ent_bits(q):
    a = np.abs(q); c = np.minimum(a, 64); v, n = np.unique(c, return_counts=True); p = n / n.sum()
    b = -(n * np.log2(p)).sum() + (a > 0).sum(); big = a[a >= 64]
    return b + ((2 * np.log2(big / 32.0)).sum() if big.size else 0)
for cell in sys.argv[1].split(','):
    p_, W, H = yuv.CELLS[cell]; fr = yuv.read_frame(p_, W, H, 3)
    for name, X in (('AVG', pyr), ('IPL', pyr_ipl)):
        codec.XF = X
        G = [codec.gains('pair', fr[0].shape), codec.gains('pair', fr[1].shape)]
        for D0 in (16, 24, 36, 54, 80):
            tot = 0; ps = []
            for i, x in enumerate(fr):
                T = X.analysis(x); g = G[0 if i == 0 else 1]; V = {}
                for b, c in T.items():
                    if b == 'LL':
                        V[b] = c; tot += 0; continue          # LL coded losslessly-ish in both (tiny)
                    D = max(1, int(2 ** np.round(np.log2(D0 / np.sqrt(g[b])))))
                    q = np.sign(c) * np.floor(np.abs(c) / D + 0.35); tot += ent_bits(q.astype(np.int64)); V[b] = (q * D).astype(np.int64)
                y, _, _ = X.synthesis(V, 4, 1019); ps.append(yuv.psnr(x, y))
            print('%-7s %s D0=%3d bpp %.3f PSNR %.2f/%.2f/%.2f' % (cell, name, D0, tot / (W * H), *ps), flush=True)
