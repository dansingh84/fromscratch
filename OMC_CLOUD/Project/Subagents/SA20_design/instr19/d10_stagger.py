# D10: staggered level-2 vertical pairing (odd LL1 columns paired one LL1 row lower) -> every picture row holds both
# level-2 row roles. Zero-detail stress (owner rowphase statistic by row mod 4) + intra PROXY vs plain AVG.
import numpy as np, sys, yuv, pyr
def prof(src, dec, sh=4):
    gs = np.abs(np.diff(src, axis=1)).mean(1); gd = np.abs(np.diff(dec, axis=1)).mean(1)
    r = np.array([gd[k::sh].sum() / gs[k::sh].sum() for k in range(sh)]); return 100 * (r.max() - r.min()) / r.mean()
def colprof(src, dec, sh=4):
    return prof(src.T, dec.T, sh)
def stag(a, inv=False):      # roll odd columns by one row (up for analysis, down for synthesis), mirror at the edge
    b = a.copy(); o = a[:, 1::2]
    b[:, 1::2] = np.roll(o, 1 if inv else -1, axis=0)
    return b
def ana(x, st):
    T1 = pyr.analysis(x, 1, 1)        # level 1 quad only -> LL1 + HL1/LH1/HH1
    LL1 = T1['LL']
    if st: LL1 = stag(LL1)
    T2 = pyr.analysis(LL1, 1, 4)      # level-2 quad + horizontal 3..5 on (possibly staggered) LL1
    return T1, T2
def syn(T1, T2, st):
    LL1, _, _ = pyr.synthesis(T2, -10**9, 10**9, 1, 4, legal=False)
    if st: LL1 = stag(LL1, inv=True)
    T1 = dict(T1); T1['LL'] = LL1
    y, _, _ = pyr.synthesis(T1, -10**9, 10**9, 1, 1, legal=False); return y
for cell in ('dng720', 'dng1080'):
    p, W, H = yuv.CELLS[cell]; x = yuv.read_frame(p, W, H, 0)
    for st in (False, True):
        for kill1, kill2 in ((['LH', 'HH'], ['LH', 'HH']), (['LH', 'HH', 'HL'], ['LH', 'HH', 'HL', 'H2'])):
            out = []
            for i in range(3):
                T1, T2 = ana(x[i], st)
                assert np.array_equal(syn(T1, T2, st), x[i]) or st and np.abs(syn(T1, T2, st) - x[i]).max() == 0
                for b in kill1: T1[b + '1'] = np.zeros_like(T1[b + '1'])
                for b in kill2:
                    k = b if b.startswith('H2') else b + '1'
                    if k in T2: T2[k] = np.zeros_like(T2[k])
                y = syn(T1, T2, st); out.append('%.1f/%.1f' % (prof(x[i], y), colprof(x[i], y)))
            print(cell, 'stagger' if st else 'plain  ', 'kill L1', '+'.join(kill1), 'L2', '+'.join(kill2), ' row/col spread Y %s Cb %s Cr %s' % tuple(out))
