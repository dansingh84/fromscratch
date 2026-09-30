"""gen-1 encoder, reading and gen-2 check for the exact-boundary-sample variant (nest2)."""
import numpy as np, nest2 as nest
DAMP_AFTER = 3
DEBUG = False

def prevals(top, ql, lo, hi, n2d, n1d):
    """re-run synthesis, returning for every detail sample its pre-clamp value and window."""
    nl = n2d + n1d
    levels_u = [{n: np.where(d['esc'] != 0, d['uesc'], d['val']) for n, d in ql[lev].items()} for lev in range(nl)]
    wins, (tlo, thi) = nest.windows(levels_u, lo, hi, n2d, n1d)
    L = np.where(top['esc'] > 0, thi, np.where(top['esc'] < 0, tlo, np.clip(top['val'], tlo, thi)))
    toppre = (top['val'], tlo, thi)
    out = [None] * nl
    for lev in reversed(range(nl)):
        win, Uv = wins[lev]
        A = L - Uv
        res = {}
        def put(n, P):
            d = ql[lev][n]; l, h = win[n]
            pre = np.where(d['esc'] != 0, d['uesc'], d['val']) + P
            v = np.where(d['esc'] > 0, h, np.where(d['esc'] < 0, l, np.clip(pre, l, h)))
            res[n] = (P, l, h)
            return v
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
    return L, toppre, out

def encode(Xsrc, lo, hi, n2d, n1d, shifts, max_rounds=64, src_rail='boundary'):
    levels, (L, tlo, thi) = nest.analysis(Xsrc, lo, hi, n2d, n1d)
    ql = []
    for lev, lvl in enumerate(levels):
        d2 = {}
        for n, d in lvl.items():
            if n == 'win':
                continue
            s = shifts[(lev, n)]
            d2[n] = {'val': nest.R(nest.Q(d['val'], s), s), 'esc': d['esc'].copy(), 'uesc': d['uesc'].copy()}
        ql.append(d2)
    st = shifts['top']
    top = {'val': nest.R(nest.Q(L, st), st), 'esc': np.where(L >= thi, 1, np.where(L <= tlo, -1, 0)).astype(np.int8)}
    rounds = 0; conv = 0
    phase = ['down']
    while True:
        rounds += 1
        want_down = 0
        rec, (tv, tl, th), res = prevals(top, ql, lo, hi, n2d, n1d)
        changed = 0
        conv_round = 0
        vt = (top['esc'] == 0) & ((tv <= tl) | (tv >= th))
        if vt.any():
            top['esc'] = np.where(vt, np.where(tv >= th, 1, -1), top['esc']).astype(np.int8); changed += int(vt.sum()); conv += int(vt.sum())
        for lev in range(n2d + n1d):
            for n, (P, l, h) in res[lev].items():
                d = ql[lev][n]
                # lattice violators -> boundary samples
                pre = d['val'] + P
                v = (d['esc'] == 0) & ((pre <= l) | (pre >= h))
                if v.any():
                    d['esc'] = np.where(v, np.where(pre >= h, 1, -1), d['esc']).astype(np.int8); conv += int(v.sum()); conv_round += int(v.sum())
                # fixed point for boundary samples: u = bound - P
                tgt = np.where(d['esc'] > 0, h - P, np.where(d['esc'] < 0, l - P, 0))
                m = (d['esc'] != 0) & (d['uesc'] != tgt)
                want_down += int(((d['esc'] != 0) & (tgt < d['uesc'])).sum())
                if DEBUG and rounds > 30 and m.any():
                    ii = np.argwhere(m)[:4]
                    print('    lev',lev,n,[(tuple(x), int(d['uesc'][tuple(x)]), int(tgt[tuple(x)]), int(d['esc'][tuple(x)]), int(P[tuple(x)]), int(h[tuple(x)])) for x in ii])
                changed += int(m.sum()) + int(v.sum())
                # monotone schedule (the joint map is isotone): plain Jacobi for the first rounds,
                # then a decreasing phase (u <- min(u, T u)) until no sample wants to go down,
                # then an increasing phase (u <- T u, which is >= u) to a fixed point.
                if rounds <= DAMP_AFTER:
                    nu = tgt
                elif phase[0] == 'down':
                    nu = np.minimum(d['uesc'], tgt)
                else:
                    nu = tgt
                d['uesc'] = np.where(d['esc'] != 0, nu, 0)
        if changed == 0:
            break
        if rounds > DAMP_AFTER and phase[0] == 'down' and want_down == 0 and conv_round == 0:
            phase[0] = 'up'
        if rounds > 28 and rounds < 34: print('   round',rounds,'changed',changed,'phase',phase[0],'want_down',want_down,'conv_round',conv_round)
        if rounds >= max_rounds:
            raise RuntimeError('no convergence')
    return ql, top, rec, {'rounds': rounds, 'converted': conv}

def read(ql, top):
    desc = []; bits_lat = 0.0; bits_esc = 0.0
    for lev, q in enumerate(ql):
        dl = {}
        for n, d in q.items():
            nv = d['val'][d['esc'] == 0]
            s = min(nest.ctz_or(nv), 20)
            sym = np.where(d['esc'] != 0, (1 << 30) * d['esc'].astype(np.int64), d['val'] >> s)
            dl[n] = (s, sym, np.where(d['esc'] != 0, d['uesc'], 0))
            bits_lat += nest.entropy_bits(sym)
            ue = d['uesc'][d['esc'] != 0]
            if ue.size:
                bits_esc += nest.entropy_bits(ue)
        desc.append(dl)
    nv = top['val'][top['esc'] == 0]
    s = min(nest.ctz_or(nv), 20)
    sym = np.where(top['esc'] != 0, (1 << 30) * top['esc'].astype(np.int64), top['val'] >> s)
    desc.append(('top', s, sym)); bits_lat += nest.entropy_bits(sym)
    return desc, bits_lat, bits_esc

def decode(desc, lo, hi, n2d, n1d):
    ql = []
    for lev in range(n2d + n1d):
        q = {}
        for n, (s, sym, ue) in desc[lev].items():
            esc = np.where(np.abs(sym) >= (1 << 30), np.sign(sym), 0).astype(np.int8)
            q[n] = {'val': np.where(esc != 0, 0, sym << s), 'esc': esc, 'uesc': ue}
        ql.append(q)
    _, s, sym = desc[-1]
    esc = np.where(np.abs(sym) >= (1 << 30), np.sign(sym), 0).astype(np.int8)
    top = {'val': np.where(esc != 0, 0, sym << s), 'esc': esc}
    rec, _, _ = nest.synthesis(top, ql, lo, hi, n2d, n1d)
    return rec

def canonical(Y, lo, hi, n2d, n1d):
    levels, (L, tlo, thi) = nest.analysis(Y, lo, hi, n2d, n1d)
    ql = []
    for lvl in levels:
        q = {}
        for n, d in lvl.items():
            if n == 'win':
                continue
            q[n] = {'val': np.where(d['esc'] != 0, 0, d['val']), 'esc': d['esc'], 'uesc': d['uesc']}
        ql.append(q)
    top = {'val': np.where((L >= thi) | (L <= tlo), 0, L), 'esc': np.where(L >= thi, 1, np.where(L <= tlo, -1, 0)).astype(np.int8)}
    return ql, top

def same_desc(a, b):
    for x, y in zip(a[:-1], b[:-1]):
        for n in x:
            if x[n][0] != y[n][0] or not np.array_equal(x[n][1], y[n][1]) or not np.array_equal(x[n][2], y[n][2]):
                return False
    return a[-1][1] == b[-1][1] and np.array_equal(a[-1][2], b[-1][2])
