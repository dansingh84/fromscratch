# train static tables on footage DISJOINT from every test cell (yuv.TRAIN)
import numpy as np, sys, pickle, codec, yuv, ent
def prior_tables():
    t = ent.Tables()
    for p in (0, 1):
        for g in range(8):
            for inter in (0, 1):
                a = np.zeros((ent.NCTX, ent.NC))
                for x in range(ent.NCTX): a[x] = 2.0 ** (-np.arange(ent.NC) * (1.5 - 0.3 * x)) * 1000
                t.cnt[(p, g, inter)] = a
    t.build(); return t
if __name__ == '__main__':
    out = sys.argv[1]; backend = sys.argv[2]; rounds = int(sys.argv[3])
    tilt = float(sys.argv[4]) if len(sys.argv) > 4 else 0.0
    tabs = prior_tables()
    clips = ['bos', 'city', 'rsg', 'traffic', 'winter']
    for r in range(rounds):
        new = ent.Tables()
        for cl in clips:
            p, W, H = yuv.TRAIN[cl]
            c = codec.Codec(W, H, S=8, backend=backend, tabs=tabs, tilt=tilt); c.tabs = tabs
            for f in (0, 9):
                src = yuv.read_frame(p, W, H, f)
                for bpp in (0.5, 1.0, 2.0, 3.0):
                    c.collect = True; ct = ent.Tables(); c.tabs = tabs
                    # collect into 'new' by swapping add target
                    tabs_add = tabs.add; tabs.add = new.add
                    out_, bits, info = c.code_frame(src, bpp=bpp)
                    tabs.add = tabs_add
                    print(r, cl, f, bpp, 'bits %.0f target %.0f over %d' % (bits.sum(), bpp * W * H, info['over']), flush=True)
        new.build(out); tabs = ent.Tables(out)
