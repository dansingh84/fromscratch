import sys, os, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import omc16, yuv
path, W, H = yuv.CELLS['dng720']; TAB = '../out/tables/tables_p2.pkl'
cod = omc16.Codec(W, H, S=4, bpp=0.5, tabs=omc16.Tables(TAB)); dref = None; join = 5
for t in range(18):
    src = yuv.read_frame(path, W, H, t % 12); rec = cod.encode(src)
    if t < join: continue
    if t == join: dref = [np.full(rec[p].shape, 512, np.int64) for p in range(3)]
    dec = cod.decode(cod.last, dref); d = dec[0] != rec[0]
    ucols = d.reshape(H, W // 32, 32).any(2)         # (H, units)
    per_unit = ucols.sum(0); regions = [int(per_unit[r * cod.Bw:(r + 1) * cod.Bw].sum()) for r in range(cod.Nc)]
    print('t', t, 'phi', cod.last['phi'], 'ucls band', np.nonzero(cod.last['ucls'] == 1)[0].tolist(), 'differing rows per region', regions,
          '| worst units', np.argsort(-per_unit)[:6].tolist(), per_unit[np.argsort(-per_unit)[:6]].tolist(), flush=True)
    dref = dec
