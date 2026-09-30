import numpy as np, yuv, ent, seq, codec
SA7 = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/'
path, W, H, lo, hi = SA7 + 'ext_10_422_l0.yuv', 512, 128, 0, 1023; tabs = ent.Tables('../out/tab_f1.pkl'); nf = yuv.nframes(path, W, H)
kw = dict(lo=lo, hi=hi, S=4, tilt=0.25, rho=0.35, bx=64, lam=4, still_hold=1, refresh=False)
g1 = seq.Seq(W, H, 1.0, tabs, **kw); g2 = seq.Seq(W, H, 1.0, tabs, **kw); g1.ccv = g2.ccv = 2; g1.c.recoff = g2.c.recoff = 2
for f in range(5):
    x = yuv.read_frame(path, W, H, f % nf); o1, b1, i1 = g1.encode(x); o2, b2, i2 = g2.encode(o1, read=True)
    if f == 4:
        print('V same', np.array_equal(i1['V'], i2['V']), 'Vc same', np.array_equal(i1['Vc'], i2['Vc']))
        print('l1d g1', i1['l1d'][24:30], 'g2', i2['l1d'][24:30], 'plans', i1['plans'][24:30])
        for p in range(3):
            for b in codec.BANDSP[p]:
                if not np.array_equal(i1['base'][p][b], i2['base'][p][b]): print('base differs', p, b)
        print('hdr diff?', b1[26] - b2[26])
import pyr
a = pyr.analysis(g1._p1[0], 2, 2)['LL']; b = pyr.analysis(o1[0], 2, 2)['LL']
d = np.nonzero(a != b); print('LL2 pass1 vs final differ at', len(d[0]), 'positions; rows', np.unique(d[0])[:20])
T1 = pyr.analysis(g1._p1[0]); T2 = pyr.analysis(o1[0])
for k in T1:
    n = int((T1[k] != T2[k]).sum())
    if n: print('band', k, 'differs', n)
i_p1 = g1._i1
for p in range(3):
    for b in ('LL', 'H5', 'H4', 'H3'):
        e1 = i_p1['exps'][(p, b)]; q1 = i_p1['Q0'][p][b]; v1 = i_p1['V0'][p][b]
        print(p, b, 'pass1 exps rows 18/28:', e1[18], e1[28], '| final emitted exps', i1['exps_emit'][(p, b)][18], i1['exps_emit'][(p, b)][28], i1['exps'][(p,b)][18], i1['exps'][(p,b)][28])
