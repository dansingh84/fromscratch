"""One-shot (bounded) escape closure with provable shift bounds (SA14).
Provisional synthesis -> per-sample shift bounds S (top-down) assuming every detail neighbour in a
set K may convert -> candidates = normal samples whose pre is within S (+window motion) of the
boundary -> convert all at once -> final synthesis must have zero violations.
Tightening: K0 = all details; K1 = candidates of pass 0 (safe since final conversions subset K0)."""
import numpy as np, nest

def bounds_and_candidates(q_levels, top, lo, hi, n2d, n1d, K):
    """K: per level dict name->bool mask of samples that may convert (None = all normal)."""
    nl = n2d + n1d
    # u and push magnitudes
    pushes = []
    for lev in range(nl):
        pp = {}
        for n, d in q_levels[lev].items():
            if n in ('win', 's'):
                continue
            mayc = (d['esc'] == 0) if K is None else (K[lev][n] & (d['esc'] == 0))
            pp[n] = np.where(mayc, np.abs(d['val']), 0)
        pushes.append(pp)
    # dU bounds per level at ee positions
    dUb = []
    for lev in range(nl):
        pp = pushes[lev]
        if lev < n2d:
            s = 4 * (nest.left(pp['B']) + pp['B'] + nest.up(pp['C']) + pp['C'])
            if nest.WD:
                s = s + abs(nest.WD) * (nest.up(nest.left(pp['D'])) + nest.up(pp['D']) + nest.left(pp['D']) + pp['D'])
            dUb.append((s + 15) >> 4)
        else:
            dUb.append((nest.left(pp['B']) + pp['B'] + 3) >> 2)
    # provisional synthesis for pre values
    rec, vt, vl = nest.synthesis(top, q_levels, lo, hi, n2d, n1d)
    # recompute pre values per level (re-run pieces of synthesis)
    levels_u = []
    for lev in range(nl):
        uu = {n: np.where(d['esc'] != 0, 0, d['val']) for n, d in q_levels[lev].items() if n not in ('win', 's')}
        levels_u.append(uu)
    wins, (tlo, thi) = nest.windows(levels_u, lo, hi, n2d, n1d)
    cand = []
    # top: value pre = top val; its window moves by dUb of the coarsest level (window of L)
    Stop = dUb[nl - 1] * 0  # no coarser shift
    wmove = dUb[nl - 1]
    pre = top['val']
    ct = (top['esc'] == 0) & ((pre + wmove >= thi) | (pre - wmove <= tlo))
    L = np.where(top['esc'] > 0, thi, np.where(top['esc'] < 0, tlo, np.clip(pre, tlo, thi)))
    SL = np.where(ct, 2 * wmove, wmove)  # shift bound of L values (window motion + snap)
    cands = [None] * nl
    for lev in reversed(range(nl)):
        win, Uv = wins[lev]
        A = L - Uv
        SA = SL + dUb[lev]
        cl = {}
        def test(n, P, SP):
            d = q_levels[lev][n]; l, h = win[n]
            # window of these samples moves with the finer level's U (if lev>0)
            wm = 0 if lev == 0 else dUb[lev - 1][tuple(slice(None) for _ in range(0))] if False else 0
            pre = d['val'] + P
            c = (d['esc'] == 0) & ((pre + SP >= h) | (pre - SP <= l))
            cl[n] = c
            val = np.where(d['esc'] > 0, h, np.where(d['esc'] < 0, l, np.clip(pre, l, h)))
            return val, np.where(c, 2 * SP + 1, SP)
        if lev < n2d:
            SB = (SA + nest.right(SA) + 1) >> 1
            SC = (SA + nest.down(SA) + 1) >> 1
            B, SBv = test('B', nest.PB(A), SB)
            C, SCv = test('C', nest.PC(A), SC)
            SD = (SBv + nest.down(SBv) + SCv + nest.right(SCv) + 3) >> 2
            D, SDv = test('D', nest.PD(B, C), SD)
            X = np.empty((A.shape[0] * 2, A.shape[1] * 2), np.int64)
            X[0::2, 0::2] = A; X[0::2, 1::2] = B; X[1::2, 0::2] = C; X[1::2, 1::2] = D
            S = np.empty_like(X)
            S[0::2, 0::2] = SA; S[0::2, 1::2] = SBv; S[1::2, 0::2] = SCv; S[1::2, 1::2] = SDv
        else:
            SB = (SA + nest.right(SA) + 1) >> 1
            B, SBv = test('B', nest.PH(A), SB)
            X = np.empty((A.shape[0], A.shape[1] * 2), np.int64)
            X[:, 0::2] = A; X[:, 1::2] = B
            S = np.empty_like(X); S[:, 0::2] = SA; S[:, 1::2] = SBv
        cands[lev] = cl
        # window motion for the next finer level's samples = that level's dUb at ee (handled via SL)
        L = X
        SL = S + (dUb[lev - 1] if False else 0)
        if lev > 0:
            # the finer level's L windows move with the finer dUb: add to shift bound of coarse samples
            fin = dUb[lev - 1]
            SL = S + fin
    return ct, cands

def encode_oneshot(Xsrc, lo, hi, n2d, n1d, shifts, tighten=1):
    levels, (L, tlo, thi) = nest.analysis(Xsrc, lo, hi, n2d, n1d)
    ql = []
    for lev, lvl in enumerate(levels):
        d2 = {}
        for n, d in lvl.items():
            if n == 'win':
                continue
            s = shifts[(lev, n)]
            d2[n] = {'val': nest.R(nest.Q(d['val'], s), s), 'esc': d['esc'].copy()}
        ql.append(d2)
    st = shifts['top']
    top = {'val': nest.R(nest.Q(L, st), st), 'esc': np.where(L >= thi, 1, np.where(L <= tlo, -1, 0)).astype(np.int8)}
    K = None
    for t in range(tighten + 1):
        ct, cands = bounds_and_candidates(ql, top, lo, hi, n2d, n1d, K)
        K = cands
    # convert: direction = side of the boundary nearer to pre (use provisional synthesis violations sign)
    rec0, vt0, vl0 = nest.synthesis(top, ql, lo, hi, n2d, n1d)
    nconv = 0
    # need the pre sign: recompute via windows on provisional
    levels_u = [{n: np.where(d['esc'] != 0, 0, d['val']) for n, d in ql[lev].items()} for lev in range(n2d + n1d)]
    # simple direction: compare provisional output sample to window midpoint
    def side(val, l, h):
        return np.where(2 * val >= l + h, 1, -1).astype(np.int8)
    # rebuild provisional per-level sample values & windows to get directions
    wins, (tlo2, thi2) = nest.windows(levels_u, lo, hi, n2d, n1d)
    Lp = np.clip(top['val'], tlo2, thi2)
    top['esc'] = np.where(ct, side(Lp, tlo2, thi2), top['esc']).astype(np.int8); nconv += int(ct.sum())
    Lv = np.where(top['esc'] > 0, thi2, np.where(top['esc'] < 0, tlo2, Lp))
    for lev in reversed(range(n2d + n1d)):
        win, Uv = wins[lev]
        A = Lv - Uv
        def val_of(n, P):
            d = ql[lev][n]; l, h = win[n]
            pre = d['val'] + P
            v = np.where(d['esc'] > 0, h, np.where(d['esc'] < 0, l, np.clip(pre, l, h)))
            return v, l, h
        if lev < n2d:
            B, l, h = val_of('B', nest.PB(A)); cb = cands[lev]['B']
            C, l2, h2 = val_of('C', nest.PC(A)); cc = cands[lev]['C']
            D, l3, h3 = val_of('D', nest.PD(B, C)); cd = cands[lev]['D']
            for n, c, v, ll, hh in (('B', cb, B, l, h), ('C', cc, C, l2, h2), ('D', cd, D, l3, h3)):
                ql[lev][n]['esc'] = np.where(c, side(v, ll, hh), ql[lev][n]['esc']).astype(np.int8); nconv += int(c.sum())
            X = np.empty((A.shape[0] * 2, A.shape[1] * 2), np.int64)
            X[0::2, 0::2] = A; X[0::2, 1::2] = B; X[1::2, 0::2] = C; X[1::2, 1::2] = D
        else:
            B, l, h = val_of('B', nest.PH(A)); cb = cands[lev]['B']
            ql[lev]['B']['esc'] = np.where(cb, side(B, l, h), ql[lev]['B']['esc']).astype(np.int8); nconv += int(cb.sum())
            X = np.empty((A.shape[0], A.shape[1] * 2), np.int64)
            X[:, 0::2] = A; X[:, 1::2] = B
        Lv = X
    rec, vt, vl = nest.synthesis(top, ql, lo, hi, n2d, n1d)
    nviol = int((vt != 0).sum()) + sum(int((v != 0).sum()) for lvl in vl for v in lvl.values())
    return ql, top, rec, {'converted': nconv, 'violations_left': nviol}
