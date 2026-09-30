"""gen-1 encoder, DEMOTION closure (nest.py semantics: boundary samples have u = 0).
Source samples on their window bound -> boundary samples (analysis already used u = 0).
Lattice samples whose pre-clamp value reaches/passes the bound -> index moved one step inward;
a zero index still on/over the bound -> boundary sample (u stays 0: no change)."""
import numpy as np, nests as nest
SRC_ESC = True
COARSE_FIRST = False
HYB_K = 2

def prevals(top, ql, lo, hi, n2d, n1d):
    rec, _, _ = nest.synthesis(top, ql, lo, hi, n2d, n1d)
    out = [nest.PRE[lev] for lev in range(n2d + n1d)]
    return rec, nest.PRE['top'], out

def _old_prevals(top, ql, lo, hi, n2d, n1d):
    nl = n2d + n1d
    levels_u = [{n: np.where(d['esc'] != 0, 0, d['val']) for n, d in ql[lev].items()} for lev in range(nl)]
    wins, (tlo, thi) = nest.windows(levels_u, lo, hi, n2d, n1d)
    L = np.where(top['esc'] > 0, thi, np.where(top['esc'] < 0, tlo, np.clip(top['val'], tlo, thi)))
    out = [None] * nl
    for lev in reversed(range(nl)):
        win, Uv = wins[lev]
        A = L - Uv
        res = {}
        def put(n, P):
            d = ql[lev][n]; l, h = win[n]
            pre = d['val'] + P
            res[n] = (pre, l, h)
            return np.where(d['esc'] > 0, h, np.where(d['esc'] < 0, l, np.clip(pre, l, h)))
        if lev < n2d:
            B = put('B', nest.PB(A)); C = put('C', nest.PC(A)); D = put('D', nest.PD(B, C))
            X = np.empty((A.shape[0] * 2, A.shape[1] * 2), np.int64)
            X[0::2, 0::2] = A; X[0::2, 1::2] = B; X[1::2, 0::2] = C; X[1::2, 1::2] = D
        else:
            B = put('B', nest.PH(A))
            X = np.empty((A.shape[0], A.shape[1] * 2), np.int64)
            X[:, 0::2] = A; X[:, 1::2] = B
        out[lev] = res
        L = X
    return L, (top['val'], tlo, thi), out

def hybrid_analysis(X, lo, hi, n2d, n1d, shifts, k=HYB_K):
    # same as nest.analysis, but a sample on its bound is an escape only if |detail| < k * step
    import nests as N
    levels = []
    for lev in range(n2d + n1d):
        if lev < n2d:
            A = X[0::2, 0::2]; B = X[0::2, 1::2]; C = X[1::2, 0::2]; D = X[1::2, 1::2]
            loA, hiA = lo[0::2, 0::2], hi[0::2, 0::2]
            win = {'B': (lo[0::2, 1::2], hi[0::2, 1::2]), 'C': (lo[1::2, 0::2], hi[1::2, 0::2]), 'D': (lo[1::2, 1::2], hi[1::2, 1::2])}
            fin = {'B': B, 'C': C, 'D': D}; P = {'B': N.PB(A), 'C': N.PC(A), 'D': N.PDS(A, B, C)}; names = ('B', 'C', 'D')
        else:
            A = X[:, 0::2]; B = X[:, 1::2]; loA, hiA = lo[:, 0::2], hi[:, 0::2]
            win = {'B': (lo[:, 1::2], hi[:, 1::2])}; fin = {'B': B}; P = {'B': N.PH(A)}; names = ('B',)
        lvl = {}; u = {}
        for n in names:
            l, h = win[n]; val = fin[n] - P[n]
            atb = (fin[n] >= h) | (fin[n] <= l)
            esc = np.where(atb & (np.abs(val) < (k << shifts[(lev, n)])), np.where(fin[n] >= h, 1, -1), 0).astype(np.int8)
            u[n] = np.where(esc != 0, 0, val); lvl[n] = {'val': val, 'esc': esc}
        if lev < n2d:
            lvl['B']['val'] = lvl['B']['val'] + N.gB(u['D']); lvl['C']['val'] = lvl['C']['val'] + N.gC(u['D'])
            Uv = N.U2(u['B'], u['C'], u['D'])
        else:
            Uv = N.UH(u['B'])
        levels.append(lvl)
        X, lo, hi = A + Uv, loA + Uv, hiA + Uv
    return levels, (X, lo, hi)

def encode(Xsrc, lo, hi, n2d, n1d, shifts, max_rounds=200, src_escapes=None):
    se = SRC_ESC if src_escapes is None else src_escapes
    if se == 'hybrid':
        levels, (L, tlo, thi) = hybrid_analysis(Xsrc, lo, hi, n2d, n1d, shifts)
        se = True
    elif se:
        levels, (L, tlo, thi) = nest.analysis(Xsrc, lo, hi, n2d, n1d)
    else:
        levels, (L, _, _) = nest.analysis(Xsrc, lo * 0 - nest.INF, hi * 0 + nest.INF, n2d, n1d)
        tlo = thi = None
    ql = []
    for lev, lvl in enumerate(levels):
        d2 = {}
        for n, d in lvl.items():
            if n == 'win':
                continue
            s = shifts[(lev, n)]
            d2[n] = {'q': nest.Q(d['val'], s), 's': s, 'esc': d['esc'].copy()}
            d2[n]['val'] = nest.R(d2[n]['q'], s)
        ql.append(d2)
    st = shifts['top']
    top = {'q': nest.Q(L, st), 's': st, 'esc': (np.where(L >= thi, 1, np.where(L <= tlo, -1, 0)) if se else np.zeros(L.shape)).astype(np.int8)}
    top['val'] = nest.R(top['q'], st)
    rounds = 0; dem = 0; esc_new = 0; hist = []
    while True:
        rounds += 1
        rec, (tv, tl, th), res = prevals(top, ql, lo, hi, n2d, n1d)
        ch = 0
        def fix(d, pre, l, h):
            nonlocal dem, esc_new
            v = (d['esc'] == 0) & ((pre <= l) | (pre >= h))
            if not v.any():
                return 0
            hiv = v & (pre >= h); lov = v & (pre <= l)
            q = d['q']
            # zero index on/over the bound -> boundary sample (its update value stays 0)
            z_hi = hiv & (q == 0); z_lo = lov & (q == 0)
            d['esc'] = np.where(z_hi, 1, np.where(z_lo, -1, d['esc'])).astype(np.int8)
            # nonzero index: one lattice step toward the interior (any sign)
            dm = (hiv | lov) & (q != 0)
            d['q'] = np.where(hiv & (q != 0), q - 1, np.where(lov & (q != 0), q + 1, q))
            d['val'] = nest.R(d['q'], d['s'])
            dem += int(dm.sum()); esc_new += int((z_hi | z_lo).sum())
            return int(v.sum())
        ch += fix(top, tv, tl, th)
        if ch == 0 or not COARSE_FIRST:
            for lev in reversed(range(n2d + n1d)):
                for n, (pre, l, h) in res[lev].items():
                    ch += fix(ql[lev][n], pre, l, h)
                if ch and COARSE_FIRST:
                    break
        hist.append(ch)
        if ch == 0:
            break
        if rounds >= max_rounds:
            raise RuntimeError('no convergence')
    return ql, top, rec, {'rounds': rounds, 'demoted': dem, 'new_boundary': esc_new, 'hist': hist}
