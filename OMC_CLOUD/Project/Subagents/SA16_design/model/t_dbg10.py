import sys, os, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import omc16, yuv
from pyr2 import BANDS
path, W, H = yuv.CELLS['dng720']
g1 = omc16.Codec(W, H, S=4, bpp=0.5)
g1.encode(yuv.read_frame(path, W, H, 0))
os.environ['DBG_SLICE'] = '1'
g1.encode(yuv.read_frame(path, W, H, 1))
res, fin, holdg, mode = g1.dbg_last; k = 1
for pi, band in ((0, 'H5'), (1, 'LL'), (0, 'LL')):
    bs, rows = g1.rows_of(band, k); ql = res['Q'][pi][band]; cl = res['C'][pi][band]; qe = fin['E'][pi][band]; fe = fin['F'][pi][band]
    print(pi, band, 'blocks', bs, 'lane q != emitted q:', int((ql != qe).sum()), 'of', ql.size, '| lane C != final:', int((cl != fe).sum()))
    d = np.argwhere(ql != qe)
    for i, j in d[:6]:
        print('   at', (i, j), 'unit', j // g1.ucols(pi, band), 'lane q', ql[i, j], 'C', cl[i, j], '| emitted q', qe[i, j], 'F', fe[i, j], 'mode', mode[bs[i], j // g1.ucols(pi, band)], 'hold ll', holdg['ll'][bs[i], j // g1.ucols(pi, band)], 'ucls', g1.last['ucls'][j // g1.ucols(pi, band)])
print('--- context / mask diff')
P = int(g1.last['P'][1]); print('chosen P', P, 'Pe', g1.last['Pe'][1])
for key in ((0, 'H5'), (1, 'LL')):
    ql, cl, il, hl, bl = g1._lane_dbg[(P,) + key]; qe, ce, ie, he, be = g1._fin_dbg[key]
    print(key, 'ctx diff', int((cl != ce).sum()), 'inter diff', int((il != ie).sum()), 'hold diff', int((hl != he).sum()), 'bits lane %.1f emitted %.1f' % (bl.sum(), be.sum()))
    d = np.argwhere((cl != ce) | (il != ie) | (hl != he) | (np.abs(bl - be) > 0.01))
    for i, j in d[:5]: print('   at', (i, j), 'q', ql[i, j], qe[i, j], 'ctx', cl[i, j], ce[i, j], 'inter', il[i, j], ie[i, j], 'hold', hl[i, j], he[i, j], 'bits %.2f %.2f' % (bl[i, j], be[i, j]))
