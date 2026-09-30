import sys, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import omc16, yuv, pyr2
from pyr2 import BANDS, group, rows_per_block
path, W, H = yuv.CELLS['dng720']
cod = omc16.Codec(W, H, S=4, bpp=0.5)
src = yuv.read_frame(path, W, H, 0)
# monkeypatch to capture Fc after encode
orig_encode = cod.encode
rec = cod.encode(src)
print('stats', cod.stats)
# rebuild Fc from last E via build_C (decoder path) and compare with the whole-frame synthesis
E = cod.last['E']; Pe = cod.last['Pe']
C = cod.build_C(E, [None]*3, Pe, cod.last['mode'], cod.last['holdg'], cod.last['Pu'], cod.last['ucls'], True)
for pi in range(3):
    xr, Fw, IVw = pyr2.synthesis(C[pi], cod.Lh[pi], 0, 1023)
    d = xr != rec[pi]
    print('plane', pi, 'decode != rec samples:', int(d.sum()))
    for band in BANDS(cod.Lh[pi]):
        # C values vs finals: where does the clamp act on the decoded C?
        clamped = Fw[band] != C[pi][band]
        if clamped.any():
            i, j = np.argwhere(clamped)[0]; r = rows_per_block(band); b = i // r; k = cod.carrier[group(band)][b]
            print('   band', band, 'clamped at decode:', int(clamped.sum()), 'first', (i, j), 'block', b, 'slice', k, 'C', int(C[pi][band][i, j]), 'F', int(Fw[band][i, j]), 'ivl', (int(IVw[band][0][i, j]), int(IVw[band][1][i, j])), 'E', int(E[pi][band][i, j]), 'Dq', cod.step(pi, band, int(Pe[k])))
    break
