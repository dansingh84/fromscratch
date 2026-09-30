# SA18 legality + exactness on rail extremes with the final configuration (cfv2 + bank + hold1):
# out-of-range samples, generation-2 picture/bit identity (re-encoder = canonical reading), CBR prefix overs.
import numpy as np, sys, os, yuv, ent, seq
SA7 = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/'
CELLS = {'cut24': (SA7 + 'cut24.yuv', 256, 64, 0, 1023), 'ext10': (SA7 + 'ext_10_422_l0.yuv', 512, 128, 0, 1023),
         'ext10l1': (SA7 + 'ext_10_422_l1.yuv', 512, 128, 4, 1019), 'gfx': (yuv.ARMS + 'cf_gfx_448x256_422_10.yuv', 448, 256, 4, 1019),
         'dng720': (yuv.CELLS['dng720'][0], 1280, 720, 4, 1019)}
tabs = ent.Tables(sys.argv[1])
for cell in sys.argv[2].split(','):
    path, W, H, lo, hi = CELLS[cell]; nf = yuv.nframes(path, W, H); N = 5
    for bpp in (0.25, 0.5, 1.0, 2.0):
        kw = dict(lo=lo, hi=hi, S=8 if H % 8 == 0 and H > 720 else 4, tilt=0.25, rho=0.35, bx=64, lam=4, still_hold=1, refresh=False)
        g1 = seq.Seq(W, H, bpp, tabs, **kw); g2 = seq.Seq(W, H, bpp, tabs, **kw); g1.ccv = g2.ccv = 2; g1.c.recoff = g2.c.recoff = 2
        st = dict(oob=0, gen2=0, bitsdiff=0, n=0, over=0)
        for f in range(N):
            x = yuv.read_frame(path, W, H, f % nf); o1, b1, i1 = g1.encode(x); o2, b2, i2 = g2.encode(o1, read=True)
            st['over'] += i1['over']; st['gen2'] += sum(int((a != b).sum()) for a, b in zip(o1, o2)); st['bitsdiff'] += int(not np.allclose(b1, b2))
            for p in range(3):
                st['oob'] += int(((o1[p] < lo) | (o1[p] > hi)).sum()); st['n'] += o1[p].size
        print('%-8s @%.2f  frames %d: out-of-range %d / %d | gen-2 differing samples %d, frames with different bits %d | CBR prefix overs %d' % (
            cell, bpp, N, st['oob'], st['n'], st['gen2'], st['bitsdiff'], st['over']), flush=True)
