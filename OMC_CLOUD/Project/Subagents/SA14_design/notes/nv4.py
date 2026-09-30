"""NEST v4 model (SA14 round 3): everything together, per plane.
- Shifted causal slices (S rows; the first row of a slice is predicted from the slice above's FINAL row;
  the last row of a slice is a low row whose update from below is zero).  2 vertical+horizontal levels
  inside the slice, then 3 horizontal-only levels.
- Leaf-reading 5/3 (separable-equivalent): every update reads transmitted leaf values.
- Injective dequantisation (IDQ) over the FULL legal window, no rail symbols.
- Encoder: open-loop quantisation, then ONE coarse-to-fine pass that, level by level, picks for every
  predicted sample the index (among: open-loop, nearest in-window, first beyond) whose decoded value is
  nearest the source value of that level (fixed tie-break), then finalises the level.
- Next encoder: exact index recovery from the picture (same parameters).
Integer only; >> is floor."""
import numpy as np

def par(sh):
    i = np.arange(sh[0])[:, None]; j = np.arange(sh[1])[None, :]
    return ((i + j) & 1).astype(np.int64)
def right(a): return np.concatenate([a[:, 1:], a[:, -1:]], 1)
def left(a): return np.concatenate([a[:, :1], a[:, :-1]], 1)
def zbelow(a): return np.concatenate([a[1:], np.zeros_like(a[:1])], 0)   # row below, zero past the slice

# ---------------------------------------------------------------- IDQ (full window)
STATS = {'sat': 0}
CLIP = False
class Params: pass
def idq(pred, q, s, lo, hi):
    D = 1 << s
    if CLIP:
        return pred + q * D
    qhi = (hi - pred) >> s; qlo = -((pred - lo) >> s)
    v = pred + q * D
    Lt = pred + qhi * D; t0 = hi - Lt; Lb = pred + qlo * D; b0 = Lb - lo
    k = q - qhi; kp = k - t0 - 1
    g = np.where(kp >= 0, kp // (D - 1), 0); r = np.where(kp >= 0, kp % (D - 1), 0)
    vt = np.where(k <= t0, hi - (k - 1), Lt - g * D - 1 - r)
    kb = qlo - q; kp = kb - b0 - 1
    g = np.where(kp >= 0, kp // (D - 1), 0); r = np.where(kp >= 0, kp % (D - 1), 0)
    vb = np.where(kb <= b0, lo + (kb - 1), Lb + g * D + 1 + r)
    pool = (hi - lo + 1) - np.maximum(0, qhi - qlo + 1); T = pool >> 1; Bc = pool - T
    over = ((q > qhi) & (k > T)) | ((q < qlo) & (kb > Bc))
    STATS['sat'] += int(over.sum())
    out = np.where(q > qhi, vt, np.where(q < qlo, vb, v))
    return np.clip(out, lo, hi)

def idq_inv(pred, v, s, lo, hi):
    D = 1 << s
    qhi = (hi - pred) >> s; qlo = -((pred - lo) >> s)
    on = ((v - pred) % D) == 0; qin = (v - pred) >> s
    Lt = pred + qhi * D; t0 = hi - Lt; Lb = pred + qlo * D; b0 = Lb - lo
    j = hi - v; jp = np.maximum(Lt - v - 1, 0)
    kt = np.where(j < t0, j + 1, t0 + (jp // D) * (D - 1) + (jp % D) + 1)
    j = v - lo; jp = np.maximum(v - Lb - 1, 0)
    kb = np.where(j < b0, j + 1, b0 + (jp // D) * (D - 1) + (jp % D) + 1)
    pool = (hi - lo + 1) - np.maximum(0, qhi - qlo + 1); T = pool >> 1
    return np.where(on, qin, np.where(kt <= T, qhi + kt, qlo - kb))

NOCHOICE = False
def choose(pred, q0, s, lo, hi, src):
    if NOCHOICE: return q0
    """source-faithful index: among the open-loop index, the nearest in-window lattice index and the first
    beyond index on the side of the overshoot, the one decoding nearest the source value (ties: open-loop,
    then nearest in-window)."""
    D = 1 << s
    qhi = (hi - pred) >> s; qlo = -((pred - lo) >> s)
    qn = np.clip(np.where(src >= pred, (src - pred + (D >> 1)) >> s, -((pred - src + (D >> 1)) >> s)), qlo, qhi)
    qb = np.where(pred + q0 * D > hi, qhi + 1, np.where(pred + q0 * D < lo, qlo - 1, q0))
    beyond = (pred + q0 * D > hi) | (pred + q0 * D < lo)
    qn = np.where(beyond, np.where(pred + q0 * D > hi, qhi, qlo), q0)   # the in-window bound-side index
    qb = np.where(beyond, qb, q0)
    best = q0; be = np.abs(idq(pred, q0, s, lo, hi) - src)
    for c in (qn, qb):
        e = np.abs(idq(pred, c, s, lo, hi) - src)
        better = e < be; best = np.where(better, c, best); be = np.where(better, e, be)
    return best

# ---------------------------------------------------------------- one shifted 2-D level
def split2(X, T):
    """X: slice rows (R even), T: final row above.  Returns A_all (m+1 rows, row 0 = top), B_all, C, D."""
    A = np.concatenate([T[None, 0::2], X[1::2, 0::2]], 0)
    B = np.concatenate([T[None, 1::2], X[1::2, 1::2]], 0)
    return A, B, X[0::2, 0::2], X[0::2, 1::2]

def merge2(A1, B1, C, D):
    m, w = C.shape
    X = np.empty((2 * m, A1.shape[1] + B1.shape[1]), np.int64)
    X[1::2, 0::2] = A1; X[1::2, 1::2] = B1; X[0::2, 0::2] = C; X[0::2, 1::2] = D
    return X

def PB(A1): return (A1 + right(A1) + par(A1.shape)) >> 1
def PC(Aall): return (Aall[:-1] + Aall[1:] + par(Aall[1:].shape)) >> 1
def PD(Aall, Ball, C):
    return ((C + right(C) + par(C.shape)) >> 1) + ((Ball[:-1] + Ball[1:] + par(C.shape)) >> 1) \
        - ((Aall[:-1] + right(Aall[:-1]) + Aall[1:] + right(Aall[1:]) + 1 + par(C.shape)) >> 2)
def gB(uD): return (uD + zbelow(uD) + 1 + par(uD.shape)) >> 2          # B row j: D above (row j-1) and below (row j)
def gC(uD): return (left(uD) + uD + 1 + par(uD.shape)) >> 2
def U2(uB, uC, uD):
    s = 4 * (left(uB) + uB + uC + zbelow(uC)) + (left(uD) + uD + left(zbelow(uD)) + zbelow(uD))
    return (s + 7 + par(uB.shape)) >> 4
def PH(A): return (A + right(A) + par(A.shape)) >> 1
def UH(uB): return (left(uB) + uB + 1 + par(uB.shape)) >> 2

N2, N1 = 2, 3
NL = N2 + N1

# ---------------------------------------------------------------- per slice: plain analysis (source / prediction)
def plain(X, tops):
    """tops: [final pixel row above, final level-1 low row above].  Returns leaf dicts per level, top LL,
    and the per-level source sample values (for the source-faithful choice)."""
    lv = []; vals = []; Z = X
    for l in range(NL):
        if l < N2:
            Aall, Ball, C, D = split2(Z, tops[l])
            dD = D - PD(Aall, Ball, C); dB = Ball[1:] - PB(Aall[1:]); dC = C - PC(Aall)
            lv.append({'B': dB + gB(dD), 'C': dC + gC(dD), 'D': dD})
            vals.append({'B': Ball[1:], 'C': C, 'D': D})
            Z = Aall[1:] + U2(dB, dC, dD)
        else:
            A = Z[:, 0::2]; B = Z[:, 1::2]; dB = B - PH(A)
            lv.append({'B': dB}); vals.append({'B': B}); Z = A + UH(dB)
    return lv, Z, vals

def upd(leaf):
    out = []
    for l in range(NL):
        lf = leaf[l]
        if l < N2:
            out.append({'B': lf['B'] - gB(lf['D']), 'C': lf['C'] - gC(lf['D']), 'D': lf['D']})
        else:
            out.append({'B': lf['B']})
    return out

def windows(u, lo, hi):
    wins = []
    for l in range(NL):
        if l < N2:
            Uv = U2(u[l]['B'], u[l]['C'], u[l]['D'])
            w = {'B': (lo[1::2, 1::2], hi[1::2, 1::2]), 'C': (lo[0::2, 0::2], hi[0::2, 0::2]), 'D': (lo[0::2, 1::2], hi[0::2, 1::2])}
            lo, hi = lo[1::2, 0::2] + Uv, hi[1::2, 0::2] + Uv
        else:
            Uv = UH(u[l]['B']); w = {'B': (lo[:, 1::2], hi[:, 1::2])}
            lo, hi = lo[:, 0::2] + Uv, hi[:, 0::2] + Uv
        wins.append((w, Uv))
    return wins, (lo, hi)

def synth(q, qt, P, lo, hi, tops, src=None, srctop=None):
    """decoder (src None) or the encoder's single source-faithful pass (src = per-level source values).
    Returns picture, final indices, leaves, and the final level-1 low rows (for the next slice's top)."""
    q = [dict(d) for d in q]
    def leafs(q):
        return [{n: P.cp[l][n] + (q[l][n] << P.sh[(l, n)]) for n in q[l]} for l in range(NL)]
    st = P.sh['top']
    wins, (tlo, thi) = windows(upd(leafs(q)), lo, hi)
    tp = np.clip(P.cp_top if P.cp_top is not None else tlo, tlo, thi)
    if src is not None:
        qc = choose(tp, qt, st, tlo, thi, srctop)
        ft = getattr(P, 'fixed_top', None)
        qt = np.where(ft, qt, qc) if ft is not None else qc
    L = idq(tp, qt, st, tlo, thi)
    lows = {}
    for l in reversed(range(NL)):
        for phase in ((0,) if src is not None else (1,)):
            u = upd(leafs(q)); wins, _ = windows(u, lo, hi); w, Uv = wins[l]
            if l < N2:
                Aall = np.concatenate([tops[l][None, 0::2], L - Uv], 0)
                def put(n, raw):
                    s = P.sh[(l, n)]; lo_, hi_ = w[n]
                    if phase == 0:
                        qc = choose(raw, q[l][n], s, lo_, hi_, src[l][n])
                        fx = getattr(P, 'fixed', None)
                        q[l][n] = np.where(fx[l][n], q[l][n], qc) if fx is not None else qc
                    return idq(raw, q[l][n], s, lo_, hi_)
                B1 = put('B', P.cp[l]['B'] - gB(u[l]['D']) + PB(Aall[1:]))
                Ball = np.concatenate([tops[l][None, 1::2], B1], 0)
                C = put('C', P.cp[l]['C'] - gC(u[l]['D']) + PC(Aall))
                D = put('D', P.cp[l]['D'] + PD(Aall, Ball, C))
                X = merge2(Aall[1:], B1, C, D)
            else:
                A = L - Uv
                s = P.sh[(l, 'B')]; lo_, hi_ = w['B']; raw = P.cp[l]['B'] + PH(A)
                if phase == 0:
                    qc = choose(raw, q[l]['B'], s, lo_, hi_, src[l]['B'])
                    fx = getattr(P, 'fixed', None)
                    q[l]['B'] = np.where(fx[l]['B'], q[l]['B'], qc) if fx is not None else qc
                B = idq(raw, q[l]['B'], s, lo_, hi_)
                X = np.empty((A.shape[0], A.shape[1] * 2), np.int64); X[:, 0::2] = A; X[:, 1::2] = B
            if phase == 0:
                u = upd(leafs(q)); wins, _ = windows(u, lo, hi); w, Uv = wins[l]
                X = None
        if src is not None:
            # provisional value of this level for the next finer level's choices
            X = _level_values(l, L, q, P, lo, hi, tops)
        lows[l] = X
        L = X
    if src is not None:
        # final decode (the decoder's own single pass) with the chosen indices
        return synth(q, qt, P, lo, hi, tops)
    return L, q, qt, leafs(q), lows[1][-1] if N2 > 1 else None

def _level_values(l, L, q, P, lo, hi, tops):
    leaf = [{n: P.cp[k][n] + (q[k][n] << P.sh[(k, n)]) for n in q[k]} for k in range(NL)]
    u = upd(leaf); wins, _ = windows(u, lo, hi); w, Uv = wins[l]
    if l < N2:
        Aall = np.concatenate([tops[l][None, 0::2], L - Uv], 0)
        B1 = idq(P.cp[l]['B'] - gB(u[l]['D']) + PB(Aall[1:]), q[l]['B'], P.sh[(l, 'B')], *w['B'])
        Ball = np.concatenate([tops[l][None, 1::2], B1], 0)
        C = idq(P.cp[l]['C'] - gC(u[l]['D']) + PC(Aall), q[l]['C'], P.sh[(l, 'C')], *w['C'])
        D = idq(P.cp[l]['D'] + PD(Aall, Ball, C), q[l]['D'], P.sh[(l, 'D')], *w['D'])
        return merge2(Aall[1:], B1, C, D)
    A = L - Uv
    B = idq(P.cp[l]['B'] + PH(A), q[l]['B'], P.sh[(l, 'B')], *w['B'])
    X = np.empty((A.shape[0], A.shape[1] * 2), np.int64); X[:, 0::2] = A; X[:, 1::2] = B
    return X

def recover(Y, P, lo, hi, tops):
    q = []; X = Y
    for l in range(NL):
        d = {}
        if l < N2:
            Aall, Ball, C, D = split2(X, tops[l])
            wD = (lo[0::2, 1::2], hi[0::2, 1::2]); wB = (lo[1::2, 1::2], hi[1::2, 1::2]); wC = (lo[0::2, 0::2], hi[0::2, 0::2])
            d['D'] = idq_inv(P.cp[l]['D'] + PD(Aall, Ball, C), D, P.sh[(l, 'D')], *wD)
            uD = P.cp[l]['D'] + (d['D'] << P.sh[(l, 'D')])
            d['B'] = idq_inv(P.cp[l]['B'] - gB(uD) + PB(Aall[1:]), Ball[1:], P.sh[(l, 'B')], *wB)
            d['C'] = idq_inv(P.cp[l]['C'] - gC(uD) + PC(Aall), C, P.sh[(l, 'C')], *wC)
            uB = P.cp[l]['B'] + (d['B'] << P.sh[(l, 'B')]) - gB(uD)
            uC = P.cp[l]['C'] + (d['C'] << P.sh[(l, 'C')]) - gC(uD)
            Uv = U2(uB, uC, uD)
            X = Aall[1:] + Uv; lo, hi = lo[1::2, 0::2] + Uv, hi[1::2, 0::2] + Uv
        else:
            A = X[:, 0::2]; B = X[:, 1::2]; s = P.sh[(l, 'B')]
            d['B'] = idq_inv(P.cp[l]['B'] + PH(A), B, s, lo[:, 1::2], hi[:, 1::2])
            Uv = UH(P.cp[l]['B'] + (d['B'] << s)); X = A + Uv; lo, hi = lo[:, 0::2] + Uv, hi[:, 0::2] + Uv
        q.append(d)
    tp = np.clip(P.cp_top if P.cp_top is not None else lo, lo, hi)
    return q, idq_inv(tp, X, P.sh['top'], lo, hi)

def Qdz(t, s, z16=9):
    off = ((16 - z16) << s) >> 4
    return np.sign(t) * ((np.abs(t) + off) >> s)

def quantise(lv, Ltop, P, hold=None):
    q = [{n: Qdz(v - P.cp[l][n], P.sh[(l, n)]) for n, v in lv[l].items()} for l in range(NL)]
    if hold is not None:
        for l in range(NL):
            for n in q[l]:
                q[l][n] = np.where(hold[l][n], 0, q[l][n])
    return q

def quantise_top(Ltop, P, lo, hi, q, hold_top=None):
    leaf = [{n: P.cp[l][n] + (q[l][n] << P.sh[(l, n)]) for n in q[l]} for l in range(NL)]
    _, (tlo, thi) = windows(upd(leaf), lo, hi)
    tp = np.clip(P.cp_top if P.cp_top is not None else tlo, tlo, thi)
    qt = Qdz(Ltop - tp, P.sh['top'])
    if hold_top is not None:
        qt = np.where(hold_top, 0, qt)
    return qt

def entropy_bits(sym):
    v, c = np.unique(sym, return_counts=True); p = c / c.sum()
    return float(-(c * np.log2(p)).sum())

def last_top(q, qt, P, lo, hi):
    leaf = [{n: P.cp[l][n] + (q[l][n] << P.sh[(l, n)]) for n in q[l]} for l in range(NL)]
    _, (tlo, thi) = windows(upd(leaf), lo, hi)
    tp = np.clip(P.cp_top if P.cp_top is not None else tlo, tlo, thi)
    return idq(tp, qt, P.sh['top'], tlo, thi)

def last_low1(X, tops):
    """plain-analysis level-1 low band, last row (the prediction image's own top for the next slice)."""
    Aall, Ball, C, D = split2(X, tops[0])
    dD = D - PD(Aall, Ball, C); dB = Ball[1:] - PB(Aall[1:]); dC = C - PC(Aall)
    Z = Aall[1:] + U2(dB, dC, dD)
    Aall, Ball, C, D = split2(Z, tops[1])
    return Z[-1]
