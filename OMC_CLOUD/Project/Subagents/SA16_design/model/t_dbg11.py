import sys, os, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import omc16, yuv
path, W, H = yuv.CELLS['dng720']
g1 = omc16.Codec(W, H, S=4, bpp=0.5); g2 = omc16.Codec(W, H, S=4, bpp=0.5)
os.environ['DBG_SLICE'] = '157'
src = yuv.read_frame(path, W, H, 0); r1 = g1.encode(src)
r2 = g2.encode(r1)
k = 157; print('g1 Pe', g1.last['Pe'][k], 'g2 Pe', g2.last['Pe'][k], 'g2 P', g2.last['P'][k])
for key in ((0, 'HH1'), (0, 'LH1')):
    Pst = int(g1.last['Pe'][k]); ql, cl, il, hl, bl = g2._lane_dbg[(Pst,) + key]; qe, ce, ie, he, be = g1._fin_dbg[key]
    print(key, 'q diff', int((ql != qe).sum()), 'ctx diff', int((cl != ce).sum()), 'bits g2 lane %.1f g1 emitted %.1f' % (bl.sum(), be.sum()))
    d = np.argwhere((ql != qe) | (cl != ce) | (np.abs(bl - be) > 0.01))
    bs, rows = g1.rows_of(key[1], k)
    for i, j in d[:6]:
        print('   at', (i, j), 'q g2', ql[i, j], 'g1', qe[i, j], 'ctx', cl[i, j], ce[i, j], 'bits %.2f %.2f' % (bl[i, j], be[i, j]), '| final', g1.last['E'][key[0]][key[1]][rows][i, j])
