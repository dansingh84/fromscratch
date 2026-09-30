import sys, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import omc16, yuv, pyr2
from pyr2 import BANDS, group, rows_per_block
path, W, H = yuv.CELLS['dng720']
cod = omc16.Codec(W, H, S=4, bpp=0.5)
src = yuv.read_frame(path, W, H, 0)
rec = cod.encode(src)
E = cod.last['E']; Pe = cod.last['Pe']
C = cod.build_C(E, [None]*3, Pe, cod.last['mode'], cod.last['holdg'], cod.last['Pu'], cod.last['ucls'], True)
pi = 0; Lh = 5
xr, Fw, IVw = pyr2.synthesis(C[pi], Lh, 0, 1023)     # whole-frame decode finals
bad = 0
for k in range(cod.NS):
    b0, b1 = cod.window(k)
    for mode_ in ('zeros_later', 'true_later'):
        Cw = {}
        for band in BANDS(Lh):
            r = rows_per_block(band); rows = np.arange(r * b0, r * b1); carr = np.repeat(cod.carrier[group(band)][b0:b1], r)
            later = carr > k
            Cw[band] = np.where(later[:, None] & (mode_ == 'zeros_later'), 0, C[pi][band][rows])   # decoded C values (finals-equivalent)
        _, Fk, IVk = pyr2.synthesis(Cw, Lh, 0, 1023)
        for band in BANDS(Lh):
            r = rows_per_block(band); rows = np.arange(r * b0, r * b1); carr = np.repeat(cod.carrier[group(band)][b0:b1], r); cur = carr == k
            d = Fk[band][cur] != Fw[band][rows][cur]
            if d.any():
                i, j = np.argwhere(d)[0]
                print('slice', k, mode_, band, 'mismatch', int(d.sum()), 'window F', int(Fk[band][cur][i, j]), 'frame F', int(Fw[band][rows][cur][i, j]),
                      'ivl window', (int(IVk[band][0][cur][i, j]), int(IVk[band][1][cur][i, j])), 'ivl frame', (int(IVw[band][0][rows][cur][i, j]), int(IVw[band][1][rows][cur][i, j])))
                bad += 1
                break
        if bad > 6: break
    if bad > 6: break
print('done')
