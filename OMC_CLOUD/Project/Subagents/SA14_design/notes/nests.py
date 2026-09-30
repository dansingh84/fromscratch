"""NEST core model (SA14 design experiment).  Integer numpy.  Own work.

Non-separable one-level 2-D lifting with a symmetric update that reads LEAF values,
rail/boundary escapes, per-sample windows, closure, canonical analysis and reading.
Also a separable integer 5/3 baseline for the efficiency comparison.

Levels: `n2d` non-separable 2-D levels, then `n1d` horizontal-only 1-D levels on the low band.
All arithmetic int64; >> is floor.
"""
import numpy as np

INF = 1 << 40
PRE = {}

# ---------------------------------------------------------------- helpers
def par(shape):
    i = np.arange(shape[0])[:, None]
    j = np.arange(shape[1])[None, :]
    return ((i + j) & 1).astype(np.int64)

def right(a):  # a[:, j+1], edge replicated
    return np.concatenate([a[:, 1:], a[:, -1:]], axis=1)

def left(a):   # a[:, j-1]
    return np.concatenate([a[:, :1], a[:, :-1]], axis=1)

def down(a):
    return np.concatenate([a[1:, :], a[-1:, :]], axis=0)

def up(a):
    return np.concatenate([a[:1, :], a[:-1, :]], axis=0)

# ---------------------------------------------------------------- predictors / update (one level)
# unbiased rounding: offsets alternate with sample parity (avoids the half-up colour cast)
def PB(A):   # predict eo from horizontal ee neighbours
    return (A + right(A) + par(A.shape)) >> 1

def PC(A):   # predict oe from vertical ee neighbours
    return (A + down(A) + par(A.shape)) >> 1

def PDS(A, B, C):  # separable-equivalent HH predictor from final A, B, C
    return ((C + right(C) + par(C.shape)) >> 1) + ((B + down(B) + par(B.shape)) >> 1) - ((A + right(A) + down(A) + down(right(A)) + 1 + par(A.shape)) >> 2)

TCLIP = 0
def cl(u):
    return np.clip(u, -TCLIP, TCLIP) if TCLIP else u

def gB(uD):
    uD = cl(uD)   # inner update of the eo detail by the HH leaves above/below  (HL = dB + gB)
    return (up(uD) + uD + 1 + par(uD.shape)) >> 2

def gC(uD):   # LH = dC + gC
    uD = cl(uD)
    return (left(uD) + uD + 1 + par(uD.shape)) >> 2

WD = 1  # weight (in 1/16) of the diagonal details in the update; set by experiment

def U2(uB, uC, uD):
    uB, uC, uD = cl(uB), cl(uC), cl(uD)
    s = 4 * (left(uB) + uB + up(uC) + uC)
    if WD:
        s = s + WD * (up(left(uD)) + up(uD) + left(uD) + uD)
    return (s + 7 + par(uB.shape)) >> 4

def PH(A):   # 1-D horizontal predict
    return (A + right(A) + par(A.shape)) >> 1

def UH(uB):
    uB = cl(uB)
    return (left(uB) + uB + 1 + par(uB.shape)) >> 2

# ---------------------------------------------------------------- structure
class Leaves:
    """per level: dict of detail arrays: val (int64, normal value incl. prediction), esc (int8)."""
    pass

def analysis(X, lo, hi, n2d, n1d, pred=None):
    """Canonical analysis.  X: final samples (int64), lo/hi: per-sample windows.
    pred: optional per-level band predictions (inter); None = intra (prediction 0).
    Returns levels list and top (L, lo, hi) and u used.  A detail sample on its window
    boundary is an escape (esc=+1 hi, -1 lo); its update contribution u = band prediction."""
    levels = []
    for lev in range(n2d + n1d):
        if lev < n2d:
            A = X[0::2, 0::2]; B = X[0::2, 1::2]; C = X[1::2, 0::2]; D = X[1::2, 1::2]
            loA, hiA = lo[0::2, 0::2], hi[0::2, 0::2]
            win = {'B': (lo[0::2, 1::2], hi[0::2, 1::2]), 'C': (lo[1::2, 0::2], hi[1::2, 0::2]),
                   'D': (lo[1::2, 1::2], hi[1::2, 1::2])}
            fin = {'B': B, 'C': C, 'D': D}
            P = {'B': PB(A), 'C': PC(A), 'D': PDS(A, B, C)}
            names = ('B', 'C', 'D')
        else:
            A = X[:, 0::2]; B = X[:, 1::2]
            loA, hiA = lo[:, 0::2], hi[:, 0::2]
            win = {'B': (lo[:, 1::2], hi[:, 1::2])}
            fin = {'B': B}
            P = {'B': PH(A)}
            names = ('B',)
        lvl = {}
        u = {}
        for n in names:
            l, h = win[n]
            esc = np.where(fin[n] >= h, 1, np.where(fin[n] <= l, -1, 0)).astype(np.int8)
            val = fin[n] - P[n]
            u[n] = np.where(esc != 0, 0, val)       # detail values d (0 for boundary samples)
            lvl[n] = {'val': val, 'esc': esc}
        if lev < n2d:
            # leaves: HL = dB + gB(dD), LH = dC + gC(dD), HH = dD
            lvl['B']['val'] = lvl['B']['val'] + gB(u['D'])
            lvl['C']['val'] = lvl['C']['val'] + gC(u['D'])
            Uv = U2(u['B'], u['C'], u['D'])
        else:
            Uv = UH(u['B'])
        L = A + Uv
        lvl['win'] = win
        levels.append(lvl)
        X, lo, hi = L, loA + Uv, hiA + Uv
    return levels, (X, lo, hi)

def windows(levels_u, lo, hi, n2d, n1d):
    """fine->coarse windows from leaf update values.  levels_u[lev] = dict name->u array."""
    wins = []
    for lev in range(n2d + n1d):
        if lev < n2d:
            win = {'B': (lo[0::2, 1::2], hi[0::2, 1::2]), 'C': (lo[1::2, 0::2], hi[1::2, 0::2]),
                   'D': (lo[1::2, 1::2], hi[1::2, 1::2])}
            uu = levels_u[lev]
            Uv = U2(uu['B'], uu['C'], uu['D'])
            loA, hiA = lo[0::2, 0::2], hi[0::2, 0::2]
        else:
            win = {'B': (lo[:, 1::2], hi[:, 1::2])}
            Uv = UH(levels_u[lev]['B'])
            loA, hiA = lo[:, 0::2], hi[:, 0::2]
        wins.append((win, Uv))
        lo, hi = loA + Uv, hiA + Uv
    return wins, (lo, hi)

def synthesis(top, levels, lo, hi, n2d, n1d, pred=None, pred_top=0):
    """Decoder.  top: dict val, esc for the coarsest low band (val = dequantised, pred added).
    levels[lev][name] = {'val': dequantised detail (pred added), 'esc': int8}.
    Returns picture and list of violations (normal samples whose pre-clamp value is at/beyond
    the window) for the encoder's closure."""
    levels_u = []
    dvals = []
    for lev in range(n2d + n1d):
        uu = {}; dv = {}
        if lev < n2d:
            dD = levels[lev]['D']
            uD = np.where(dD['esc'] != 0, 0, dD['val'])
            dv['D'] = dD['val']
            dv['B'] = levels[lev]['B']['val'] - gB(uD)
            dv['C'] = levels[lev]['C']['val'] - gC(uD)
        else:
            dv['B'] = levels[lev]['B']['val']
        for n, d in levels[lev].items():
            if n == 'win':
                continue
            uu[n] = np.where(d['esc'] != 0, 0, dv[n])
        levels_u.append(uu); dvals.append(dv)
    wins, (tlo, thi) = windows(levels_u, lo, hi, n2d, n1d)
    PRE.clear()
    PRE['top'] = (top['val'], tlo, thi)
    viol = []
    # coarsest low band
    tv = top['val']; te = top['esc']
    pre = tv
    vt = (te == 0) & ((pre <= tlo) | (pre >= thi))
    viol.append(('top', np.where(vt, np.where(pre >= thi, 1, -1), 0).astype(np.int8)))
    L = np.where(te > 0, thi, np.where(te < 0, tlo, np.clip(pre, tlo, thi)))
    vio_lev = [None] * (n2d + n1d)
    for lev in reversed(range(n2d + n1d)):
        win, Uv = wins[lev]
        uu = levels_u[lev]
        A = L - Uv
        out = {}
        vl = {}
        def put(n, P):
            d = levels[lev][n]
            l, h = win[n]
            pre = dvals[lev][n] + P
            v = (d['esc'] == 0) & ((pre <= l) | (pre >= h))
            vl[n] = np.where(v, np.where(pre >= h, 1, -1), 0).astype(np.int8)
            PRE.setdefault(lev, {})[n] = (pre, l, h)
            return np.where(d['esc'] > 0, h, np.where(d['esc'] < 0, l, np.clip(pre, l, h)))
        if lev < n2d:
            B = put('B', PB(A)); C = put('C', PC(A)); D = put('D', PDS(A, B, C))
            X = np.empty((A.shape[0] * 2, A.shape[1] * 2), np.int64)
            X[0::2, 0::2] = A; X[0::2, 1::2] = B; X[1::2, 0::2] = C; X[1::2, 1::2] = D
        else:
            B = put('B', PH(A))
            X = np.empty((A.shape[0], A.shape[1] * 2), np.int64)
            X[:, 0::2] = A; X[:, 1::2] = B
        vio_lev[lev] = vl
        L = X
    return L, viol[0][1], vio_lev

# ---------------------------------------------------------------- quantiser (nested lattices, R(q) = q*2^s)
def Q(c, s, z16=9):
    """dead-zone quantiser, step 2^s; zero cell |c| < z*2^s; reconstruction q*2^s."""
    if s == 0:
        return c.copy()
    off = ((16 - z16) << s) >> 4
    a = np.abs(c)
    return np.sign(c) * ((a + off) >> s)

def R(q, s):
    return q << s

def ctz_or(vals):
    """coarsest power-of-two shift whose lattice contains all values (all zero -> 63)."""
    o = int(np.bitwise_or.reduce(np.abs(vals).ravel())) if vals.size else 0
    if o == 0:
        return 63
    return (o & -o).bit_length() - 1

def entropy_bits(sym):
    v, c = np.unique(sym, return_counts=True)
    p = c / c.sum()
    return float(-(c * np.log2(p)).sum())

# ---------------------------------------------------------------- encoder (gen 1, intra)
def encode_intra(Xsrc, lo, hi, n2d, n1d, shifts, max_iter=64):
    """shifts: dict (lev,name)->s and ('top')->s.  Returns leaves (dequantised), top, recon, stats."""
    levels, (L, tlo, thi) = analysis(Xsrc, lo, hi, n2d, n1d)
    q_levels = []
    for lev, lvl in enumerate(levels):
        ql = {}
        for n, d in lvl.items():
            if n == 'win':
                continue
            s = shifts[(lev, n)]
            ql[n] = {'val': R(Q(d['val'], s), s), 'esc': d['esc'].copy(), 's': s}
        q_levels.append(ql)
    st = shifts['top']
    top = {'val': R(Q(L, st), st), 'esc': np.where(L >= thi, 1, np.where(L <= tlo, -1, 0)).astype(np.int8), 's': st}
    it = 0; conv = 0
    while True:
        rec, vt, vl = synthesis(top, q_levels, lo, hi, n2d, n1d)
        n_new = int((vt != 0).sum())
        top['esc'] = np.where(vt != 0, vt, top['esc']).astype(np.int8)
        for lev in range(n2d + n1d):
            for n, v in vl[lev].items():
                n_new += int((v != 0).sum())
                q_levels[lev][n]['esc'] = np.where(v != 0, v, q_levels[lev][n]['esc']).astype(np.int8)
        it += 1
        if n_new == 0:
            break
        conv += n_new
        if it >= max_iter:
            raise RuntimeError('closure did not converge')
    return q_levels, top, rec, {'iters': it, 'converted': conv}

def read_description(q_levels, top):
    """Canonical reading: per band coarsest consistent shift; symbols = index or escape."""
    desc = []
    bits = 0.0
    for lev, ql in enumerate(q_levels):
        dl = {}
        for n, d in ql.items():
            nv = d['val'][d['esc'] == 0]
            s = min(ctz_or(nv), 20)
            sym = np.where(d['esc'] != 0, (1 << 30) * d['esc'].astype(np.int64), d['val'] >> s)
            dl[n] = (s, sym)
            bits += entropy_bits(sym)
        desc.append(dl)
    nv = top['val'][top['esc'] == 0]
    s = min(ctz_or(nv), 20)
    sym = np.where(top['esc'] != 0, (1 << 30) * top['esc'].astype(np.int64), top['val'] >> s)
    desc.append(('top', s, sym))
    bits += entropy_bits(sym)
    return desc, bits

def decode_description(desc, lo, hi, n2d, n1d):
    q_levels = []
    for lev in range(n2d + n1d):
        ql = {}
        for n, (s, sym) in desc[lev].items():
            esc = np.where(np.abs(sym) >= (1 << 30), np.sign(sym), 0).astype(np.int8)
            ql[n] = {'val': np.where(esc != 0, 0, sym << s), 'esc': esc}
        q_levels.append(ql)
    _, s, sym = desc[-1]
    esc = np.where(np.abs(sym) >= (1 << 30), np.sign(sym), 0).astype(np.int8)
    top = {'val': np.where(esc != 0, 0, sym << s), 'esc': esc}
    rec, _, _ = synthesis(top, q_levels, lo, hi, n2d, n1d)
    return rec

def canonical_leaves(Y, lo, hi, n2d, n1d):
    """Next encoder on a decoded picture: exact leaves by canonical analysis."""
    levels, (L, tlo, thi) = analysis(Y, lo, hi, n2d, n1d)
    q_levels = []
    for lvl in levels:
        ql = {}
        for n, d in lvl.items():
            if n == 'win':
                continue
            ql[n] = {'val': np.where(d['esc'] != 0, 0, d['val']), 'esc': d['esc']}
        q_levels.append(ql)
    top = {'val': np.where((L >= thi) | (L <= tlo), 0, L),
           'esc': np.where(L >= thi, 1, np.where(L <= tlo, -1, 0)).astype(np.int8)}
    return q_levels, top

# ---------------------------------------------------------------- separable 5/3 baseline
def f53_1d(x, axis):
    x = np.moveaxis(x, axis, 0)
    e = x[0::2]; o = x[1::2]
    er = np.concatenate([e[1:], e[-1:]], 0)
    d = o - ((e + er) >> 1)
    dl = np.concatenate([d[:1], d[:-1]], 0)
    s = e + ((dl + d + 2) >> 2)
    return np.moveaxis(s, 0, axis), np.moveaxis(d, 0, axis)

def i53_1d(s, d, axis):
    s = np.moveaxis(s, axis, 0); d = np.moveaxis(d, axis, 0)
    dl = np.concatenate([d[:1], d[:-1]], 0)
    e = s - ((dl + d + 2) >> 2)
    er = np.concatenate([e[1:], e[-1:]], 0)
    o = d + ((e + er) >> 1)
    x = np.empty((e.shape[0] * 2,) + e.shape[1:], np.int64)
    x[0::2] = e; x[1::2] = o
    return np.moveaxis(x, 0, axis)

def sep_fwd(X, n2d, n1d):
    bands = []
    for lev in range(n2d + n1d):
        if lev < n2d:
            s, d = f53_1d(X, 1)
            ll, lh = f53_1d(s, 0)
            hl, hh = f53_1d(d, 0)
            bands.append({'HL': hl, 'LH': lh, 'HH': hh})
            X = ll
        else:
            s, d = f53_1d(X, 1)
            bands.append({'H': d})
            X = s
    return bands, X

def sep_inv(bands, X, n2d, n1d):
    for lev in reversed(range(n2d + n1d)):
        b = bands[lev]
        if lev < n2d:
            s = i53_1d(X, b['LH'], 0)
            d = i53_1d(b['HL'], b['HH'], 0)
            X = i53_1d(s, d, 1)
        else:
            X = i53_1d(X, b['H'], 1)
    return X
