import numpy as np, yuv, ent, tpp
path, W, H, lo, hi = yuv.ARMS + 'cf_gfx_448x256_422_10.yuv', 448, 256, 4, 1019
tabs = ent.Tables('../out/tab_f0.pkl'); kw = dict(lo=lo, hi=hi, S=8, tilt=0.25, rho=0.35, cheap=1)
g1 = tpp.TPP(W, H, 0.5, tabs, **kw); g2 = tpp.TPP(W, H, 0.5, tabs, auto=1, **kw)
orig = g2.try_read
def tr(src, base, im, vb):
    c = g2.c
    try: plans, Q, bits = c.read(src, base, im, vb)
    except AssertionError as e: print('  read assert', e); return None
    emin = np.array([min(c.E[k].values()) for k in plans]); B = g2.bpp * g2.W * g2.S
    cum = np.cumsum(bits) - B * np.arange(1, len(bits) + 1)
    print('  slices emin<1: %d, prefix excess max %.1f (slices over %d), plans %s' % ((emin < 1).sum(), cum.max(), (cum > 1e-6).sum(), plans[:8]))
    return orig(src, base, im, vb)
g2.try_read = tr
for f in range(3):
    x = yuv.read_frame(path, W, H, f); o1, b1, i1 = g1.encode(x)
    print('frame', f, 'gen1 plans', i1['plans'][:8], 'bits', round(b1.sum()))
    o2, b2, i2 = g2.encode(o1)
    print('  gen2 hop', i2.get('hop', False), 'diff', sum(int((a != b).sum()) for a, b in zip(o1, o2)), 'bits', round(b2.sum()))
