# D1: row-phase detail retention of the pair pyramid's ZERO-DETAIL synthesis (no coding at all).
# owner's rowphase statistic: per row, mean |horizontal gradient| of decode / of source, averaged by row mod 4.
import numpy as np, sys, yuv, pyr
def prof(src, dec, sh=4):
    gs = np.abs(np.diff(src, axis=1)).mean(1); gd = np.abs(np.diff(dec, axis=1)).mean(1)
    r = np.array([gd[k::sh].sum() / gs[k::sh].sum() for k in range(sh)]); return r, 100 * (r.max() - r.min()) / r.mean()
cell = sys.argv[1] if len(sys.argv) > 1 else 'dng720'
p, W, H = yuv.CELLS[cell]; x = yuv.read_frame(p, W, H, 0)
for kill in (['LH1', 'HH1'], ['LH1', 'HH1', 'LH2', 'HH2'], ['LH1', 'HH1', 'HL1'], ['LH1', 'HH1', 'HL1', 'LH2', 'HH2', 'HL2']):
    out = []
    for i in range(3):
        T = pyr.analysis(x[i])
        for b in kill: T[b] = np.zeros_like(T[b])
        y, _, _ = pyr.synthesis(T, -10**9, 10**9, legal=False)
        r, s = prof(x[i], y); out.append('%s spread %.1f%% [%s]' % ('YCbCr'[i] if i == 0 else ['Cb', 'Cr'][i - 1], s, ' '.join('%.3f' % v for v in r)))
    print(cell, 'zeroed', '+'.join(kill), ' | '.join(out))
