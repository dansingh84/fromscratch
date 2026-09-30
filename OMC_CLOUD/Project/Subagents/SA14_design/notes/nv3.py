"""NEST v2 model (SA14): leaf-reading 5/3 (separable-equivalent) + INJECTIVE DEQUANTISATION (IDQ).
Every index maps to a legal value: in-window lattice points pred+q*2^s map to themselves; indices
beyond the window map, one to one, onto the off-lattice values of the window (ranked from the top for
the upper side, from the bottom for the lower side).  No clip, no rail symbol, no closure.
The next encoder inverts the map exactly (index recovery) given the same parameters.
Whole-frame transform (no slices) in this model; 2 x 2-D levels + 3 x 1-D horizontal levels."""
import numpy as np
N2, N1 = 2, 3
NL = N2 + N1
RAILPOL = 'all'
RAIL = 1 << 40   # sentinel magnitude in index arrays: +RAIL = upper bound, -RAIL = lower bound
STATS = {'sat': 0}

def par(sh):
    i = np.arange(sh[0])[:, None]; j = np.arange(sh[1])[None, :]
    return ((i + j) & 1).astype(np.int64)
def right(a): return np.concatenate([a[:, 1:], a[:, -1:]], 1)
def left(a): return np.concatenate([a[:, :1], a[:, :-1]], 1)
def down(a): return np.concatenate([a[1:], a[-1:]], 0)
def up(a): return np.concatenate([a[:1], a[:-1]], 0)
def PB(A): return (A + right(A) + par(A.shape)) >> 1
def PC(A): return (A + down(A) + par(A.shape)) >> 1
def PDS(A, B, C):
    return ((C + right(C) + par(C.shape)) >> 1) + ((B + down(B) + par(B.shape)) >> 1) \
        - ((A + right(A) + down(A) + down(right(A)) + 1 + par(A.shape)) >> 2)
def gB(u): return (up(u) + u + 1 + par(u.shape)) >> 2
def gC(u): return (left(u) + u + 1 + par(u.shape)) >> 2
def U2(b, c, d):
    s = 4 * (left(b) + b + up(c) + c) + (up(left(d)) + up(d) + left(d) + d)
    return (s + 7 + par(b.shape)) >> 4
def UH(b): return (left(b) + b + 1 + par(b.shape)) >> 2

# ------------------------------------------------------------------ plain analysis (source, and c_p of moved blocks)
def plain(X):
    """exact integer analysis; returns list of level dicts of leaf values and top LL."""
    lv = []
    for l in range(NL):
        if l < N2:
            A = X[0::2, 0::2]; B = X[0::2, 1::2]; C = X[1::2, 0::2]; D = X[1::2, 1::2]
            dD = D - PDS(A, B, C); dB = B - PB(A); dC = C - PC(A)
            lv.append({'B': dB + gB(dD), 'C': dC + gC(dD), 'D': dD})
            X = A + U2(dB, dC, dD)
        else:
            A = X[:, 0::2]; B = X[:, 1::2]; dB = B - PH(A)
            lv.append({'B': dB}); X = A + UH(dB)
    return lv, X
def PH(A): return (A + right(A) + par(A.shape)) >> 1

# ------------------------------------------------------------------ IDQ
def idq(pred, q, s, lo, hi, qmax):
    D = 1 << s
    qhi = (hi - pred) >> s
    qlo = -((pred - lo) >> s)
    v = pred + q * D
    Lt = pred + qhi * D; t0 = hi - Lt
    Lb = pred + qlo * D; b0 = Lb - lo
    k = q - qhi                        # top
    kp = k - t0 - 1; g = np.where(kp >= 0, kp // (D - 1), 0); r = np.where(kp >= 0, kp % (D - 1), 0)
    vt = np.where(k <= t0, hi - (k - 1), Lt - g * D - 1 - r)
    kb = qlo - q                       # bottom
    kp = kb - b0 - 1; g = np.where(kp >= 0, kp // (D - 1), 0); r = np.where(kp >= 0, kp % (D - 1), 0)
    vb = np.where(kb <= b0, lo + (kb - 1), Lb + g * D + 1 + r)
    pool = (hi - lo + 1) - np.maximum(0, qhi - qlo + 1)
    T = pool >> 1; Bc = pool - T
    over = ((q > qhi) & (k > T)) | ((q < qlo) & (kb > Bc))
    STATS['sat'] += int(over.sum())
    out = np.where(q > qhi, np.where(k > T, np.clip(vt, lo, hi), vt), np.where(q < qlo, np.where(kb > Bc, np.clip(vb, lo, hi), vb), v))
    out = np.clip(out, lo, hi)   # only saturated (non-conforming) indices can reach here out of range
    return out

def idq_inv(pred, v, s, lo, hi, qmax):
    D = 1 << s
    qhi = (hi - pred) >> s; qlo = -((pred - lo) >> s)
    on = ((v - pred) % D) == 0
    qin = (v - pred) >> s
    Lt = pred + qhi * D; t0 = hi - Lt; Lb = pred + qlo * D; b0 = Lb - lo
    j = hi - v; jp = Lt - v - 1
    kt = np.where(j < t0, j + 1, t0 + (np.maximum(jp, 0) // D) * (D - 1) + (np.maximum(jp, 0) % D) + 1)
    j = v - lo; jp = v - Lb - 1
    kb = np.where(j < b0, j + 1, b0 + (np.maximum(jp, 0) // D) * (D - 1) + (np.maximum(jp, 0) % D) + 1)
    pool = (hi - lo + 1) - np.maximum(0, qhi - qlo + 1)
    T = pool >> 1
    return np.where(on, qin, np.where(kt <= T, qhi + kt, qlo - kb))

# ------------------------------------------------------------------ codec pieces
class Params:
    """per plane: shifts[(lev,name)], shifts['top']; cp: list of level dicts (band prediction, 0 = intra)
    and cp_top; lo, hi."""
    pass

def qmax_for(s, lo, hi):
    return ((hi - lo) - (1 << s)) >> s

def windows(u_lv, lo, hi):
    """u_lv: per level dict of update values dB,dC,dD (2-D) / dB (1-D). returns per level (win dict, U) and top window."""
    wins = []
    for l in range(NL):
        u = u_lv[l]
        if l < N2:
            Uv = U2(u['B'], u['C'], u['D'])
            w = {'B': (lo[0::2, 1::2], hi[0::2, 1::2]), 'C': (lo[1::2, 0::2], hi[1::2, 0::2]), 'D': (lo[1::2, 1::2], hi[1::2, 1::2])}
            lo, hi = lo[0::2, 0::2] + Uv, hi[0::2, 0::2] + Uv
        else:
            Uv = UH(u['B'])
            w = {'B': (lo[:, 1::2], hi[:, 1::2])}
            lo, hi = lo[:, 0::2] + Uv, hi[:, 0::2] + Uv
        wins.append((w, Uv))
    return wins, (lo, hi)

RAILMASK = []
def upd_values(leaf_lv, rails=None):
    """from leaf values (c_p + R(q)) to update values dB, dC, dD; rail samples have update value 0."""
    out = []
    for l in range(NL):
        lf = leaf_lv[l]
        rm = rails[l] if rails is not None else {n: np.zeros(v.shape, bool) for n, v in lf.items()}
        if l < N2:
            dD = lf['D']
            out.append({'B': np.where(rm['B'], 0, lf['B'] - gB(dD)), 'C': np.where(rm['C'], 0, lf['C'] - gC(dD)), 'D': dD})
        else:
            out.append({'B': lf['B']})
    return out
def railmask(q_lv):
    return [{n: np.abs(q) >= RAIL for n, q in d.items()} for d in q_lv]

def decode(q_lv, q_top, P, lo0, hi0):
    """q_lv: indices per level; P: params. returns picture, leaf values."""
    leaf = leaves(q_lv, P)
    u_lv = upd_values(leaf, railmask(q_lv))
    wins, (tlo, thi) = windows(u_lv, lo0, hi0)
    st = P.sh['top']
    pred = np.clip(P.cp_top if P.cp_top is not None else tlo, tlo, thi)
    L = idq_r(pred, q_top, st, tlo, thi)
    for l in reversed(range(NL)):
        w, Uv = wins[l]; u = u_lv[l]
        A = L - Uv
        def put(n, raw):
            lo_, hi_ = w[n]; s = P.sh[(l, n)]
            return idq_r(raw, q_lv[l][n], s, lo_, hi_)
        if l < N2:
            B = put('B', P.cp[l]['B'] - gB(u['D']) + PB(A))
            C = put('C', P.cp[l]['C'] - gC(u['D']) + PC(A))
            D = put('D', P.cp[l]['D'] + PDS(A, B, C))
            X = np.empty((A.shape[0] * 2, A.shape[1] * 2), np.int64)
            X[0::2, 0::2] = A; X[0::2, 1::2] = B; X[1::2, 0::2] = C; X[1::2, 1::2] = D
        else:
            B = put('B', P.cp[l]['B'] + PH(A))
            X = np.empty((A.shape[0], A.shape[1] * 2), np.int64); X[:, 0::2] = A; X[:, 1::2] = B
        L = X
    return L, leaf

def recover(Y, P, lo0, hi0):
    """next encoder: exact index recovery from a decoded picture with the same parameters."""
    q_lv = []; X = Y; lo, hi = lo0, hi0
    for l in range(NL):
        q = {}
        if l < N2:
            A = X[0::2, 0::2]; B = X[0::2, 1::2]; C = X[1::2, 0::2]; D = X[1::2, 1::2]
            def inv(n, raw, val, lo_, hi_):
                s = P.sh[(l, n)]; pr = raw
                return idq_inv(pr, val, s, lo_, hi_, qmax_for(s, lo_, hi_))
            wD = (lo[1::2, 1::2], hi[1::2, 1::2]); wB = (lo[0::2, 1::2], hi[0::2, 1::2]); wC = (lo[1::2, 0::2], hi[1::2, 0::2])
            q['D'] = inv('D', P.cp[l]['D'] + PDS(A, B, C), D, *wD)
            uD = P.cp[l]['D'] + (q['D'] << P.sh[(l, 'D')])
            q['B'] = inv('B', P.cp[l]['B'] - gB(uD) + PB(A), B, *wB)
            q['C'] = inv('C', P.cp[l]['C'] - gC(uD) + PC(A), C, *wC)
            dB = P.cp[l]['B'] + (q['B'] << P.sh[(l, 'B')]) - gB(uD)
            dC = P.cp[l]['C'] + (q['C'] << P.sh[(l, 'C')]) - gC(uD)
            Uv = U2(dB, dC, uD)
            X = A + Uv; lo, hi = lo[0::2, 0::2] + Uv, hi[0::2, 0::2] + Uv
        else:
            A = X[:, 0::2]; B = X[:, 1::2]
            s = P.sh[(l, 'B')]; lo_, hi_ = lo[:, 1::2], hi[:, 1::2]
            pr = P.cp[l]['B'] + PH(A)
            q['B'] = idq_inv(pr, B, s, lo_, hi_, qmax_for(s, lo_, hi_))
            dB = P.cp[l]['B'] + (q['B'] << s)
            Uv = UH(dB); X = A + Uv; lo, hi = lo[:, 0::2] + Uv, hi[:, 0::2] + Uv
        q_lv.append(q)
    st = P.sh['top']
    pred = np.clip(P.cp_top if P.cp_top is not None else lo, lo, hi)
    q_top = idq_inv(pred, X, st, lo, hi, qmax_for(st, lo, hi))
    return q_lv, q_top

def Qdz(t, s, z16=9):
    off = ((16 - z16) << s) >> 4
    return np.sign(t) * ((np.abs(t) + off) >> s)

def encode(X, P, lo0, hi0, hold=None, z16=9):
    """gen-1: plain analysis of the source, open-loop quantisation against the band prediction,
    indices capped to the normative range; `hold` (per level dict of bool masks, same shapes) forces
    index 0 (exact repeat of the previous leaves where the prediction is the previous leaves)."""
    src, Ls = plain(X)
    q_lv = []
    for l in range(NL):
        q = {}
        for n, v in src[l].items():
            s = P.sh[(l, n)]; t = v - P.cp[l][n]
            qq = Qdz(t, s, z16)
            if hold is not None:
                qq = np.where(hold[l][n], 0, qq)
            q[n] = qq
        q_lv.append(q)
    st = P.sh['top']
    leaf = [{n: P.cp[l][n] + (q_lv[l][n] << P.sh[(l, n)]) for n in q_lv[l]} for l in range(NL)]
    _, (tlo, thi) = windows(upd_values(leaf), lo0, hi0)
    pred = np.clip(P.cp_top if P.cp_top is not None else tlo, tlo, thi)
    qt = Qdz(Ls - pred, st, z16)
    if hold is not None:
        qt = np.where(hold['top'], 0, qt)
    return q_lv, qt

def entropy_bits(sym):
    v, c = np.unique(sym, return_counts=True); p = c / c.sum()
    return float(-(c * np.log2(p)).sum())

def bits_of(q_lv, q_top):
    return sum(entropy_bits(q[n]) for q in q_lv for n in q) + entropy_bits(q_top)

def refine(X, q_lv, q_top, P, lo0, hi0, z16=9):
    """encoder-only, ONE fixed pass (quality, not correctness): re-quantise detail samples whose decoder
    prediction moved away from the source prediction by more than half a step (pinned evens near
    rails), against the decoder's actual prediction.  Any index set is legal and exact."""
    src, Ls = plain(X)
    # source sample values per level (the plain analysis low bands)
    lows = [X]; Y = X
    for l in range(NL):
        Y = (Y[0::2, 0::2] if l < N2 else Y[:, 0::2]) + 0
        lows.append(None)
    # recompute source low bands exactly
    lowsrc = [X]; Z = X
    for l in range(NL):
        if l < N2:
            A = Z[0::2, 0::2]; B = Z[0::2, 1::2]; C = Z[1::2, 0::2]; D = Z[1::2, 1::2]
            dD = D - PDS(A, B, C); dB = B - PB(A); dC = C - PC(A); Z = A + U2(dB, dC, dD)
        else:
            A = Z[:, 0::2]; B = Z[:, 1::2]; Z = A + UH(B - PH(A))
        lowsrc.append(Z)
    leaf = [{n: P.cp[l][n] + (q_lv[l][n] << P.sh[(l, n)]) for n in q_lv[l]} for l in range(NL)]
    u_lv = upd_values(leaf)
    wins, (tlo, thi) = windows(u_lv, lo0, hi0)
    st = P.sh['top']
    pred = np.clip(P.cp_top if P.cp_top is not None else tlo, tlo, thi)
    L = idq(pred, q_top, st, tlo, thi, 0)
    nre = 0
    for l in reversed(range(NL)):
        w, Uv = wins[l]; u = u_lv[l]; S = lowsrc[l]
        A = L - Uv
        def req(n, raw, srcval):
            nonlocal nre
            s = P.sh[(l, n)]; lo_, hi_ = w[n]
            qn = q_lv[l][n]
            virt = raw + (qn << s)
            bad = (virt > hi_) | (virt < lo_)
            # beyond samples: pick, among {in-window top/bottom lattice index, first beyond index}, the one
            # whose mapped value is nearest the source value
            qhi = (hi_ - raw) >> s; qlo = -((raw - lo_) >> s)
            cands = [np.where(virt > hi_, qhi, qlo), np.where(virt > hi_, qhi + 1, qlo - 1), qn]
            vals = [idq(raw, c, s, lo_, hi_, 0) for c in cands]
            best = cands[0].copy(); bv = np.abs(vals[0] - srcval)
            for c, v in zip(cands[1:], vals[1:]):
                better = np.abs(v - srcval) < bv; best = np.where(better, c, best); bv = np.where(better, np.abs(v - srcval), bv)
            newq = np.where(bad, best, qn); nre += int((newq != qn).sum())
            q_lv[l][n] = newq
            return idq(raw, newq, s, lo_, hi_, 0)
        if l < N2:
            B = req('B', P.cp[l]['B'] - gB(u['D']) + PB(A), S[0::2, 1::2])
            C = req('C', P.cp[l]['C'] - gC(u['D']) + PC(A), S[1::2, 0::2])
            D = req('D', P.cp[l]['D'] + PDS(A, B, C), S[1::2, 1::2])
            Xo = np.empty((A.shape[0] * 2, A.shape[1] * 2), np.int64)
            Xo[0::2, 0::2] = A; Xo[0::2, 1::2] = B; Xo[1::2, 0::2] = C; Xo[1::2, 1::2] = D
        else:
            B = req('B', P.cp[l]['B'] + PH(A), S[:, 1::2])
            Xo = np.empty((A.shape[0], A.shape[1] * 2), np.int64); Xo[:, 0::2] = A; Xo[:, 1::2] = B
        L = Xo
    return q_lv, q_top, nre


def leaves(q_lv, P):
    out = []
    for l in range(NL):
        d = {}
        for n, q in q_lv[l].items():
            rail = np.abs(q) >= RAIL
            d[n] = np.where(rail, 0, P.cp[l][n] + (np.where(rail, 0, q) << P.sh[(l, n)]))
            if n == 'D' or l >= N2:
                pass
        out.append(d)
    return out

def idq_r(pred, q, s, lo, hi):
    """rails -> bound; others -> IDQ inside the open interior [lo+1, hi-1]."""
    rail = np.abs(q) >= RAIL
    qq = np.where(rail, 0, q)
    v = idq(pred, qq, s, lo + 1, hi - 1, 0)
    return np.where(q >= RAIL, hi, np.where(q <= -RAIL, lo, v))

def idq_r_inv(pred, v, s, lo, hi):
    q = idq_inv(pred, v, s, lo + 1, hi - 1, 0)
    return np.where(v >= hi, RAIL, np.where(v <= lo, -RAIL, q))

def encode3(X, P, lo0, hi0, hold=None, z16=9, rails=True):
    """gen-1: analysis of the source with rail detection (sample on its source window bound -> RAIL,
    update value 0, so the low band is consistent); open-loop quantisation of the others against the
    band prediction.  hold: per level dict of bool masks forcing index 0 (exact repeat)."""
    q_lv = []; Z = X; lo, hi = lo0, hi0
    for l in range(NL):
        q = {}
        if l < N2:
            A = Z[0::2, 0::2]; B = Z[0::2, 1::2]; C = Z[1::2, 0::2]; D = Z[1::2, 1::2]
            w = {'B': (lo[0::2, 1::2], hi[0::2, 1::2]), 'C': (lo[1::2, 0::2], hi[1::2, 0::2]), 'D': (lo[1::2, 1::2], hi[1::2, 1::2])}
            fin = {'B': B, 'C': C, 'D': D}
            dD = D - PDS(A, B, C)
            rD = (D >= w['D'][1]) | (D <= w['D'][0]) if rails else np.zeros(D.shape, bool)
            if RAILPOL == 'zero': rD = rD & (Qdz(dD - P.cp[l]['D'], P.sh[(l, 'D')], z16) == 0)
            uD = np.where(rD, 0, dD)
            dB = B - PB(A); dC = C - PC(A)
            rB = (B >= w['B'][1]) | (B <= w['B'][0]) if rails else np.zeros(B.shape, bool)
            rC = (C >= w['C'][1]) | (C <= w['C'][0]) if rails else np.zeros(C.shape, bool)
            if RAILPOL == 'zero':
                rB = rB & (Qdz(dB + gB(uD) - P.cp[l]['B'], P.sh[(l, 'B')], z16) == 0)
                rC = rC & (Qdz(dC + gC(uD) - P.cp[l]['C'], P.sh[(l, 'C')], z16) == 0)
            tgt = {'B': dB + gB(uD), 'C': dC + gC(uD), 'D': dD}
            rm = {'B': rB, 'C': rC, 'D': rD}
            uB = np.where(rB, 0, dB); uC = np.where(rC, 0, dC)
            Uv = U2(uB, uC, uD)
            Znew = A + Uv; lo, hi = lo[0::2, 0::2] + Uv, hi[0::2, 0::2] + Uv
        else:
            A = Z[:, 0::2]; B = Z[:, 1::2]
            w = {'B': (lo[:, 1::2], hi[:, 1::2])}; fin = {'B': B}
            dB = B - PH(A)
            rB = (B >= w['B'][1]) | (B <= w['B'][0]) if rails else np.zeros(B.shape, bool)
            if RAILPOL == 'zero': rB = rB & (Qdz(dB - P.cp[l]['B'], P.sh[(l, 'B')], z16) == 0)
            tgt = {'B': dB}; rm = {'B': rB}
            Uv = UH(np.where(rB, 0, dB))
            Znew = A + Uv; lo, hi = lo[:, 0::2] + Uv, hi[:, 0::2] + Uv
        for n in tgt:
            s = P.sh[(l, n)]
            qq = Qdz(tgt[n] - P.cp[l][n], s, z16)
            if hold is not None:
                qq = np.where(hold[l][n], 0, qq)
            side = np.where(fin[n] >= w[n][1], RAIL, -RAIL)
            q[n] = np.where(rm[n], side, qq)
        q_lv.append(q)
        Z = Znew
    st = P.sh['top']
    leaf = leaves(q_lv, P)
    _, (tlo, thi) = windows(upd_values(leaf, railmask(q_lv)), lo0, hi0)
    pred = np.clip(P.cp_top if P.cp_top is not None else tlo, tlo, thi)
    qt = Qdz(Z - pred, st, z16)
    if hold is not None:
        qt = np.where(hold['top'], 0, qt)
    if rails:
        qt = np.where(Z >= thi, RAIL, np.where(Z <= tlo, -RAIL, qt))
    return q_lv, qt

def recover3(Y, P, lo0, hi0):
    q_lv = []; X = Y; lo, hi = lo0, hi0
    for l in range(NL):
        q = {}
        if l < N2:
            A = X[0::2, 0::2]; B = X[0::2, 1::2]; C = X[1::2, 0::2]; D = X[1::2, 1::2]
            wD = (lo[1::2, 1::2], hi[1::2, 1::2]); wB = (lo[0::2, 1::2], hi[0::2, 1::2]); wC = (lo[1::2, 0::2], hi[1::2, 0::2])
            q['D'] = idq_r_inv(P.cp[l]['D'] + PDS(A, B, C), D, P.sh[(l, 'D')], *wD)
            rD = np.abs(q['D']) >= RAIL
            uD = np.where(rD, 0, P.cp[l]['D'] + (np.where(rD, 0, q['D']) << P.sh[(l, 'D')]))
            q['B'] = idq_r_inv(P.cp[l]['B'] - gB(uD) + PB(A), B, P.sh[(l, 'B')], *wB)
            q['C'] = idq_r_inv(P.cp[l]['C'] - gC(uD) + PC(A), C, P.sh[(l, 'C')], *wC)
            rB = np.abs(q['B']) >= RAIL; rC = np.abs(q['C']) >= RAIL
            dB = np.where(rB, 0, P.cp[l]['B'] + (np.where(rB, 0, q['B']) << P.sh[(l, 'B')]) - gB(uD))
            dC = np.where(rC, 0, P.cp[l]['C'] + (np.where(rC, 0, q['C']) << P.sh[(l, 'C')]) - gC(uD))
            Uv = U2(dB, dC, uD)
            X = A + Uv; lo, hi = lo[0::2, 0::2] + Uv, hi[0::2, 0::2] + Uv
        else:
            A = X[:, 0::2]; B = X[:, 1::2]; s = P.sh[(l, 'B')]
            q['B'] = idq_r_inv(P.cp[l]['B'] + PH(A), B, s, lo[:, 1::2], hi[:, 1::2])
            rB = np.abs(q['B']) >= RAIL
            dB = np.where(rB, 0, P.cp[l]['B'] + (np.where(rB, 0, q['B']) << s))
            Uv = UH(dB); X = A + Uv; lo, hi = lo[:, 0::2] + Uv, hi[:, 0::2] + Uv
        q_lv.append(q)
    st = P.sh['top']
    pred = np.clip(P.cp_top if P.cp_top is not None else lo, lo, hi)
    return q_lv, idq_r_inv(pred, X, st, lo, hi)

def symbols(q):
    return np.where(q >= RAIL, 1 << 30, np.where(q <= -RAIL, -(1 << 30), q))

def bits3(q_lv, q_top):
    return sum(entropy_bits(symbols(q[n])) for q in q_lv for n in q) + entropy_bits(symbols(q_top))
