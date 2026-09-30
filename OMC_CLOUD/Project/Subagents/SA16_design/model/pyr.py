# CQP-1 transform: pair mean/difference pyramid, 2 vertical x Lh horizontal levels, 4-row blocks,
# ALL difference predictors causal (left mean / above mean), position-alternating rounding,
# legality by interval clamp of every leaf from already-final values.  SA16, 2026-09-28.
import numpy as np

# ---------------------------------------------------------------- 1-D pair primitives
def phase(rows, pairs, axis, off=0):
    """rounding phase s in {0,1}, alternating along both ABSOLUTE coordinates (off = absolute index of row 0)."""
    i = np.arange(rows)[:, None] + off; j = np.arange(pairs)[None, :]
    return ((i + j) & 1).astype(np.int64)

def split_h(x, off=0):
    """x (R, 2K) -> m (R,K), d (R,K).  d = e - o ; m = e - ((d+s)>>1).  off = absolute row index of x[0]."""
    e = x[:, 0::2]; o = x[:, 1::2]; d = e - o; s = phase(x.shape[0], d.shape[1], 1, off)
    return e - ((d + s) >> 1), d

def merge_h(m, d, off=0):
    s = phase(m.shape[0], m.shape[1], 1, off)
    e = m + ((d + s) >> 1); o = e - d
    x = np.empty((m.shape[0], 2 * m.shape[1]), np.int64); x[:, 0::2] = e; x[:, 1::2] = o
    return x

def split_v(x, off=0):
    """x (2K, C) -> m (K,C), d (K,C); pairs of consecutive rows.  off = absolute PAIR index of the first pair."""
    e = x[0::2]; o = x[1::2]; d = e - o; s = phase(d.shape[0], d.shape[1], 0, off)
    return e - ((d + s) >> 1), d

def merge_v(m, d, off=0):
    s = phase(m.shape[0], m.shape[1], 0, off)
    e = m + ((d + s) >> 1); o = e - d
    x = np.empty((2 * m.shape[0], m.shape[1]), np.int64); x[0::2] = e; x[1::2] = o
    return x

def dbox(A0, A1, B0, B1, m, s):
    """legal interval of d given the pair mean m, phase s, and per-sample ranges e in [A0,A1], o in [B0,B1]."""
    lo = np.maximum(2 * (A0 - m) - s, 2 * (m - B1) + s - 1)
    hi = np.minimum(2 * (A1 - m) + 1 - s, 2 * (m - B0) + s)
    return lo, hi

def mbox(A0, A1, B0, B1, s):
    """legal interval of the pair mean m given per-sample ranges."""
    return (A0 + B0 - s + 1) >> 1, (A1 + B1 - s + 1) >> 1

# causal predictors of a difference from means: horizontal (left mean, own mean), vertical (above, own)
def pred_h(m):
    p = np.zeros_like(m); p[:, 1:] = (m[:, :-1] - m[:, 1:] + 1) >> 1; return p

def pred_v_pairs(m):
    """m: rows of pair means (2 per 4-row block); the same prediction for both pairs of a block:
    (m[2b]-m[2b+1]+1)>>1."""
    p = (m[0::2] - m[1::2] + 1) >> 1
    return np.repeat(p, 2, axis=0)

def pred_v_blocks(m, m_above):
    """m: one row per block; prediction (m[b-1]-m[b]+1)>>1; m_above = the block above the first (or None)."""
    p = np.zeros_like(m)
    p[1:] = (m[:-1] - m[1:] + 1) >> 1
    if m_above is not None: p[0] = (m_above - m[0] + 1) >> 1
    return p

BANDS = lambda Lh: ['LL'] + ['H%d' % k for k in range(Lh, 2, -1)] + ['LH2', 'HL2', 'HH2', 'LH1', 'HL1', 'HH1']

# ---------------------------------------------------------------- analysis (open loop)
def analysis(x, Lh, above=None):
    """x (H, W) int64, H % 4 == 0, W % 2^Lh == 0.  Returns dict band -> coefficient array (open loop:
    every predictor reads the picture's own means).  above = (LL2 row, HL2 row) of the block above x
    (used by the first block's vertical level-2 predictors), or None (frame top)."""
    T = {}
    L1, d = split_h(x); E1 = d - pred_h(L1)
    LL1, dv = split_v(L1); T['LH1'] = dv - pred_v_pairs(LL1)
    HL1, dv = split_v(E1); T['HL1'] = HL1; T['HH1'] = dv - pred_v_pairs(HL1)
    L2, d = split_h(LL1); E2 = d - pred_h(L2)
    LL2, dv = split_v(L2); T['LH2'] = dv - pred_v_blocks(LL2, None if above is None else above[0])
    HL2, dv = split_v(E2); T['HL2'] = HL2; T['HH2'] = dv - pred_v_blocks(HL2, None if above is None else above[1])
    ll = LL2
    for k in range(3, Lh + 1):
        ll, d = split_h(ll); T['H%d' % k] = d - pred_h(ll)
    T['LL'] = ll
    T['_above'] = (LL2[-1].copy(), HL2[-1].copy())
    return T

# ---------------------------------------------------------------- synthesis with clamps
def synthesis(C, Lh, lo, hi, above=None, want_iv=False):
    """C: dict band -> coefficient values BEFORE clamping (e.g. c_p + step*q).  Applies the legality clamp of
    every leaf from final values, returns (x, Cfinal, IV) where Cfinal are the values actually used and
    IV[band] = (ilo, ihi) the interval each value was clamped into."""
    F = {}; IV = {}
    def leaf(name, v, ilo, ihi):
        w = np.clip(v, ilo, ihi); F[name] = w; IV[name] = (ilo, ihi); return w
    full = lambda a: (np.full(a.shape, lo, np.int64), np.full(a.shape, hi, np.int64))
    ll = leaf('LL', C['LL'], *full(C['LL']))
    for k in range(Lh, 2, -1):
        p = pred_h(ll); A0, A1 = full(ll); s = phase(ll.shape[0], ll.shape[1], 1)
        dlo, dhi = dbox(A0, A1, A0, A1, ll, s)
        e = leaf('H%d' % k, C['H%d' % k], dlo - p, dhi - p)
        ll = merge_h(ll, e + p)
    LL2 = ll
    # level 2 vertical: L2 rows from LL2 + LH2
    p = pred_v_blocks(LL2, None if above is None else above[0]); A0, A1 = full(LL2); s = phase(LL2.shape[0], LL2.shape[1], 0)
    dlo, dhi = dbox(A0, A1, A0, A1, LL2, s)
    e = leaf('LH2', C['LH2'], dlo - p, dhi - p)
    L2 = merge_v(LL2, e + p)
    # E2 intervals from L2 rows
    ph = pred_h(L2); A0, A1 = full(L2); sh = phase(L2.shape[0], L2.shape[1], 1)
    elo, ehi = dbox(A0, A1, A0, A1, L2, sh); elo = elo - ph; ehi = ehi - ph
    sv = phase(L2.shape[0] // 2, L2.shape[1], 0)
    mlo, mhi = mbox(elo[0::2], ehi[0::2], elo[1::2], ehi[1::2], sv)
    HL2 = leaf('HL2', C['HL2'], mlo, mhi)
    p = pred_v_blocks(HL2, None if above is None else above[1])
    dlo, dhi = dbox(elo[0::2], ehi[0::2], elo[1::2], ehi[1::2], HL2, sv)
    e = leaf('HH2', C['HH2'], dlo - p, dhi - p)
    E2 = merge_v(HL2, e + p)
    LL1 = merge_h(L2, E2 + ph)
    # level 1 vertical: L1 rows
    p = pred_v_pairs(LL1); A0, A1 = full(LL1); s = phase(LL1.shape[0], LL1.shape[1], 0)
    dlo, dhi = dbox(A0, A1, A0, A1, LL1, s)
    e = leaf('LH1', C['LH1'], dlo - p, dhi - p)
    L1 = merge_v(LL1, e + p)
    ph = pred_h(L1); A0, A1 = full(L1); sh = phase(L1.shape[0], L1.shape[1], 1)
    elo, ehi = dbox(A0, A1, A0, A1, L1, sh); elo = elo - ph; ehi = ehi - ph
    sv = phase(L1.shape[0] // 2, L1.shape[1], 0)
    mlo, mhi = mbox(elo[0::2], ehi[0::2], elo[1::2], ehi[1::2], sv)
    HL1 = leaf('HL1', C['HL1'], mlo, mhi)
    p = pred_v_pairs(HL1)
    dlo, dhi = dbox(elo[0::2], ehi[0::2], elo[1::2], ehi[1::2], HL1, sv)
    e = leaf('HH1', C['HH1'], dlo - p, dhi - p)
    E1 = merge_v(HL1, e + p)
    x = merge_h(L1, E1 + ph)
    F['_above'] = (LL2[-1].copy(), HL2[-1].copy())
    return x, F, IV

# ---------------------------------------------------------------- self test
if __name__ == '__main__':
    import sys
    rng = np.random.default_rng(1)
    # 1. interval formulas by brute force
    lo, hi = 0, 15
    for s in (0, 1):
        for m in range(lo, hi + 1):
            ok = [d for d in range(-64, 65) if lo <= m + ((d + s) >> 1) <= hi and lo <= m + ((d + s) >> 1) - d <= hi]
            dlo, dhi = dbox(np.array(lo), np.array(hi), np.array(lo), np.array(hi), np.array(m), np.array(s))
            assert ok and ok[0] == dlo and ok[-1] == dhi and len(ok) == dhi - dlo + 1, (s, m, ok, dlo, dhi)
    # general A/B ranges
    for _ in range(2000):
        A0, B0 = rng.integers(-20, 20, 2); A1 = A0 + rng.integers(0, 30); B1 = B0 + rng.integers(0, 30); s = int(rng.integers(0, 2))
        ml, mh = mbox(*[np.array(v) for v in (A0, A1, B0, B1)], np.array(s))
        ms = sorted(set(e - ((e - o + s) >> 1) for e in range(A0, A1 + 1) for o in range(B0, B1 + 1)))
        assert ms[0] == ml and ms[-1] == mh and len(ms) == mh - ml + 1, (A0, A1, B0, B1, s, ms, ml, mh)
        for m in range(ml, mh + 1):
            ok = [d for d in range(-200, 201) if A0 <= m + ((d + s) >> 1) <= A1 and B0 <= m + ((d + s) >> 1) - d <= B1]
            dlo, dhi = dbox(*[np.array(v) for v in (A0, A1, B0, B1, m, s)])
            assert ok and ok[0] == dlo and ok[-1] == dhi and len(ok) == dhi - dlo + 1
    print('intervals: OK')
    # 2. bijection + legality on a real frame
    sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
    import yuv
    Y, Cb, Cr = yuv.read_frame('/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1280x720_422_10.yuv', 1280, 720, 3)
    for pl, Lh in ((Y, 5), (Cb, 4), (Cr, 4)):
        T = analysis(pl, Lh)
        x, F, IV = synthesis(T, Lh, 0, 1023)
        assert np.array_equal(x, pl), 'bijection FAILED'
        for b in BANDS(Lh):
            assert np.all(F[b] == T[b]), 'legal picture coefficient clamped in ' + b
        # random coefficients -> legal picture
        R = {b: rng.integers(-3000, 3000, T[b].shape) for b in BANDS(Lh)}
        x2, F2, _ = synthesis(R, Lh, 0, 1023)
        assert x2.min() >= 0 and x2.max() <= 1023, 'illegal output'
        # re-analysis of the legal decode gives back the clamped values exactly
        T2 = analysis(x2, Lh)
        for b in BANDS(Lh): assert np.array_equal(T2[b], F2[b]), 'reading FAILED in ' + b
    print('bijection, legality, reading: OK')
