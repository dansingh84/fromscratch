# zero-vertical-detail interpolator of a 2-level vertical pair pyramid: weights of rows 0..3 of a group on the
# level-2 means M, for level-2 slope alpha and level-1 slope beta (d = top - bottom predicted as coef*(prev-next)).
import numpy as np
def rows(alpha, beta, g2=None):
    n = 11; c = 5
    def M(k): e = np.zeros(n); e[c + k] = 1; return e
    def m(j):      # level-1 mean j (two per group); j = 2g or 2g+1
        g, s = divmod(j, 2)
        D = alpha * (M(g - 1) - M(g + 1)) if g2 is None else g2(M, g)
        return M(g) + (D / 2 if s == 0 else -D / 2)
    out = []
    for j in (0, 1):
        dl = beta * (m(j - 1) - m(j + 1))
        out += [m(j) + dl / 2, m(j) - dl / 2]
    return np.array(out)
for a, b in [(0.25, 0.25), (0.25, 0.125), (0.375, 0.25), (0.3125, 0.1875), (0.25, 0.1875), (0.1875, 0.25)]:
    W = rows(a, b); s2 = (W ** 2).sum(1)
    # correlated content: AR(1) rho on the M sequence (M already a 4-row mean)
    for rho in (0.0, 0.5, 0.8):
        C = rho ** np.abs(np.subtract.outer(np.arange(11), np.arange(11)))
        v = np.einsum('ri,ij,rj->r', W, C, W)
    print('alpha %.4f beta %.4f  sum w^2 per row %s   ratio outer/inner %.3f' % (a, b, np.round(s2, 3), s2[0] / s2[1]))
