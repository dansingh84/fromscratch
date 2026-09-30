import numpy as np, sys, yuv, ent, seq
SA7 = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/'
C = {'ext10': (SA7 + 'ext_10_422_l0.yuv', 512, 128, 0, 1023), 'gfx': (yuv.ARMS + 'cf_gfx_448x256_422_10.yuv', 448, 256, 4, 1019),
     'cut24': (SA7 + 'cut24.yuv', 256, 64, 0, 1023)}
cell, bpp = sys.argv[1], float(sys.argv[2]); path, W, H, lo, hi = C[cell]; tabs = ent.Tables('../out/tab_f1.pkl'); nf = yuv.nframes(path, W, H)
kw = dict(lo=lo, hi=hi, S=4, tilt=0.25, rho=0.35, bx=64, lam=4, still_hold=1, refresh=False)
g1 = seq.Seq(W, H, bpp, tabs, **kw); g2 = seq.Seq(W, H, bpp, tabs, **kw); g1.ccv = g2.ccv = 2; g1.c.recoff = g2.c.recoff = 2
B = bpp * W * 4
for f in range(5):
    x = yuv.read_frame(path, W, H, f % nf); o1, b1, i1 = g1.encode(x); o2, b2, i2 = g2.encode(o1, read=True)
    cum = np.cumsum(b1); lim = B * np.arange(1, len(b1) + 1); ov = np.nonzero(cum > lim + 1e-6)[0]
    ch = i1.get('chosen'); ex = (b1 - ch) if ch is not None and len(ch) == len(b1) else np.zeros(1)
    print('   emitted-chosen max %.1f, slices >16: %d' % (ex.max(), int((ex > 16).sum())))
    print(f, 'intra' if i1['intra'] else 'inter', 'overs', len(ov), 'first', ov[:3], 'max slice/B %.3f' % (b1 / B).max(), 'sum/target %.4f' % (b1.sum() / (B * len(b1))),
          'bits same' if np.allclose(b1, b2) else 'bits diff: slices %s d %s' % (np.nonzero(~np.isclose(b1, b2))[0][:5], (b2 - b1)[~np.isclose(b1, b2)][:5]),
          'plans same' if np.array_equal(i1['plans'], i2['plans']) else 'plans diff', 'l1d same' if np.array_equal(i1.get('l1d'), i2.get('l1d')) else 'l1d diff')
