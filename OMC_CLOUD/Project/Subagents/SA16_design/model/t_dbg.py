import sys, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import omc16, yuv, pyr2
from pyr2 import BANDS, group, rows_per_block
path, W, H = yuv.CELLS['dng720']
cod = omc16.Codec(W, H, S=4, bpp=0.5)
src = yuv.read_frame(path, W, H, 0)
rec = cod.encode(src, two_pass=False)
P1 = cod.last['P']; E1 = cod.last['E']
Tr = [pyr2.analysis(rec[pi], cod.Lh[pi]) for pi in range(3)]
ucls, xp, Tp, static = cod.prepare(cod.last['V'], True, 0)
# what does the reading say per slice?
cod.BND = cod.boundary_masks(Tr)
bad = 0
for k in range(cod.NS):
    Pst = cod.reading_plan(Tr, Tp, k, True, ucls, static)
    if Pst < P1[k]:
        bad += 1
        if bad <= 3:
            print('slice', k, 'P1', P1[k], 'reading', Pst)
            # find offending coefficients
            for pi in range(3):
                for band in BANDS(cod.Lh[pi]):
                    bs, rows = cod.rows_of(band, k)
                    if not bs.size: continue
                    x = Tr[pi][band][rows]; e = omc16.expo(pi, band, int(P1[k])); v = cod.vof(pi, band, rows, x)
                    m = v < e
                    if m.any():
                        i = np.argwhere(m)[0]; r0 = rows[i[0]]
                        print('  plane', pi, band, 'e', e, 'n_bad', int(m.sum()), 'value', int(x[i[0], i[1]]), 'emitted q', int(E1[pi][band][r0, i[1]]),
                              'src coef', int(pyr2.analysis(src[pi], cod.Lh[pi])[band][r0, i[1]]), 'up/lo', bool(cod.BUP[pi][band][r0, i[1]]), bool(cod.BLO[pi][band][r0, i[1]]))
print('slices with finer reading than P1:', bad, 'of', cod.NS)
# run pass 2 explicitly
Pk2, mode2, hold2, Pu2, costs2 = cod.plan_pass(Tr, Tp, True, ucls, static, cod.last['V'], 'p2')
print('viaread', int(cod.viaread.sum()), 'P2==P1', int((Pk2 == P1).sum()))
parts2 = cod.build_C(Tr, Tp, Pk2, mode2, hold2, Pu2, ucls, True, viaread=cod.viaread)
rec2, E2, _ = cod.reconstruct(parts2)
for pi in range(3):
    d = rec2[pi] != rec[pi]; print('plane', pi, 'differing samples', int(d.sum()))
    if d.any():
        ys, xs = np.nonzero(d); print('   first at', ys[0], xs[0], 'slice', ys[0] // 4)
print('--- final value differences per band')
parts1 = cod.build_C([pyr2.analysis(src[pi], cod.Lh[pi]) for pi in range(3)], Tp, P1, cod.last['mode'], cod.last['hold'], cod.last['Pu'], ucls, True, viaread=np.zeros(cod.NS, bool))
rec1b, E1b, F1 = cod.reconstruct(parts1)
rec2, E2, F2 = cod.reconstruct(parts2)
assert all(np.array_equal(rec1b[p], rec[p]) for p in range(3))
for pi in range(3):
    for band in BANDS(cod.Lh[pi]):
        d = F1[pi][band] != F2[pi][band]
        if d.any():
            i = np.argwhere(d)[0]; r0, c0 = i
            r = rows_per_block(band); b = r0 // r; k = cod.carrier[group(band)][b]
            C2, base2, D2, Q2, _, _ = parts2[pi]; C1, base1, D1, Q1, _, _ = parts1[pi]
            _, F_, IV = pyr2.synthesis(Tr[pi], cod.Lh[pi], 0, 1023)
            print('plane', pi, band, 'ndiff', int(d.sum()), 'at', (r0, c0), 'slice', k, 'P1', P1[k], 'P2', Pk2[k], 'viaread', cod.viaread[k],
                  '| pass1 final', int(F1[pi][band][r0, c0]), 'D1', int(D1[band][r0, c0]), 'q1', int(Q1[band][r0, c0]),
                  '| pass2 final', int(F2[pi][band][r0, c0]), 'D2', int(D2[band][r0, c0]), 'q2', int(Q2[band][r0, c0]), 'C2', int(C2[band][r0, c0]),
                  '| Tr value', int(Tr[pi][band][r0, c0]), 'ivl', (int(IV[band][0][r0, c0]), int(IV[band][1][r0, c0])), 'up/lo', bool(cod.BUP[pi][band][r0, c0]), bool(cod.BLO[pi][band][r0, c0]),
                  'expo2', omc16.expo(pi, band, int(Pk2[k])), 'val', int(omc16.val2(Tr[pi][band][r0, c0])))
