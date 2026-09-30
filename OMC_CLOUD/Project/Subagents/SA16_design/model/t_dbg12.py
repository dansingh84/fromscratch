import sys, os, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import omc16, yuv, pyr2
path, W, H = yuv.CELLS['dng720']
g1 = omc16.Codec(W, H, S=4, bpp=0.5); os.environ['DBG_SLICE'] = '157'
src = yuv.read_frame(path, W, H, 0); r1 = g1.encode(src)
k = 157
for pi in (0,):
    T = pyr2.analysis(r1[pi], g1.Lh[pi]); _, F, IV = pyr2.synthesis(T, g1.Lh[pi], 0, 1023)
    for band in ('LH1', 'HH1', 'HL1', 'LH2', 'H3'):
        ilo, ihi, f, rows = g1._fin_iv[(pi, band)]
        dlo = ilo != IV[band][0][rows]; dhi = ihi != IV[band][1][rows]; df = f != T[band][rows]
        print(band, 'ilo diff', int(dlo.sum()), 'ihi diff', int(dhi.sum()), 'final vs reanalysis diff', int(df.sum()))
        d = np.argwhere(dlo | dhi)
        for i, j in d[:3]:
            print('   at', (i, j), 'window ivl', (ilo[i, j], ihi[i, j]), 'frame ivl', (IV[band][0][rows][i, j], IV[band][1][rows][i, j]), 'final', f[i, j], 'reanalysis', T[band][rows][i, j])
print('--- replicate gen-2 quant for LH1 at slice 157, (0,295)')
pi, band, k = 0, 'LH1', 157
T = pyr2.analysis(r1[pi], g1.Lh[pi]); _, F, IV = pyr2.synthesis(T, g1.Lh[pi], 0, 1023)
bs, rows = g1.rows_of(band, k); D = g1.step(pi, band, 252); x = T[band][rows]
up = (T[band] == IV[band][1])[rows]; lo = (T[band] == IV[band][0])[rows]
i, j = 0, 295
print('x', x[i, j], 'D', D, 'ivl', (IV[band][0][rows][i, j], IV[band][1][rows][i, j]), 'up', up[i, j], 'lo', lo[i, j], 'Q', omc16.Q(np.array([x[i, j]]), D)[0])
g2 = omc16.Codec(W, H, S=4, bpp=0.5); Ts2 = [pyr2.analysis(r1[p], g2.Lh[p]) for p in range(3)]; MS = g2.boundary_masks(Ts2)
print('MS up/lo at that coef:', MS[0][pi][band][rows][i, j], MS[1][pi][band][rows][i, j])
q = g2.quant(pi, band, rows, x, 0, D, M=MS); print('g2.quant ->', q[i, j])
print('expo at 252:', omc16.expo(pi, band, 252), 'g1 Pe', g1.last['Pe'][k], 'g1 emitted', g1.last['E'][pi][band][rows][i, j])
