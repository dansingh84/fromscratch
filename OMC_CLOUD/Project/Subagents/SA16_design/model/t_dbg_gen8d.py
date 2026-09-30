import sys, os, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import omc16, yuv, pyr2
from pyr2 import BANDS, rows_per_block, group
path, W, H = yuv.CELLS['floor']; TAB = '../out/tables/tables_p2.pkl'
g1 = omc16.Codec(W, H, S=8, bpp=0.5, tabs=omc16.Tables(TAB)); g2 = omc16.Codec(W, H, S=8, bpp=0.5, tabs=omc16.Tables(TAB))
for t in range(2):
    src = yuv.read_frame(path, W, H, t); r1 = g1.encode(src); r2 = g2.encode(r1)
k = 20; u = 14; b = 40
print('hold g1', {g: bool(g1.last['holdg'][g][b, u]) for g in ('ll','mid','fine')}, 'g2', {g: bool(g2.last['holdg'][g][b, u]) for g in ('ll','mid','fine')}, 'Pu', g1.last['Pu'][b, u], g2.last['Pu'][b, u], 'PuP', g1._PuP[b, u], g2._PuP[b, u], 'static', g1._static[b, u], g2._static[b, u], 'Pe', g1.last['Pe'][k], g2.last['Pe'][k], 'P', g1.last['P'][k], g2.last['P'][k], 'stats g1', g1.stats.get('hold_flip'), 'g2', g2.stats.get('hold_flip'))
T1 = [pyr2.analysis(r1[p], g1.Lh[p]) for p in range(3)]; T2 = [pyr2.analysis(r2[p], g2.Lh[p]) for p in range(3)]
V = g1.last['V']; ucls, xp, Tp, static = g1.prepare(V, False, 1, ref=g1.ref2)
MP = g1.boundary_masks(Tp)
for pi in range(3):
    for band in ('LH1', 'HL1', 'HH1'):
        r = rows_per_block(band); c = g1.ucols(pi, band); rows = np.arange(r * b, r * b + r); cs = slice(c * u, c * u + c)
        f1 = T1[pi][band][rows][:, cs]; f2 = T2[pi][band][rows][:, cs]; x = Tp[pi][band][rows][:, cs]
        Dq = g1.step(pi, band, int(g1._PuP[b, u])); th = g1.hold_target(pi, band, rows, Tp[pi][band][rows], Dq * np.ones(Tp[pi][band][rows].shape, np.int64), MP)[:, cs]
        _, F1, IV1 = pyr2.synthesis(T1[pi], g1.Lh[pi], 0, 1023); ilo = IV1[band][0][rows][:, cs]; ihi = IV1[band][1][rows][:, cs]
        e1 = g1.last['E'][pi][band][rows][:, cs]; e2 = g2.last['E'][pi][band][rows][:, cs]
        d = (f1 != f2) | (e1 != e2) | (f1 != np.clip(th, ilo, ihi))
        print('plane', pi, band, 'Dq', Dq, 'f1==xp', int((f1 == x).sum()), '/', f1.size, 'f1==clip(th)', int((f1 == np.clip(th, ilo, ihi)).sum()), 'f2==clip(th)', int((f2 == np.clip(th, ilo, ihi)).sum()), 'f1!=f2', int((f1 != f2).sum()), 'e1!=e2', int((e1 != e2).sum()), 'MPup', int(MP[0][pi][band][rows][:, cs].sum()), 'MPlo', int(MP[1][pi][band][rows][:, cs].sum()))
        if d.any():
            i, j = np.argwhere(d)[0]; print('     at', (i, j), 'xp', x[i, j], 'th', th[i, j], 'ivl', (ilo[i, j], ihi[i, j]), 'f1', f1[i, j], 'f2', f2[i, j], 'e1', e1[i, j], 'e2', e2[i, j])
