# SA18 generation chain: g1 (camera input) -> g2 reads g1's picture -> g3 reads g2's picture. Pictures and bits compared.
import numpy as np, sys, os, yuv, ent, seq
cell, bpp, N = sys.argv[1], float(sys.argv[2]), int(sys.argv[3])
ccv = int(os.environ.get('CCV', '2'))
p, W, H = yuv.CELLS[cell]; tabs = ent.Tables(os.environ.get('TABS', '../out/tab_h_r1.pkl'))
kw = dict(tilt=0.25, rho=0.35, bx=64, lam=4, still_hold=1, refresh=False, S=4 if H == 720 else 8)
g = [seq.Seq(W, H, bpp, tabs, **kw) for _ in range(3)]
for s in g: s.ccv = ccv; s.c.recoff = int(os.environ.get('RECOFF', '0'))
same = lambda a, b: sum(int((x != y).sum()) for x, y in zip(a, b))
nf = yuv.nframes(p, W, H)
for f in range(N):
    x = yuv.read_frame(p, W, H, f % nf)
    o1, b1, i1 = g[0].encode(x)
    o2, b2, i2 = g[1].encode(o1, read=True)
    o3, b3, i3 = g[2].encode(o2, read=True)
    print('f%2d gen2 diff %d bits %s | gen3 diff %d bits %s | g1 over %d max slice bits/B %.4f' % (
        f, same(o1, o2), 'same' if np.allclose(b1, b2) else 'DIFF %.0f' % (b2.sum() - b1.sum()), same(o2, o3),
        'same' if np.allclose(b2, b3) else 'DIFF', i1['over'], (b1 / (bpp * W * kw['S'])).max()), flush=True)
