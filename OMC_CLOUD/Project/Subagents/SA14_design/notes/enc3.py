"""gen-1 encoder, DEMOTION closure (nest.py semantics: boundary samples have u = 0).
Source samples on their window bound -> boundary samples (analysis already used u = 0).
Lattice samples whose pre-clamp value reaches/passes the bound -> index moved one step inward;
a zero index still on/over the bound -> boundary sample (u stays 0: no change)."""
import numpy as np, nest

def prevals(top, ql, lo, hi, n2d, n1d):
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

def encode(Xsrc, lo, hi, n2d, n1d, shifts, max_rounds=200):
    levels, (L, tlo, thi) = nest.analysis(Xsrc, lo, hi, n2d, n1d)
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
    top = {'q': nest.Q(L, st), 's': st, 'esc': np.where(L >= thi, 1, np.where(L <= tlo, -1, 0)).astype(np.int8)}
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
            # zero index already over the bound -> boundary sample (u stays 0)
            z_hi = hiv & (q <= 0); z_lo = lov & (q >= 0)
            d['esc'] = np.where(z_hi, 1, np.where(z_lo, -1, d['esc'])).astype(np.int8)
            dm = (hiv & (q > 0)) | (lov & (q < 0))
            d['q'] = np.where(hiv & (q > 0), q - 1, np.where(lov & (q < 0), q + 1, q))
            d['val'] = nest.R(d['q'], d['s'])
            dem += int(dm.sum()); esc_new += int((z_hi | z_lo).sum())
            return int(v.sum())
        ch += fix(top, tv, tl, th)
        for lev in range(n2d + n1d):
            for n, (pre, l, h) in res[lev].items():
                ch += fix(ql[lev][n], pre, l, h)
        hist.append(ch)
        if ch == 0:
            break
        if rounds >= max_rounds:
            raise RuntimeError('no convergence')
    return ql, top, rec, {'rounds': rounds, 'demoted': dem, 'new_boundary': esc_new, 'hist': hist}
