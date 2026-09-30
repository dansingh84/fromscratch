# generation chain + mid-stream JOIN + packet LOSS on one cell. universal encoders downstream.
import numpy as np, sys, yuv, ent, seq
cell, bpp, tabp, jf, lf, ls = sys.argv[1], float(sys.argv[2]), sys.argv[3], int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6])
N = int(sys.argv[7]) if len(sys.argv) > 7 else 12
p, W, H = yuv.CELLS[cell]; tabs = ent.Tables(tabp)
g1 = seq.Seq(W, H, bpp, tabs); g2 = seq.Seq(W, H, bpp, tabs); g2.universal = True
g3 = seq.Seq(W, H, bpp, tabs); g3.universal = True
gj = seq.Seq(W, H, bpp, tabs); gj.universal = True          # joins at frame jf
dl = seq.Decoder(g1)
same = lambda a, b: sum(int((x != y).sum()) for x, y in zip(a, b))
for f in range(N):
    x = yuv.read_frame(p, W, H, f % yuv.nframes(p, W, H))
    o1, b1, i1 = g1.encode(x)
    o2, b2, i2 = g2.encode(o1); o3, b3, i3 = g3.encode(o2)
    oj = gj.encode(o1)[0] if f >= jf else None
    d = dl.decode(i1, lost=(ls,) if f == lf else ())
    print('f%2d gen2 diff %d bits %s | gen3 diff %d | join diff %s lock %s | loss-decoder diff %d | g1 over %d' % (
        f, same(o1, o2), 'same' if np.allclose(b1, b2) else 'DIFF', same(o2, o3), same(o1, oj) if oj is not None else '-',
        gj.lock, same(o1, d), i1['over']), flush=True)
