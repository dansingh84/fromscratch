# intra-only A/B: code frames 2..5 of a cell as intra at exact CBR; NEG (mean, worst) + PSNR Y/Cb/Cr.
import numpy as np, sys, yuv, ent, seq, metrics
cell, bpp, tabp, tag = sys.argv[1], float(sys.argv[2]), sys.argv[3], sys.argv[4]
p, W, H = yuv.CELLS[cell]; tabs = ent.Tables(tabp)
s = seq.Seq(W, H, bpp, tabs, tilt=0.25, rho=0.35, bx=64, lam=4, refresh=False, S=4 if H == 720 else 8)
src = []; dec = []; mx = 0
for f in range(2, 6):
    x = yuv.read_frame(p, W, H, f); o, b, i = s.encode(x, force_intra=True); src.append(x); dec.append(o); mx = max(mx, b.sum() / (bpp * W * H))
r = metrics.summary(src, dec, W, H, first=0)
oob = sum(int(((d[k] < 4) | (d[k] > 1019)).sum()) for d in dec for k in range(3))
print('%s %s @%.2f intra NEG %.2f (worst %.2f) PSNR %.2f/%.2f/%.2f max bits/target %.4f oob %d' % (tag, cell, bpp, r['neg'], r['negmin'], *r['psnr'], mx, oob), flush=True)
