# intra A/B at REAL code lengths: NEG (all frames coded intra, frames 0..N-1), PSNR, bits; plus rail legality stats
import numpy as np, sys, yuv, ent, seq, pyr, codec, metrics
lim = int(sys.argv[1]); tabs = ent.Tables(sys.argv[2]); pyr.LIMIT = bool(lim)
for cell in sys.argv[3].split(','):
    path, W, H = yuv.CELLS[cell]
    for bpp in (0.5, 1.0):
        src = []; dec = []; bits = 0
        for f in (0, 4, 8):
            g = seq.Seq(W, H, bpp, tabs); x = yuv.read_frame(path, W, H, f); o, b, i = g.encode(x)
            src.append(x); dec.append(o); bits += b.sum()
        r = metrics.summary(src, dec, W, H, first=0)
        print('LIMIT=%d %s @%.1f intra: NEG %.2f (worst %.2f) PSNR %.2f/%.2f/%.2f bits/target %.4f' % (lim, cell, bpp, r['neg'], r['negmin'], *r['psnr'], bits / (3 * bpp * W * H)), flush=True)
