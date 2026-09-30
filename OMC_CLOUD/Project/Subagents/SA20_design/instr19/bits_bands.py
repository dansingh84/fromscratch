# SA19: where the bits go (emitted description), per band group and plane, plus vector bits, frames 2..N-1
import numpy as np, sys, yuv, ent, tpp, codec
cell, bpp, tab = sys.argv[1], float(sys.argv[2]), sys.argv[3]; N = int(sys.argv[4])
p, W, H = yuv.CELLS[cell]; s = tpp.TPP(W, H, bpp, ent.Tables(tab), tilt=0.25, rho=0.35, S=4 if cell == 'dng720' else 8)
acc = {}; vbits = 0.0; tot = 0.0
for f in range(N):
    o, b, i = s.encode(yuv.read_frame(p, W, H, f))
    if f < 2: continue
    tot += b.sum(); vbits += s.vec_bits(i['V1']).sum()
    c = s.c; nS = H // s.S
    for pl in range(3):
        for bd in codec.BANDSP[pl]:
            e_s = np.array([c.E[k][(pl, bd)] for k in i['plans']]); e_r = np.repeat(e_s, s.S // codec.ROWDIV[(pl, bd)])
            g = 'coarse' if codec.LEVEL[bd] >= 3 else ('L2' if codec.LEVEL[bd] == 2 else 'L1')
            acc[(pl, g)] = acc.get((pl, g), 0) + c.sbits(pl, bd, i['Q'][pl][bd], np.ones_like(i['Q'][pl][bd], bool), e=e_r).sum()
print(cell, bpp, 'frames 2..%d: vectors %.1f %% of bits' % (N - 1, 100 * vbits / tot))
for pl in range(3): print('  plane', pl, ' '.join('%s %.1f %%' % (g, 100 * acc[(pl, g)] / tot) for g in ('coarse', 'L2', 'L1')))
