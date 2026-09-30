# SA17 pair pyramid ("quad" levels 1..Lv, horizontal pair levels Lv+1..Lh), continuous over the whole plane.
# Every leaf is predicted from values that are already FINAL and read by nothing but its own pair:
#   level l quad:  LL -> HL (horizontal pair of the vertical-mean row VM) -> LH, HH (horizontal pair of the
#   vertical-difference row VD) -> pixels (vertical pair of VM, VD).
# Legality: each leaf is clamped into the set that keeps its pair's outputs in their target intervals,
# computed from final values only (acyclic). Canonical index = smallest |q| whose clamped value reproduces.
import numpy as np

def par(h, w, off=0):
    return ((np.arange(h)[:, None] + np.arange(w)[None, :] + off) & 1).astype(np.int64)

# ---------------- integer S-transform pair with parity-alternating rounding ----------------
def pa(a, b, pi):
    return (a + b + pi) >> 1, a - b
def ps(m, d, pi):
    s = 2 * m - pi + ((d + pi) & 1)
    return (s + d) >> 1, (s - d) >> 1

def dset(m, pi, alo, ahi, blo, bhi):
    """feasible d (per parity) for a pair with mean m and a in [alo,ahi], b in [blo,bhi].
    returns (lo0,hi0,lo1,hi1): d even in [lo0,hi0] or d odd in [lo1,hi1] (after parity rounding)."""
    out = []
    for p in (0, 1):
        s = 2 * m - pi + ((p + pi) & 1)
        lo_ = np.maximum(2 * alo - s, s - 2 * bhi); hi_ = np.minimum(2 * ahi - s, s - 2 * blo)
        lo_ = lo_ + ((lo_ - p) & 1); hi_ = hi_ - ((hi_ - p) & 1)       # snap to parity p
        out += [lo_, hi_]
    return out

def dclamp(v, S):
    """nearest feasible value to v in the parity-union set S (ties -> toward 0). exact, monotone."""
    lo0, hi0, lo1, hi1 = S
    c0 = np.clip(v, lo0, hi0); c0 = np.where((c0 - v) & 1, c0 + np.where(c0 < hi0, 1, -1), c0)
    c1 = np.clip(v, lo1, hi1); c1 = np.where((c1 - v - 1) & 1, c1 + np.where(c1 < hi1, 1, -1), c1)
    e0 = lo0 <= hi0; e1 = lo1 <= hi1
    # c0 must be even-parity member: recompute cleanly
    c0 = np.clip(v, lo0, hi0); c0 = c0 - ((c0 & 1) != 0) * np.where(c0 > lo0, 1, -1)
    c1 = np.clip(v, lo1, hi1); c1 = c1 - ((c1 & 1) != 1) * np.where(c1 > lo1, 1, -1)
    d0 = np.where(e0, np.abs(c0 - v), 1 << 40); d1 = np.where(e1, np.abs(c1 - v), 1 << 40)
    pick1 = (d1 < d0) | ((d1 == d0) & (np.abs(c1) < np.abs(c0)))
    return np.where(pick1, c1, c0)

def inner(S):
    """largest interval all of whose integers are feasible (target interval for the next pair)."""
    lo0, hi0, lo1, hi1 = S
    e0 = lo0 <= hi0; e1 = lo1 <= hi1
    L = np.minimum(lo0, lo1); L = np.where(np.maximum(lo0, lo1) > L + 1, np.maximum(lo0, lo1) - 1, L)
    U = np.maximum(hi0, hi1); U = np.where(np.minimum(hi0, hi1) < U - 1, np.minimum(hi0, hi1) + 1, U)
    L = np.where(e0 & e1, L, np.where(e0, lo0, lo1)); U = np.where(e0 & e1, U, np.where(e0, lo0, lo1))
    return L, U

def mset(pi, J0lo, J0hi, J1lo, J1hi):
    """feasible means for a pair whose outputs must lie in J0 x J1 (intervals)."""
    return (J0lo + J1lo + pi) >> 1, (J0hi + J1hi + pi) >> 1

# ---------------- 2/6 slope predictors from final means (mirror at plane edges) ----------------
def mir(a, k, axis):
    n = a.shape[axis]; i = np.arange(n) + k
    i = np.where(i < 0, -i, i); i = np.where(i > n - 1, 2 * (n - 1) - i, i)
    return np.take(a, i, axis=axis)
LIMIT = False
RANGELIM = None
RAILLIM = None          # (lo, hi): limit the slope only where the unlimited predicted pair would leave [lo, hi]
def slope(m, axis, pi):
    s = (mir(m, -1, axis) - mir(m, 1, axis) + 1 + pi) >> 2
    if RANGELIM is not None:
        # continuous: shrink the slope just enough that the predicted pair m +- s/2 stays in [lo, hi]
        lo, hi = RANGELIM
        cap = np.maximum(0, np.minimum(2 * (hi - m), 2 * (m - lo)))
        return np.sign(s) * np.minimum(np.abs(s), cap)
    if RAILLIM is not None:
        lo, hi = RAILLIM
        a = 2 * (mir(m, -1, axis) - m); b = 2 * (m - mir(m, 1, axis))
        same = (np.sign(s) == np.sign(a)) & (np.sign(s) == np.sign(b))
        mag = np.minimum(np.abs(s), np.minimum(np.abs(a), np.abs(b)))
        lim = np.where(same, np.sign(s) * mag, 0)
        hs = (np.abs(s) + 1) >> 1
        out = (m + hs > hi) | (m - hs < lo)
        return np.where(out, lim, s)
    if not LIMIT: return s
    # TVD limiter: the predicted pair never leaves the range of its neighbouring means (no new extremum,
    # no prediction-made overshoot). minmod(s, 2(m[-1]-m), 2(m-m[+1])), integer, from final values only.
    a = 2 * (mir(m, -1, axis) - m); b = 2 * (m - mir(m, 1, axis))
    same = (np.sign(s) == np.sign(a)) & (np.sign(s) == np.sign(b))
    mag = np.minimum(np.abs(s), np.minimum(np.abs(a), np.abs(b)))
    return np.where(same, np.sign(s) * mag, 0)

# ---------------- analysis (open loop, plain) ----------------
def analysis(x, Lv=2, Lh=5):
    T = {}; ll = x.astype(np.int64)
    for l in range(1, Lv + 1):
        h, w = ll.shape
        VM, VD = pa(ll[0::2], ll[1::2], par(h // 2, w))
        pv = par(h // 2, w // 2)
        LL, HLr = pa(VM[:, 0::2], VM[:, 1::2], pv)
        LHm, HHr = pa(VD[:, 0::2], VD[:, 1::2], pv)
        T['HL%d' % l] = HLr - slope(LL, 1, pv)
        T['LH%d' % l] = LHm - slope(LL, 0, pv)
        T['HH%d' % l] = HHr - hhpred(HLr, LHm, pv)
        ll = LL
    for l in range(Lv + 1, Lh + 1):
        h, w = ll.shape; pv = par(h, w // 2, l)
        m, d = pa(ll[:, 0::2], ll[:, 1::2], pv)
        T['H%d' % l] = d - slope(m, 1, pv); ll = m
    T['LL'] = ll
    return T

def hhpred(HLr, LHm, pv):
    # symmetric: vertical slope of the horizontal detail + horizontal slope of the vertical detail, /8
    return (mir(HLr, -1, 0) - mir(HLr, 1, 0) + mir(LHm, -1, 1) - mir(LHm, 1, 1) + 3 + pv) >> 3

def bands(Lv=2, Lh=5):
    b = ['LL'] + ['H%d' % l for l in range(Lh, Lv, -1)]
    for l in range(Lv, 0, -1): b += ['HL%d' % l, 'LH%d' % l, 'HH%d' % l]
    return b

# ---------------- synthesis with legality (decoder) ----------------
FIX = None          # SA19 encoder-only hook: dict band -> (base_leaf, step, target_leaf, ro); stats in FIXSTAT
FIXSTAT = {}
def _fix(b, v, p, inS):
    """encoder-side: if v (value domain) is outside its feasible set, move its INDEX to the lattice point inside the set
    nearest to the source target. inS(values) -> bool mask. Returns new v (still unclamped; the clamp then is a no-op
    wherever a lattice point existed)."""
    if FIX is None or b not in FIX: return v
    base, st, tgt, ro = FIX[b]
    bad = ~inS(v)
    FIXSTAT[b] = FIXSTAT.get(b, np.zeros(2, np.int64)) + [int(bad.sum()), 0]
    if not bad.any(): return v
    q0 = np.round((v - p - base) / st).astype(np.int64)
    best = v.copy(); bd = np.full(v.shape, np.inf); ok = np.zeros(v.shape, bool)
    for k in range(-8, 9):
        q = q0 + k; val = base + recon(q, st, ro) + p
        good = bad & inS(val); dist = np.abs(val - p - tgt).astype(float)
        take = good & (dist < bd); best = np.where(take, val, best); bd = np.where(take, dist, bd); ok |= good
    FIXSTAT[b][1] += int(ok.sum())
    return np.where(ok, best, v)

def synthesis(V, lo, hi, Lv=2, Lh=5, legal=True, want_iv=False):
    """V: band -> leaf VALUES before clamping (base + q*step). Returns (plane, F, IV):
    F: band -> final (clamped) leaf values; IV: band -> feasible set used (for the canonical reading)."""
    F = {}; IV = {}
    ll = V['LL']
    if legal: ll = np.clip(ll, lo, hi)
    F['LL'] = ll; IV['LL'] = ('iv', np.full(ll.shape, lo), np.full(ll.shape, hi))
    for l in range(Lh, Lv, -1):
        h, w = ll.shape; pv = par(h, w, l)
        p = slope(ll, 1, pv); v = V['H%d' % l] + p
        if legal:
            S = dset(ll, pv, lo, hi, lo, hi); v = _fix('H%d' % l, v, p, lambda z: dclamp(z, S) == z); v = dclamp(v, S); IV['H%d' % l] = ('set', p, S)
        F['H%d' % l] = v - p
        a, b = ps(ll, v, pv); ll = np.empty((h, 2 * w), np.int64); ll[:, 0::2] = a; ll[:, 1::2] = b
    for l in range(Lv, 0, -1):
        h, w = ll.shape; pv = par(h, w)
        # HL -> VM
        p = slope(ll, 1, pv); v = V['HL%d' % l] + p
        if legal:
            S = dset(ll, pv, lo, hi, lo, hi); v = _fix('HL%d' % l, v, p, lambda z: dclamp(z, S) == z); v = dclamp(v, S); IV['HL%d' % l] = ('set', p, S)
        HLr = v; F['HL%d' % l] = v - p
        a, b = ps(ll, HLr, pv); VM = np.empty((h, 2 * w), np.int64); VM[:, 0::2] = a; VM[:, 1::2] = b
        # targets for VD given VM (vertical pixel pair)
        pvv = par(h, 2 * w)
        SV = dset(VM, pvv, lo, hi, lo, hi); Jlo, Jhi = inner(SV)
        # LH (mean of the VD pair)
        p = slope(ll, 0, pv); v = V['LH%d' % l] + p
        if legal:
            mlo, mhi = mset(pv, Jlo[:, 0::2], Jhi[:, 0::2], Jlo[:, 1::2], Jhi[:, 1::2])
            v = _fix('LH%d' % l, v, p, lambda z: (z >= mlo) & (z <= mhi)); v = np.clip(v, mlo, mhi); IV['LH%d' % l] = ('iv', mlo - p, mhi - p)
        LHm = v; F['LH%d' % l] = v - p
        # HH
        p = hhpred(HLr, LHm, pv); v = V['HH%d' % l] + p
        if legal:
            S = dset(LHm, pv, Jlo[:, 0::2], Jhi[:, 0::2], Jlo[:, 1::2], Jhi[:, 1::2]); v = _fix('HH%d' % l, v, p, lambda z: dclamp(z, S) == z); v = dclamp(v, S)
            IV['HH%d' % l] = ('set', p, S)
        F['HH%d' % l] = v - p
        a, b = ps(LHm, v, pv); VD = np.empty((h, 2 * w), np.int64); VD[:, 0::2] = a; VD[:, 1::2] = b
        x0, x1 = ps(VM, VD, pvv); ll = np.empty((2 * h, 2 * w), np.int64); ll[0::2] = x0; ll[1::2] = x1
    return ll, F, IV

def clampf(IVb, v):
    """apply the feasible set of a band (leaf space) to leaf values v"""
    if IVb[0] == 'iv': return np.clip(v, IVb[1], IVb[2])
    p, S = IVb[1], IVb[2]
    return dclamp(v + p, S) - p

def recon(q, step, ro=0):
    """SA18 texture reconstruction offset: a nonzero index reconstructs at (|q| + 2^-ro) * step (outward), ro=0: off"""
    return q * step + (np.sign(q) * (step >> ro) if ro else 0)

def canon_index(w, base, step, IVb, ro=0):
    """smallest |q| with clampf(base+recon(q)) == w. Returns (q, ok)."""
    r = w - base; f = np.floor_divide(r, step)
    best = np.zeros_like(w); found = np.zeros(w.shape, bool)
    for q in [np.zeros_like(f), f - 2, f - 1, f, f + 1, f + 2]:
        good = (clampf(IVb, base + recon(q, step, ro)) == w)
        take = good & (~found | (np.abs(q) < np.abs(best)))
        best = np.where(take, q, best); found |= good
    return best, found
