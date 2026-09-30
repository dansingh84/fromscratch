# tuning on TRAINING footage only (disjoint from test cells). usage: tune.py TABLES TAG clip,clip bpp,bpp key=val...
import numpy as np, sys, json, os, yuv, ent, seq, metrics
tabp, tag, clips, bpps = sys.argv[1], sys.argv[2], sys.argv[3].split(','), [float(b) for b in sys.argv[4].split(',')]
kw = {}; skw = {}
for a in sys.argv[5:]:
    k, v = a.split('=')
    if k in ('refresh', 'clean', 'S', 'cycle', 'bx', 'lam', 'still_hold', 'ry', 'ztol'): skw[k] = int(v)
    elif k == 'l1k': skw[k] = float(v)
    elif k == 'rho_still': skw[k] = float(v)
    else: kw[k] = float(v)
tabs = ent.Tables(tabp); NF = 8
for cl in clips:
    p, W, H = yuv.TRAIN[cl]
    for bpp in bpps:
        s = seq.Seq(W, H, bpp, tabs, **skw, **kw); src = []; dec = []
        for f in range(NF):
            x = yuv.read_frame(p, W, H, f); o, b, i = s.encode(x); src.append(x); dec.append(o)
        r = metrics.summary(src, dec, W, H)
        print('%s %s @%.1f NEG %.3f worst %.3f PSNR %.2f/%.2f/%.2f' % (tag, cl, bpp, r['neg'], r['negmin'], *r['psnr']), flush=True)
