import sys, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import omc16, yuv, pyr2
from pyr2 import BANDS, group, rows_per_block
path, W, H = yuv.CELLS['dng720']
cod = omc16.Codec(W, H, S=4, bpp=0.5)
cod.encode(yuv.read_frame(path, W, H, 0))
src = yuv.read_frame(path, W, H, 1)
# replicate encode() prelude for frame 1
t = cod.t; intra = False; phi = t % cod.Nc
V = np.zeros((cod.nby, cod.nbx, 2), np.int64)
ucls, xp, Tp, static = cod.prepare(V, intra, phi)
Ts = [pyr2.analysis(src[pi], cod.Lh[pi]) for pi in range(3)]
cod.BND = cod.boundary_masks(Ts); cx, vc = cod.contexts(Tp, V, intra)
nb, U = cod.nblk, cod.U
mode = np.zeros((nb, U), np.int64); hold = static & (ucls == 1)[None, :]; Pu = np.full((nb, U), -1, np.int64); hold_x = np.zeros((nb, U), bool)
cod.llu = [np.zeros((nb, U), np.int64) for _ in range(3)]
Pk = np.zeros(cod.NS, np.int64); st = dict(Fc=None, mode=mode, hold=hold, Pu=Pu, hold_x=hold_x, Pk=Pk)
k = 50
for P in (omc16.PMAX, 240, 180):
    res = cod.lane(Ts, Tp, k, P, intra, ucls, V, st, cx, vc, False)
    print('P', P, 'bits', res['bits'], 'budget ~', (cod.F - 32) * cod.share[k])
    for pi in range(3):
        for band in BANDS(cod.Lh[pi]):
            q = res['Q'][pi][band]
            if q is None: continue
            bs, rows = cod.rows_of(band, k); D = cod.step(pi, band, P)
            print('   ', pi, band, 'D', D, 'n', q.size, 'nonzero', int((q != 0).sum()), 'max|q|', int(np.abs(q).max()), 'mode inter frac %.2f' % res['mode'][bs].mean())
    print('   vector bits', cod.vector_bits(V, k), 'hold units', int(hold.sum()), 'static', int(static.sum()))
