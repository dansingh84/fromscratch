# SA19: diagnose SA18's rail breaks. Per frame: gen-2 picture/bit identity, and where bits differ (slice, plan, exps);
# per frame CBR prefix overs with the slices that overrun.
import numpy as np, sys, yuv, ent, seq, codec
SA7 = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/'
CELLS = {'cut24': (SA7 + 'cut24.yuv', 256, 64, 0, 1023), 'ext10': (SA7 + 'ext_10_422_l0.yuv', 512, 128, 0, 1023),
         'ext10l1': (SA7 + 'ext_10_422_l1.yuv', 512, 128, 4, 1019), 'gfx': (yuv.ARMS + 'cf_gfx_448x256_422_10.yuv', 448, 256, 4, 1019)}
tabs = ent.Tables(sys.argv[1]); cell = sys.argv[2]; bpp = float(sys.argv[3]); N = int(sys.argv[4]) if len(sys.argv) > 4 else 5
path, W, H, lo, hi = CELLS[cell]; nf = yuv.nframes(path, W, H)
kw = dict(lo=lo, hi=hi, S=8 if H % 8 == 0 and H > 720 else 4, tilt=0.25, rho=0.35, bx=64, lam=4, still_hold=1, refresh=False)
g1 = seq.Seq(W, H, bpp, tabs, **kw); g2 = seq.Seq(W, H, bpp, tabs, **kw); g1.ccv = g2.ccv = 2; g1.c.recoff = g2.c.recoff = 2
B = bpp * W * g1.S
for f in range(N):
    x = yuv.read_frame(path, W, H, f % nf); o1, b1, i1 = g1.encode(x); o2, b2, i2 = g2.encode(o1, read=True)
    pd = sum(int((a != b).sum()) for a, b in zip(o1, o2)); oob = sum(int(((o1[p] < lo) | (o1[p] > hi)).sum()) for p in range(3))
    cum = np.cumsum(b1); lim = B * np.arange(1, len(b1) + 1); ov = np.nonzero(cum > lim + 1e-6)[0]
    print('f%d intra=%s picdiff %d oob %d bits1 %.1f bits2 %.1f overs %d max(cum-lim) %.1f' % (f, i1['intra'], pd, oob, b1.sum(), b2.sum(), ov.size, (cum - lim).max()), flush=True)
    if ov.size: print('   over slices', ov[:20], 'b1', np.round(b1[ov[:8]], 1), 'B', B)
    if not np.allclose(b1, b2):
        d = np.nonzero(~np.isclose(b1, b2))[0]
        print('   bits differ slices', d, 'b1', np.round(b1[d], 2), 'b2', np.round(b2[d], 2))
        print('   plans1', i1['plans'][d], 'plans2', i2['plans'][d], 'l1d1', i1.get('l1d', [None]*999)[d] if i1.get('l1d') is not None else None, 'l1d2', i2.get('l1d')[d] if i2.get('l1d') is not None else None)
        for p in range(3):
            for b in codec.BANDSP[p]:
                q1, q2 = i1['Q'][p][b], i2['Q'][p][b]
                if q1.shape == q2.shape and not np.array_equal(q1, q2): print('   Q differs', p, b, int((q1 != q2).sum()))
        if 'Vc' in i1 and 'Vc' in i2: print('   Vc diff blocks', int((i1['Vc'] != i2['Vc']).any(-1).sum()), 'V diff', int((i1['V'] != i2['V']).any(-1).sum()))
