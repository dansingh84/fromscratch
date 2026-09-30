# SA19 D3 decomposition: per plane and band, error energy of a decode vs the source (frames 2..N-1), ours vs today's.
import numpy as np, sys, yuv, pyr
cell, bpp, ours = sys.argv[1], sys.argv[2], sys.argv[3]
p, W, H = yuv.CELLS[cell]; N = 12
td = yuv.TODAY[cell] % bpp
acc = {}
for f in range(2, N):
    s = yuv.read_frame(p, W, H, f); a = yuv.read_frame(ours, W, H, f); t = yuv.read_frame(td, W, H, f)
    for pl in range(3):
        Ts = pyr.analysis(s[pl]); Ta = pyr.analysis(a[pl]); Tt = pyr.analysis(t[pl])
        for b in Ts:
            acc[(pl, b, 'o')] = acc.get((pl, b, 'o'), 0) + float(((Ta[b] - Ts[b]) ** 2).sum())
            acc[(pl, b, 't')] = acc.get((pl, b, 't'), 0) + float(((Tt[b] - Ts[b]) ** 2).sum())
            acc[(pl, b, 'e')] = acc.get((pl, b, 'e'), 0) + float(((Ts[b]) ** 2).sum())
print(cell, bpp, ours.split('/')[-1])
for pl in range(3):
    print(' plane', pl, '  band: ours/today error energy (source energy share)')
    print('   ' + '  '.join('%s %.2f' % (b, acc[(pl, b, 'o')] / max(acc[(pl, b, 't')], 1)) for b in ['LL', 'H5', 'H4', 'H3', 'HL2', 'LH2', 'HH2', 'HL1', 'LH1', 'HH1']))
    print('   abs ours ' + ' '.join('%.3g' % acc[(pl, b, 'o')] for b in ['LL', 'H5', 'H4', 'H3', 'HL2', 'LH2', 'HH2', 'HL1', 'LH1', 'HH1']))
