import sys, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import omc16, yuv, pyr2
from pyr2 import BANDS, group, rows_per_block
path, W, H = yuv.CELLS['dng720']
cod = omc16.Codec(W, H, S=4, bpp=0.5)
src = yuv.read_frame(path, W, H, 0)
rec = cod.encode(src, two_pass=False)
L = cod.last; eb = L['bits']
Ts = [pyr2.analysis(src[pi], cod.Lh[pi]) for pi in range(3)]
ucls, xp, Tp, static = cod.prepare(L['V'], True, 0)
cod.BND = cod.boundary_masks(Ts); cod.canon = False
parts = cod.build_C(Ts, Tp, L['P'], L['Pe'], L['mode'], L['hold'], L['Pu'], ucls, True, viaread=np.zeros(cod.NS, bool))
rec1, E1, F1 = cod.reconstruct(parts)
worst = None
for k in range(cod.NS):
    c, pe = cod.slice_bits(Ts, Tp, k, int(L['P'][k]), True, ucls, L['mode'], L['hold'], L['Pu'], L['V'], L['P'])
    d = eb[k] - c
    if worst is None or d > worst[0]: worst = (d, k, c, eb[k], pe, int(L['Pe'][k]))
print('worst slice discrepancy (emitted - costed):', worst)
d, k = worst[0], worst[1]
P = int(L['P'][k]); Pe = int(L['Pe'][k])
for pi in range(3):
    pc = 0 if pi == 0 else 1
    for band in BANDS(cod.Lh[pi]):
        bs, rows = cod.rows_of(band, k)
        if not bs.size: continue
        D = cod.step(pi, band, P); De = cod.step(pi, band, Pe); x = Ts[pi][band][rows]
        q = cod.quant(pi, band, rows, x, 0, D, raw=(band == 'LL')); qe = q // (De // D)
        cv1 = D * q; qE = E1[pi][band][rows]; cvE = F1[pi][band][rows]
        if band == 'LL': continue
        b1 = omc16.bits_map(cod.tabs, pc, band, qe, np.zeros(x.shape, bool), cv1, cod.T).sum()
        b2 = omc16.bits_map(cod.tabs, pc, band, qE, np.zeros(x.shape, bool), cvE, cod.T).sum()
        nq = int((qe != qE).sum()); ncv = int((cv1 != cvE).sum())
        if abs(b1 - b2) > 0.5 or nq:
            i = np.argwhere((qe != qE) | (cv1 != cvE))
            j = i[0] if len(i) else None
            print(pi, band, 'costed %.1f emitted %.1f  q diff %d cv diff %d' % (b1, b2, nq, ncv), 'D', D, 'De', De,
                  '' if j is None else 'ex: x=%d q=%d qE=%d cv=%d cvE=%d bnd=%s' % (x[j[0], j[1]], qe[j[0], j[1]], qE[j[0], j[1]], cv1[j[0], j[1]], cvE[j[0], j[1]], (bool(cod.BUP[pi][band][rows][j[0], j[1]]), bool(cod.BLO[pi][band][rows][j[0], j[1]]))))
