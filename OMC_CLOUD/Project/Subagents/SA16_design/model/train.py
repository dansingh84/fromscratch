# static tANS tables trained on footage DISJOINT from every test cell (yuv.TRAIN), emitted symbols only.
import sys, pickle, numpy as np, glob
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import omc16, yuv
OUT = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/out/tables/'
import os; os.makedirs(OUT, exist_ok=True)
if sys.argv[1] == 'clip':
    ci = int(sys.argv[2]); init = sys.argv[3] if len(sys.argv) > 3 else None; nfr = int(sys.argv[4]) if len(sys.argv) > 4 else 4
    clip = yuv.TRAIN[ci]; tabs = omc16.Tables(init)
    for bpp in (0.5, 1.0):
        cod = omc16.Codec(1920, 1080, S=8, bpp=bpp, tabs=tabs); cod.train = True
        for t in range(nfr):
            cod.encode(yuv.read_frame(clip, 1920, 1080, t))
            print(clip.split('/')[-1], bpp, t, int(cod.stats['frame_bits']), cod.F, flush=True)
    pickle.dump(tabs.cnt, open(OUT + "cnt_%d_%s.pkl" % (ci, ("p1" if init is None else ("p3" if "p2" in init else "p2"))), "wb"))
elif sys.argv[1] == 'merge':
    tag = sys.argv[2]; tabs = omc16.Tables()
    for f in glob.glob(OUT + 'cnt_*_%s.pkl' % tag):
        for k, v in pickle.load(open(f, 'rb')).items():
            tabs.cnt[k] = tabs.cnt.get(k, 0) + v
    tabs.build(OUT + 'tables_%s.pkl' % tag)
    print('tables', len(tabs.len), 'symbols', int(sum(v.sum() for v in tabs.cnt.values())))
