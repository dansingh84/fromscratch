import numpy as np, sys, pickle, yuv, ent, seq
cl, bpp, start, out = sys.argv[1], float(sys.argv[2]), sys.argv[3], sys.argv[4]
tabs = ent.Tables(start); new = ent.Tables()
p, W, H = yuv.TRAIN[cl]
s = seq.Seq(W, H, bpp, tabs, tilt=0.25, rho=0.35, bx=64, lam=4, refresh=False)
s.c.collect = True; tabs.add = new.add
for f in range(8):
    o, b, i = s.encode(yuv.read_frame(p, W, H, f))
    if f == 3: s2 = None
print(cl, bpp, 'bits %.0f over %d' % (b.sum(), i['over']), flush=True)
pickle.dump(new.cnt, open(out, 'wb'))
