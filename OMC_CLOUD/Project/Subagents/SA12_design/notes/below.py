"""R1 cause test: is the residual slice-edge excess the missing context BELOW the slice?
Intra f8, final variant; below-context = (none: linear extrapolation) | (oracle: source rows of the next slice)
| (proxy: the co-located rows of frame f7 source = a zero-motion stand-in for the MC reference in inter frames).
Reports bits (entropy est), PSNR, v16, first/last row ratio per plane at one Qf."""
import sys, os, math, numpy as np
os.environ['HF_FAST'] = '1'; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hf, grid
path, sh, Qf = sys.argv[1], 16, float(sys.argv[2])
src = hf.load(path, 1920, 1080, 8, '422'); prv = hf.load(path, 1920, 1080, 7, '422')
L, nv, kH, kV = 5, 3, 's10', 's10a'
KLL = int(os.environ.get('KLL', '-1')); COARSE_LEV = int(os.environ.get('CLEV', '9')); COARSE_F = float(os.environ.get('CF', '0'))
MODES = os.environ.get('MODES', 'none,oracle,proxy').split(',')
LOSSLESS = os.environ.get('LOSSLESS', '').split(',')
for mode in MODES:
    tb = 0; out = []
    for pi, P in enumerate(src):
        H, W = P.shape; X = P[:1072].astype(np.int64).reshape(-1, sh, W); Pv = prv[pi][:1072].astype(np.int64)
        w = hf.weights(sh, W, L, nv, kH, kV); ks = hf.keys(L, nv); w[ks[-1]] *= 4.0 ** (-KLL)
        for kk in ks:
            if kk[0] >= COARSE_LEV and kk != ks[-1]: w[kk] *= 4.0 ** COARSE_F
        st = {k: max(1, int(round(2.0 ** round(Qf - 0.5 * math.log2(w[k]))))) for k in ks}
        for kk in ks:
            if ('%d%s' % kk) in LOSSLESS: st[kk] = 1
        rec = np.zeros_like(X); Q = []
        for k in range(X.shape[0]):
            ctx = None
            if k > 0: hf._slice0[0] = k - 1; ctx = hf.ctx_of(rec[k - 1:k], L, nv, kH)
            if mode != 'none' and k + 1 < X.shape[0]:
                hf._slice0[0] = k + 1
                nb = X[k + 1:k + 2] if mode == 'oracle' else Pv[(k + 1) * sh:(k + 2) * sh][None]
                bl = hf.ctx_below(nb, L, nv, kH)
                ctx = {lv: ((ctx[lv][0], ctx[lv][1]) if ctx else (None, None)) + bl[lv] for lv in bl}
            hf._slice0[0] = k
            C = hf.Coder('enc', st); rec[k:k + 1] = hf.rec_level(C, 1, L, nv, X[k:k + 1], np.zeros(X[k:k+1].shape, np.int64), np.full(X[k:k+1].shape, 1023, np.int64), kH, kV, ctx)
            Q.append(C.Q)
        tb += sum(hf.ent(np.concatenate([q[kk].ravel() for q in Q])) for kk in ks)
        R = rec.reshape(-1, W); e = (R - P[:1072]).astype(float)
        st_ = grid.stats(e); ph = [float(np.abs(e[j::sh]).mean()) for j in range(sh)]
        dy = np.abs(np.diff(e, axis=0)); ys = np.arange(1, e.shape[0]); p0 = dy[ys % 16 == 0].mean(); p8 = dy[ys % 16 == 8].mean(); oth = dy[(ys % 16 != 0) & (ys % 16 != 8)].mean()
        st_['v16'] = p0 / oth; st_['p8'] = p8 / oth
        out.append('%s psnr %.2f v16 %.2f p8 %.2f first %.2f last %.2f' % ('YUV'[pi], 10 * math.log10(1023 ** 2 / float((e ** 2).mean())), st_['v16'], st_['p8'], ph[0] / np.mean(ph), ph[-1] / np.mean(ph)))
    print(os.path.basename(path)[:10], 'Qf', Qf, '%-6s' % mode, 'bpp %.3f' % (tb / (1920 * 1072)), ' | '.join(out), flush=True)
