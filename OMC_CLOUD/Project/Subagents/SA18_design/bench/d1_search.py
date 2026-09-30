# vertical 2-level pair pyramid, float: level-2 predictor D^ = a1(M-1 - M+1) + a2(M-2 - M+2), level-1 d^ = b1(..)+b2(..)
# measures (1) row-phase spread of the zero-vertical-detail synthesis (owner statistic, per plane),
# (2) residual energy of LH-type (vertical) details as a coding proxy (screening only).
import numpy as np, sys, yuv, itertools
def sh(a, k):
    n = a.shape[0]; i = np.arange(n) + k; i = np.where(i < 0, -i, i); i = np.where(i > n - 1, 2 * (n - 1) - i, i); return a[i]
def pred(m, c1, c2): return c1 * (sh(m, -1) - sh(m, 1)) + c2 * (sh(m, -2) - sh(m, 2))
def run(x, a1, a2, b1, b2):
    x = x.astype(float); m = (x[0::2] + x[1::2]) / 2; d = x[0::2] - x[1::2]
    M = (m[0::2] + m[1::2]) / 2; D = m[0::2] - m[1::2]
    Dh = pred(M, a1, a2); mz = np.empty_like(m); mz[0::2] = M + Dh / 2; mz[1::2] = M - Dh / 2
    dh = pred(mz, b1, b2); y = np.empty_like(x); y[0::2] = mz + dh / 2; y[1::2] = mz - dh / 2
    gs = np.abs(np.diff(x, axis=1)).mean(1); gd = np.abs(np.diff(y, axis=1)).mean(1)
    r = np.array([gd[k::4].sum() / gs[k::4].sum() for k in range(4)]); spread = 100 * (r.max() - r.min()) / r.mean()
    e2 = np.abs(D - Dh).mean(); e1 = np.abs(d - pred(m, b1, b2)).mean()
    return spread, e1, e2
frames = []
for cell in ('dng720', 'dng1080', 'hwy', 'spot'):
    p, W, H = yuv.CELLS[cell]; frames.append((cell, yuv.read_frame(p, W, H, 3)))
cands = [(0.25, 0, 0.25, 0)] + [(a1, a2, b1, b2) for a1 in (0.25, 0.3125, 0.375) for a2 in (0, -1/32, -1/16) for b1 in (0.125, 0.1875, 0.25, 0.3125) for b2 in (0, -1/32, -1/16)]
res = []
for c in cands:
    S = []; E1 = []; E2 = []
    for cell, x in frames:
        for i in range(3):
            s, e1, e2 = run(x[i], *c); S.append(s); E1.append(e1); E2.append(e2)
    res.append((c, max(S), np.mean(S), np.mean(E1), np.mean(E2), S))
base = res[0]
print('base 2/6', 'maxspread %.2f mean %.2f e1 %.3f e2 %.3f' % base[1:5])
for r in sorted(res, key=lambda r: r[1])[:15]:
    print(r[0], 'maxspread %.2f mean %.2f  e1 %+.2f%% e2 %+.2f%%' % (r[1], r[2], 100 * (r[3] / base[3] - 1), 100 * (r[4] / base[4] - 1)), ' '.join('%.1f' % v for v in r[5]))
