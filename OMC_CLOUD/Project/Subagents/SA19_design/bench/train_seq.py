# train intra+inter tables with the sequence codec on footage DISJOINT from all test cells
import numpy as np, sys, codec, yuv, ent, seq, train
out, backend, rounds, start = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
kw = {}
for a in sys.argv[5:]:
    k, v = a.split('='); kw[k] = float(v)
tabs = ent.Tables(start) if start != 'prior' else train.prior_tables()
# inter keys missing in an intra-only start: copy intra lengths as a first guess
for k in list(tabs.len):
    for inter in (0, 1):
        for eb in range(ent.NEB):
            k2 = (k[0], k[1], inter, eb)
            if k2 not in tabs.len: tabs.len[k2] = tabs.len[k].copy()
clips = ['bos', 'city', 'rsg', 'traffic', 'winter']
NF = 8
for r in range(rounds):
    new = ent.Tables()
    for cl in clips:
        p, W, H = yuv.TRAIN[cl]
        for bpp in (0.5, 1.0, 2.0):
            s = seq.Seq(W, H, bpp, tabs, backend=backend, **kw)
            s.c.collect = True
            add = tabs.add; tabs.add = new.add
            for f in range(NF):
                o, bits, info = s.encode(yuv.read_frame(p, W, H, f))
            tabs.add = add
            print(r, cl, bpp, 'last frame bits %.0f over %d' % (bits.sum(), info['over']), flush=True)
    new.build(out); tabs = ent.Tables(out)
