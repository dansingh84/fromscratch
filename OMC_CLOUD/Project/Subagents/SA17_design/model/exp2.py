# E2: plain clip at the output + gen-2 reading by nearest-lattice rounding. How often does the reading miss?
import numpy as np, sys, xf, yuv
SA7 = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/'
CELLS = {'gfx': (yuv.ARMS + 'cf_gfx_448x256_422_10.yuv', 448, 256, [0, 1, 2]),
         'cut24': (SA7 + 'cut24.yuv', 256, 64, [0, 5, 10]),
         'ext10': (SA7 + 'ext_10_422_l0.yuv', 512, 128, [0, 1, 2]),
         'ext10l1': (SA7 + 'ext_10_422_l1.yuv', 512, 128, [0, 1, 2]),
         'dng720': (yuv.CELLS['dng720'][0], 1280, 720, [3])}
vf, hf = sys.argv[1], sys.argv[2]; lo, hi = int(sys.argv[3]), int(sys.argv[4])
Lh = 5
for cell in sys.argv[5].split(','):
    path, W, H, frs = CELLS[cell]
    Lh_ = min(Lh, int(np.log2(W // 2 // 8)) + 1)
    for D0 in (16, 32, 64, 128, 256):
        st = dict(pix=0, clip=0, oob=0, mism=0, coef=0, pixdiff=0, maxo=0)
        for f in frs:
            for x in yuv.read_frame(path, W, H, f):
                T = xf.analysis(x - 512, 2, Lh_, vf, hf); G = xf.gains(x.shape, 2, Lh_, vf, hf)
                R = {}; Q = {}
                for b, c in T.items():
                    D = max(1.0, D0 / np.sqrt(G[b])); q = (np.sign(c) * np.floor(np.abs(c) / D + 0.4)).astype(np.int64)
                    Q[b] = (q, D); R[b] = np.round(q * D).astype(np.int64)
                Y = xf.synthesis(R, 2, Lh_, vf, hf) + 512
                Dp = np.clip(Y, lo, hi)
                st['pix'] += Y.size; st['clip'] += int((Dp != Y).sum()); st['maxo'] = max(st['maxo'], int(np.abs(Dp - Y).max()))
                T2 = xf.analysis(Dp - 512, 2, Lh_, vf, hf); R2 = {}
                for b in T2:
                    q, D = Q[b]; q2 = np.round(T2[b] / D).astype(np.int64)
                    st['mism'] += int((q2 != q).sum()); st['coef'] += q.size; R2[b] = np.round(q2 * D).astype(np.int64)
                Y2 = np.clip(xf.synthesis(R2, 2, Lh_, vf, hf) + 512, lo, hi)
                st['pixdiff'] += int((Y2 != Dp).sum())
        print('%s V%s H%s D0=%3d clipped %d/%d (max overshoot %d)  gen2 index mismatches %d  gen2 pixels differing %d' % (
            cell, vf, hf, D0, st['clip'], st['pix'], st['maxo'], st['mism'], st['pixdiff']), flush=True)
