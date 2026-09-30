# SA17 transforms: integer lifting along axis 0 of a 2-D array (columns independent).
# 'f' = float mode (for gain computation), else integer with position-alternating rounding.
import numpy as np

def _fl(a, sh, f):
    return a / (1 << sh) if f else (a >> sh)

def _par(n, w, off=0):
    # position parity pi = (row + col + off) & 1, shape (n, w)
    return ((np.arange(n)[:, None] + np.arange(w)[None, :] + off) & 1).astype(np.int64)

# ---------------- CDF 5/3 ----------------
def a53(X, f=False, alt=True):
    e = X[0::2]; o = X[1::2]
    n, w = o.shape
    en = np.concatenate([e[1:], e[-1:]], 0) if e.shape[0] == o.shape[0] else e[1:]
    pi = _par(n, w) if (alt and not f) else (0 if not f else 0)
    if f: d = o - (e[:n] + en) / 2
    else: d = o - ((e[:n] + en + pi) >> 1)
    dp = np.concatenate([d[:1], d[:-1]], 0)
    if e.shape[0] > n: dp = np.concatenate([dp, d[-1:]], 0); dn = np.concatenate([d, d[-1:]], 0)
    else: dn = d
    r2 = (1 + _par(e.shape[0], w, 1)) if (alt and not f) else 2
    if f: s = e + (dp + dn) / 4
    else: s = e + ((dp + dn + r2) >> 2)
    return s, d

def s53(s, d, f=False, alt=True):
    n, w = d.shape
    dp = np.concatenate([d[:1], d[:-1]], 0)
    dn = d
    if s.shape[0] > n: dp = np.concatenate([dp, d[-1:]], 0); dn = np.concatenate([d, d[-1:]], 0)
    r2 = (1 + _par(s.shape[0], w, 1)) if (alt and not f) else 2
    e = s - ((dp + dn) / 4 if f else ((dp + dn + r2) >> 2))
    en = np.concatenate([e[1:], e[-1:]], 0) if e.shape[0] == n else e[1:]
    pi = _par(n, w) if (alt and not f) else 0
    o = d + ((e[:n] + en) / 2 if f else ((e[:n] + en + pi) >> 1))
    X = np.empty((s.shape[0] + n, w), dtype=d.dtype if not f else float)
    X[0::2] = e; X[1::2] = o
    return X

# ------------- pair (S-transform mean + difference predicted from neighbour means, "2/6") -------------
def a26(X, f=False, alt=True):
    x0 = X[0::2]; x1 = X[1::2]; n, w = x0.shape
    pi = _par(n, w) if (alt and not f) else 0
    if f: m = (x0 + x1) / 2
    else: m = (x0 + x1 + pi) >> 1
    draw = x0 - x1
    mp = np.concatenate([m[1:2], m[:-1]], 0) if n > 1 else m   # mirror m[-1]=m[1]
    mn = np.concatenate([m[1:], m[-2:-1]], 0) if n > 1 else m  # mirror m[n]=m[n-2]
    if f: p = (mp - mn) / 4
    else: p = (mp - mn + 1 + _par(n, w, 1)) >> 2 if alt else (mp - mn + 2) >> 2
    return m, draw - p

def s26(m, d, f=False, alt=True):
    n, w = m.shape
    mp = np.concatenate([m[1:2], m[:-1]], 0) if n > 1 else m
    mn = np.concatenate([m[1:], m[-2:-1]], 0) if n > 1 else m
    if f: p = (mp - mn) / 4
    else: p = (mp - mn + 1 + _par(n, w, 1)) >> 2 if alt else (mp - mn + 2) >> 2
    draw = d + p
    X = np.empty((2 * n, w), dtype=float if f else np.int64)
    if f:
        X[0::2] = m + draw / 2; X[1::2] = m - draw / 2
    else:
        pi = _par(n, w) if alt else 0
        ssum = 2 * m - pi + ((draw + pi) & 1)
        X[0::2] = (ssum + draw) >> 1; X[1::2] = (ssum - draw) >> 1
    return X

FILT = {'53': (a53, s53), '26': (a26, s26)}
def hfilt(hf, l):
    # '97m2' -> 97m at levels 1..2, 53 elsewhere
    if hf.startswith('97m') and len(hf) > 3:
        return FILT['97m'] if l <= int(hf[3:]) else FILT['53']
    return FILT[hf]

def analysis(x, Lv=2, Lh=5, vf='53', hf='53', f=False):
    """Mallat 2-D: Lv levels of (V then H), then Lh-Lv H-only levels on LL. returns dict band->array"""
    T = {}; ll = x.astype(float) if f else x.astype(np.int64)
    for l in range(1, Lv + 1):
        ah = hfilt(hf, l)[0]; av = hfilt(vf, l)[0]
        L, Hh = av(ll, f)                     # vertical: L rows, H rows
        LL, HL = ah(L.T, f); LH, HH = ah(Hh.T, f)
        T['HL%d' % l] = HL.T; T['LH%d' % l] = LH.T; T['HH%d' % l] = HH.T
        ll = LL.T
    for l in range(Lv + 1, Lh + 1):
        LL, Hc = hfilt(hf, l)[0](ll.T, f); T['H%d' % l] = Hc.T; ll = LL.T
    T['LL'] = ll
    return T

def synthesis(T, Lv=2, Lh=5, vf='53', hf='53', f=False):
    ll = T['LL']
    for l in range(Lh, Lv, -1):
        ll = hfilt(hf, l)[1](ll.T, T['H%d' % l].T, f).T
    for l in range(Lv, 0, -1):
        sh = hfilt(hf, l)[1]; sv = hfilt(vf, l)[1]
        L = sh(ll.T, T['HL%d' % l].T, f).T
        Hh = sh(T['LH%d' % l].T, T['HH%d' % l].T, f).T
        ll = sv(L, Hh, f)
    return ll

def bands(Lv=2, Lh=5):
    b = ['LL'] + ['H%d' % l for l in range(Lh, Lv, -1)]
    for l in range(Lv, 0, -1): b += ['HL%d' % l, 'LH%d' % l, 'HH%d' % l]
    return b

_GAIN = {}
def gains(shape, Lv=2, Lh=5, vf='53', hf='53'):
    key = (shape, Lv, Lh, vf, hf)
    if key in _GAIN: return _GAIN[key]
    H, W = shape
    T0 = analysis(np.zeros(shape), Lv, Lh, vf, hf, f=True)
    G = {}
    for b in T0:
        T = {k: np.zeros_like(v) for k, v in T0.items()}
        h, w = T[b].shape; T[b][h // 2, w // 2] = 1.0
        y = synthesis(T, Lv, Lh, vf, hf, f=True)
        G[b] = float((y ** 2).sum())
    _GAIN[key] = G
    return G

# ---- pair variants: 2/6 + symmetric update from neighbour differences; 2/10 prediction ----
def _mir(m, k):
    # m[n+k] with whole-sample mirror at both ends
    n = m.shape[0]; idx = np.arange(n) + k
    idx = np.where(idx < 0, -idx, idx); idx = np.where(idx > n - 1, 2 * (n - 1) - idx, idx)
    return m[idx]

def _pred(m, kind, f, alt):
    n, w = m.shape
    if kind == '26':
        num = _mir(m, -1) - _mir(m, 1); sh = 2
    else:  # 2/10: (22(m-1 - m+1) + 3(m+2 - m-2))/64
        num = 22 * (_mir(m, -1) - _mir(m, 1)) + 3 * (_mir(m, 2) - _mir(m, -2)); sh = 6
    if f: return num / (1 << sh)
    r = ((1 << (sh - 1)) - 1 + _par(n, w, 1)) if alt else (1 << (sh - 1))
    return (num + r) >> sh

def make_pair(kind='26', uc=0):
    """uc: update weight as shift (0 = none, 3 -> 1/8, 4 -> 1/16) on (d[n-1]-d[n+1])"""
    def upd(d, f, alt):
        if uc == 0: return 0
        num = _mir(d, -1) - _mir(d, 1)
        if f: return num / (1 << uc)
        n, w = d.shape
        r = ((1 << (uc - 1)) - 1 + _par(n, w, 0)) if alt else (1 << (uc - 1))
        return (num + r) >> uc
    def a(X, f=False, alt=True):
        x0 = X[0::2]; x1 = X[1::2]; n, w = x0.shape
        pi = _par(n, w) if (alt and not f) else 0
        m = (x0 + x1) / 2 if f else (x0 + x1 + pi) >> 1
        d = (x0 - x1) - _pred(m, kind, f, alt)
        return m + upd(d, f, alt), d
    def s(mu, d, f=False, alt=True):
        m = mu - upd(d, f, alt); n, w = m.shape
        draw = d + _pred(m, kind, f, alt)
        X = np.empty((2 * n, w), dtype=float if f else np.int64)
        if f: X[0::2] = m + draw / 2; X[1::2] = m - draw / 2
        else:
            pi = _par(n, w) if alt else 0
            ssum = 2 * m - pi + ((draw + pi) & 1)
            X[0::2] = (ssum + draw) >> 1; X[1::2] = (ssum - draw) >> 1
        return X
    return a, s

for _k in ('26', '210'):
    for _u in (0, 3, 4, 5):
        FILT['%s' % _k + ('u%d' % _u if _u else '')] = make_pair(_k, _u)

# ---- (9,7)-M = (4,2) interpolating lifting: predict (-1,9,9,-1)/16, update (1,1)/4 ----
def a97m(X, f=False, alt=True):
    e = X[0::2]; o = X[1::2]; n, w = o.shape
    em = _mir(e, 0); e1 = _mir(np.concatenate([e, e[-1:]], 0), 0)
    E = lambda k: _mir(e, k)
    num = 9 * (E(0)[:n] + E(1)[:n]) - (E(-1)[:n] + E(2)[:n])
    if f: d = o - num / 16
    else: d = o - ((num + 7 + _par(n, w) * 1 + (1 if not alt else 0)) >> 4) if alt else o - ((num + 8) >> 4)
    dp = np.concatenate([d[:1], d[:-1]], 0)
    r2 = (1 + _par(e.shape[0], w, 1)) if (alt and not f) else 2
    s = e + ((dp + d) / 4 if f else ((dp + d + r2) >> 2))
    return s, d

def s97m(s, d, f=False, alt=True):
    n, w = d.shape
    dp = np.concatenate([d[:1], d[:-1]], 0)
    r2 = (1 + _par(s.shape[0], w, 1)) if (alt and not f) else 2
    e = s - ((dp + d) / 4 if f else ((dp + d + r2) >> 2))
    E = lambda k: _mir(e, k)
    num = 9 * (E(0)[:n] + E(1)[:n]) - (E(-1)[:n] + E(2)[:n])
    if f: o = d + num / 16
    else: o = d + (((num + 7 + _par(n, w)) >> 4) if alt else ((num + 8) >> 4))
    X = np.empty((2 * n, w), dtype=float if f else np.int64); X[0::2] = e; X[1::2] = o
    return X
FILT['97m'] = (a97m, s97m)

def make_hmix(k1='97m', k2='53', nlev=2):
    """horizontal filter by level: levels 1..nlev use k1, others k2 (level passed via closure counter)"""
    return None

# ---- predict-only 5/3 ("lazy + bilinear predict", no update) ----
def a53p(X, f=False, alt=True):
    e = X[0::2]; o = X[1::2]; n, w = o.shape
    en = np.concatenate([e[1:], e[-1:]], 0) if e.shape[0] == o.shape[0] else e[1:]
    pi = _par(n, w) if (alt and not f) else 0
    d = o - ((e[:n] + en) / 2 if f else ((e[:n] + en + pi) >> 1))
    return e.copy(), d
def s53p(s, d, f=False, alt=True):
    n, w = d.shape; e = s
    en = np.concatenate([e[1:], e[-1:]], 0) if e.shape[0] == n else e[1:]
    pi = _par(n, w) if (alt and not f) else 0
    o = d + ((e[:n] + en) / 2 if f else ((e[:n] + en + pi) >> 1))
    X = np.empty((s.shape[0] + n, w), dtype=float if f else np.int64); X[0::2] = e; X[1::2] = o
    return X
FILT['53p'] = (a53p, s53p)
_hf_orig = hfilt
def hfilt(hf, l):
    # 'p53_k' -> predict-only 5/3 at levels <= k, 5/3 elsewhere
    if hf.startswith('p53_'):
        return FILT['53p'] if l <= int(hf[4:]) else FILT['53']
    return _hf_orig(hf, l)

# pair with NEGATIVE-sign update, and one-sided (causal) update variants
def make_pair2(kind='26', uc=4, sign=-1, causal=False):
    def upd(d, f, alt):
        num = (_mir(d, -1) - (0 if causal else _mir(d, 1))) * sign
        if causal: num = num * 1
        if f: return num / (1 << uc)
        n, w = d.shape
        r = ((1 << (uc - 1)) - 1 + _par(n, w, 0)) if alt else (1 << (uc - 1))
        return (num + r) >> uc
    def a(X, f=False, alt=True):
        x0 = X[0::2]; x1 = X[1::2]; n, w = x0.shape
        pi = _par(n, w) if (alt and not f) else 0
        m = (x0 + x1) / 2 if f else (x0 + x1 + pi) >> 1
        d = (x0 - x1) - _pred(m, kind, f, alt)
        return m + upd(d, f, alt), d
    def s(mu, d, f=False, alt=True):
        m = mu - upd(d, f, alt); n, w = m.shape
        draw = d + _pred(m, kind, f, alt)
        X = np.empty((2 * n, w), dtype=float if f else np.int64)
        if f: X[0::2] = m + draw / 2; X[1::2] = m - draw / 2
        else:
            pi = _par(n, w) if alt else 0
            ssum = 2 * m - pi + ((draw + pi) & 1)
            X[0::2] = (ssum + draw) >> 1; X[1::2] = (ssum - draw) >> 1
        return X
    return a, s
for _u in (3, 4, 5):
    FILT['26n%d' % _u] = make_pair2('26', _u, -1, False)
    FILT['26c%d' % _u] = make_pair2('26', _u, 1, True)
    FILT['26cn%d' % _u] = make_pair2('26', _u, -1, True)
