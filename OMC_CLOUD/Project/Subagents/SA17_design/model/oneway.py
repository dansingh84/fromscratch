# one-way link: fallback wave with cycle c, no return path. slice k lost at frame t0 at the decoder; count damaged frames.
import numpy as np, sys, yuv, ent, seq
cell, bpp, tabp, cyc, t0, k = sys.argv[1], float(sys.argv[2]), sys.argv[3], int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6])
p, W, H = yuv.CELLS[cell]; S = 4 if cell == 'dng720' else 8
g = seq.Seq(W, H, bpp, ent.Tables(tabp), refresh=True, cycle=cyc, still_hold=1, tilt=0.25, rho=0.35, bx=64, lam=4, S=S)
d = seq.Decoder(g)
for f in range(t0 + 3 * cyc + 3):
    x = yuv.read_frame(p, W, H, f % yuv.nframes(p, W, H)); o, b, i = g.encode(x)
    y = d.decode(i, lost=(k,) if f == t0 else ())
    print('%s c=%d f%2d phi %s %s damaged %d' % (cell, cyc, f, i.get('phi'), 'LOSS' if f == t0 else '    ', sum(int((a != c).sum()) for a, c in zip(o, y))), flush=True)
