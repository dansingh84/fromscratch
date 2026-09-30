import sys, os, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import omc16, yuv, pyr2
from pyr2 import BANDS, rows_per_block, group
path, W, H = yuv.CELLS['floor']; TAB = '../out/tables/tables_p2.pkl'
g1 = omc16.Codec(W, H, S=8, bpp=0.5, tabs=omc16.Tables(TAB)); g2 = omc16.Codec(W, H, S=8, bpp=0.5, tabs=omc16.Tables(TAB))
for t in range(2):
    src = yuv.read_frame(path, W, H, t); r1 = g1.encode(src); r2 = g2.encode(r1)
k = 103; u = 14
T1 = [pyr2.analysis(r1[p], g1.Lh[p]) for p in range(3)]; T2 = [pyr2.analysis(r2[p], g2.Lh[p]) for p in range(3)]
print('ucls[14]', g1.last['ucls'][u], 'phi', g1.last['phi'], 'holds unit 14 blocks 206,207:', {g: g1.last['holdg'][g][206:208, u].tolist() for g in ('ll','mid','fine')}, 'Pu', g1.last['Pu'][206:208, u].tolist(), 'mode', g1.last['mode'][206:208, u].tolist(), 'static', g1._static[206:208, u].tolist())
for pi in range(3):
    for band in BANDS(g1.Lh[pi]):
        bs, rows = g1.rows_of(band, k)
        if not bs.size: continue
        c = g1.ucols(pi, band); cs = slice(c * u, c * u + c)
        e1 = g1.last['E'][pi][band][rows][:, cs]; e2 = g2.last['E'][pi][band][rows][:, cs]
        f1 = T1[pi][band][rows][:, cs]; f2 = T2[pi][band][rows][:, cs]
        if not np.array_equal(e1, e2) or not np.array_equal(f1, f2):
            i, j = np.argwhere((e1 != e2) | (f1 != f2))[0]
            print('plane', pi, band, 'blocks', bs.tolist(), 'sym diff', int((e1 != e2).sum()), 'final diff', int((f1 != f2).sum()), 'first', (i, j), 'g1 q/final', e1[i, j], f1[i, j], 'g2 q/final', e2[i, j], f2[i, j])
