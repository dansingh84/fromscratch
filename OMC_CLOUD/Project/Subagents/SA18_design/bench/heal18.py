# on-demand heal over a return path: slice k lost at frame t (decoder conceals: indices 0 -> prediction),
# the flag reaches the encoder after RT frames, the encoder codes rows [kS - m, (k+1)S + m] intra in frame t+RT+1.
# No scheduled wave (refresh=0). Reports per-frame damaged samples at the decoder.
import numpy as np, sys, yuv, ent, seq
cell, bpp, tabp, RT, t0, k = sys.argv[1], float(sys.argv[2]), sys.argv[3], int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6])
NL = int(sys.argv[7]) if len(sys.argv) > 7 else 1          # consecutive slices lost
N = t0 + RT + 5; p, W, H = yuv.CELLS[cell]; tabs = ent.Tables(tabp)
kw = dict(tilt=0.25, rho=0.35, bx=64, lam=4)
g = seq.Seq(W, H, bpp, tabs, refresh=False, still_hold=1, S=(4 if H == 720 else 8), **kw); g.ccv = 2; g.c.recoff = 2; d = seq.Decoder(g)
S = g.S; m = 16 + (RT + 1) * 8           # transform reach + vertical MC reach (RY=4 rows/frame, OBMC) per frame of delay
for f in range(N):
    x = yuv.read_frame(p, W, H, f % yuv.nframes(p, W, H))
    heal = (max(0, k * S - m), min(H, (k + NL) * S + m)) if f == t0 + RT + 1 else None
    o, b, i = g.encode(x, heal=heal); y = d.decode(i, lost=tuple(range(k, k + NL)) if f == t0 else ())
    diff = sum(int((a != c).sum()) for a, c in zip(o, y))
    rows = np.nonzero(np.any([ (a != c).any(1) for a, c in zip(o, y)], axis=0))[0]
    print('%s RT=%d f%2d %s damaged samples %7d rows %s  bits/target %.4f over %d' % (cell, RT, f, 'LOSS' if f == t0 else ('HEAL' if heal else '    '),
          diff, '%d..%d' % (rows.min(), rows.max()) if rows.size else '-', b.sum() / (bpp * W * H), i['over']), flush=True)
