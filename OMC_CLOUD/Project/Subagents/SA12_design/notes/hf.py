#!/usr/bin/env python3
"""SA12 experiment 'HF': Haar-family pyramid = integer S-transform pairs (lowpass = floor average of the pair,
detail = difference) with every detail PREDICTED from the already-final lowpass (2/6 or 2/10 symmetric horizontally;
causal c2/c3 or symmetric vertically).  Coded CLOSED LOOP coarse-to-fine; every transmitted value is clamped into the
interval that keeps its two output samples inside their legal boxes (acyclic: the interval depends only on final
values), and the index is the canonical K(r) of the clamped value, so re-encoding the decoded picture returns the
same indices.  Per level (2-D levels): H split -> Lc, dH ; V split Lc -> LL, LH ; residual e = dH - P_H(Lc_rec) ;
V split e -> HL, HH.  H-only levels above nv.  Integer throughout.
Rate estimator, step rule and PSNR as SA11 struct_s.py (zeroth-order entropy per band per frame; D = 2^round(Qf -
0.5 log2 w_b); LL step x 2^k with the best k per arm).
usage: hf.py path W H frame sh fmt depth lo hi tag variants_json"""
import numpy as np, sys, math, json
fd = np.floor_divide
import os as _os
EDGE_TH = int(_os.environ.get('HF_EDGE', '0'))   # sixteenths; 0 = off (7/16 everywhere)

def ext(s, above, k=2, below=None):
    n = s.shape[-1]
    if n >= 2:
        L = [s[..., :1] - (j + 1) * (s[..., 1:2] - s[..., :1]) for j in range(k)][::-1]
        R = [s[..., -1:] + (j + 1) * (s[..., -1:] - s[..., -2:-1]) for j in range(k)]
    else:
        L = [s[..., :1]] * k; R = [s[..., -1:]] * k
    if above is not None: L = [above[..., j:j + 1] for j in range(k)]
    if below is not None: R = [below[..., j:j + 1] for j in range(k)]
    return np.concatenate(L + [s] + R, -1)

def pred(s, kind, above=None, below=None):
    n = s.shape[-1]; k = 2; e = ext(s, above, k, below); c = lambda o: e[..., k + o:k + o + n]
    if kind == 'z':   return np.zeros_like(s)
    if kind in ('s6', 's6a'):  return fd(c(-1) - c(1) + 8, 16) if SUM else fd(c(-1) - c(1) + 2, 4)
    if kind in ('s10', 's10a'): return fd(22 * (c(-1) - c(1)) + 3 * (c(2) - c(-2)) + 128, 256) if SUM else fd(22 * (c(-1) - c(1)) + 3 * (c(2) - c(-2)) + 32, 64)
    if kind == 'c2':  return fd(c(-1) - c(0) + 1, 2)
    if kind == 'c3':  return fd(-3 * c(0) + 4 * c(-1) - c(-2) + 2, 4)
    raise ValueError(kind)

def dint(s, la, ua, lb, ub, r=0):
    if SUM:
        sg = r if isinstance(r, np.ndarray) or r in (1, -1) else 1
        m = (s + sg * (s & 1)) >> 1; f = s - m
        lo = np.maximum(la - m, f - ub); hi = np.minimum(ua - m, f - lb)
    else:
        lo = np.maximum(2 * (la - s) - 1 + r, 2 * (s - ub) - r); hi = np.minimum(2 * (ua - s) + r, 2 * (s - lb) + 1 - r)
    if not (lo <= hi).all(): raise AssertionError('empty interval %d' % int((lo > hi).sum()))
    return lo, hi

def Kidx(r, lo, hi, D):
    q = np.sign(r) * fd(np.abs(r) * 16 + 7 * D, 16 * D)
    q = np.where(r >= hi, -fd(-hi, D), q)
    q = np.where((r <= lo) & (r < hi), fd(lo, D), q)
    return q

class Coder:
    """mode 'enc': quantise targets, store indices; 'dec': read indices."""
    def __init__(self, mode, steps, Qin=None, th=7):
        self.mode, self.steps, self.Q, self.Qin, self.nclamp, self.th, self.deg = mode, steps, {}, Qin, 0, th, {}
    def qc(self, key, target, lo, hi):
        D = self.steps[key]
        if self.mode == 'enc':
            th = np.full(target.shape, THMAP.get(key[0], self.th) if self.th == 7 else self.th, np.int64)
            if EDGE_TH and key[0] == 1 and key[1] in ('LH', 'HH'): th[:, -1, :] = EDGE_TH
            if LL_HALF and key[1] == 'LL' and self.th == 7: th[...] = 8
            q0 = np.sign(target) * fd(np.abs(target) * 16 + th * D, 16 * D)
            r = np.where(target >= hi, hi, np.where(target <= lo, lo, np.clip(q0 * D, lo, hi)))
            q = Kidx(r, lo, hi, D)
            self.nclamp += int((q0 != q).sum())
        else:
            q = self.Qin[key]
        self.Q[key] = q
        self.deg[key] = (lo == hi)       # single-value interval: derived, not transmitted (decoder knows it)
        return np.clip(q * D, lo, hi)

RND = int(_os.environ.get('HF_RND', '3'))
THMAP = {}   # level -> rounding offset (sixteenths); encoder-only, set by experiments
SUM = (RND == 3)
LL_HALF = int(_os.environ.get('HF_LLHALF', '1'))     # 1 = checkerboard rounding parity r (unbiased pair average); 0 = floor
STAGE_R = {}      # RND=2: constant r per (level, axis): set by rec_level via _cur
_cur = [0, 'H']
def _stage_r():
    lev, ax = _cur
    return (lev + (1 if ax == 'V' else 0)) & 1       # alternate H/V within a level and between levels
def rpat(shape):   # r = (i + j) & 1 over the last two axes (pair index, cross index), zero if RND off
    if not RND: return 0
    if RND == 2: return _stage_r()
    i = np.arange(shape[-2])[:, None]; j = np.arange(shape[-1])[None, :]
    return ((i + j) & 1).astype(np.int64)
def rh(shape): return rpat(shape)                                   # horizontal: last axis = pair index
def rv(shape):                                                      # vertical: axis 1 = pair index
    if not RND: return 0
    if RND == 2: return _stage_r()
    i = np.arange(shape[1])[:, None]; j = np.arange(shape[2])[None, :]; return ((i + j) & 1).astype(np.int64)
SIGNED = int(_os.environ.get('HF_SIGN', '1'))   # SUM mode: which sample of an odd-sum pair gets the extra unit
_slice0 = [0]      # absolute slice index of axis-0 element 0 (set by the sequential slice loops)
def _sig(shape):
    """deterministic aperiodic +-1 per pair (model: integer hash; hardware: an LFSR sequence seeded per row).
    Depends on (stage, absolute slice index, pair index, cross index)."""
    if not SIGNED: return 1
    lev, ax = _cur; st = 2 * lev + (1 if ax == 'V' else 0)
    n = (np.arange(shape[0], dtype=np.int64) + _slice0[0])[:, None, None]
    i = np.arange(shape[-2], dtype=np.int64)[None, :, None]; j = np.arange(shape[-1], dtype=np.int64)[None, None, :]
    h = ((i * 73856093) ^ (j * 19349663) ^ (st * 83492791) ^ (n * 2654435761)) & 0xFFFFFFFF
    h ^= h >> 13; h = (h * 1274126177) & 0xFFFFFFFF; h ^= h >> 16
    return (1 - 2 * (h & 1)).astype(np.int64)
def _sp(a, b, r, sg=1):
    if SUM:
        s = a + b; d = a - b                 # d == s (mod 2); d = 2 d' + sg*(s&1)
        return s, (d - sg * (s & 1)) // 2
    return fd(a + b + r, 2), a - b
def _mg(s, d, r, sg=1):
    if SUM:
        dd = 2 * d + sg * (s & 1); a = (s + dd) >> 1; return a, a - dd
    a = s + fd(d + 1 - r, 2); return a, a - d
def hsplit(A): a, b = A[..., 0::2], A[..., 1::2]; return _sp(a, b, 0 if SUM else rh(a.shape), _sig(a.shape) if SUM else 1)
def vsplit(A): a, b = A[:, 0::2, :], A[:, 1::2, :]; return _sp(a, b, 0 if SUM else rv(a.shape), _sig(a.shape) if SUM else 1)
def hmerge(s, d):
    a, b = _mg(s, d, 0 if SUM else rh(s.shape), _sig(s.shape) if SUM else 1); out = np.empty(s.shape[:-1] + (2 * s.shape[-1],), s.dtype)
    out[..., 0::2] = a; out[..., 1::2] = b; return out
def vmerge(s, d):
    a, b = _mg(s, d, 0 if SUM else rv(s.shape), _sig(s.shape) if SUM else 1); out = np.empty((s.shape[0], 2 * s.shape[1], s.shape[2]), s.dtype)
    out[:, 0::2] = a; out[:, 1::2] = b; return out
T = lambda x: np.swapaxes(x, 1, 2)    # (ns, rows, cols) <-> (ns, cols, rows)

def vpred(s, kind, above, below=None):  # s (ns, rows, cols); above/below (ns, cols, 2) or None
    return T(pred(T(s), kind, above if (kind[0] == 'c' or kind.endswith('a')) else None, below))

def rec_level(C, lev, L, nv, A, Alo, Ahi, kH, kV, ctx):
    """returns final A (ns, r, c).  A = source at this level (enc) or zeros (dec)."""
    if lev > L:
        return C.qc((lev, 'LL'), A, Alo, Ahi)
    _cur[:] = [lev, 'H']; Lc_s, dH_s = hsplit(A)
    Llo, _ = hsplit(Alo); Lhi, _ = hsplit(Ahi)          # floor-average boxes
    if lev <= nv:
        _cur[:] = [lev, 'V']; LL_s, dL_s = vsplit(Lc_s); LLlo, _ = vsplit(Llo); LLhi, _ = vsplit(Lhi)
        LL = rec_level(C, lev + 1, L, nv, LL_s, LLlo, LLhi, kH, kV, ctx)
        _cur[:] = [lev, 'V']
        p = vpred(LL, kV, ctx[lev][0] if ctx else None, ctx[lev][2] if ctx and len(ctx[lev]) > 2 else None)
        lo, hi = dint(LL, Llo[:, 0::2], Lhi[:, 0::2], Llo[:, 1::2], Lhi[:, 1::2], _sig(LL.shape) if SUM else rv(LL.shape))
        dL = C.qc((lev, 'LH'), dL_s - p, lo - p, hi - p) + p
        Lc = vmerge(LL, dL)
    else:
        _cur[:] = [lev, 'H']
        Lc = rec_level(C, lev + 1, L, nv, Lc_s, Llo, Lhi, kH, kV, ctx)
    _cur[:] = [lev, 'H']; pH = pred(Lc, kH)
    hlo, hhi = dint(Lc, Alo[..., 0::2], Ahi[..., 0::2], Alo[..., 1::2], Ahi[..., 1::2], _sig(Lc.shape) if SUM else rh(Lc.shape))
    elo, ehi = hlo - pH, hhi - pH; e_s = dH_s - pH
    if lev <= nv:
        _cur[:] = [lev, 'V']; HL_s, dE_s = vsplit(e_s); HLlo, _ = vsplit(elo); HLhi, _ = vsplit(ehi)
        HL = C.qc((lev, 'HL'), HL_s, HLlo, HLhi)
        p2 = vpred(HL, kV, ctx[lev][1] if ctx else None, ctx[lev][3] if ctx and len(ctx[lev]) > 2 else None)
        lo2, hi2 = dint(HL, elo[:, 0::2], ehi[:, 0::2], elo[:, 1::2], ehi[:, 1::2], _sig(HL.shape) if SUM else rv(HL.shape))
        dE = C.qc((lev, 'HH'), dE_s - p2, lo2 - p2, hi2 - p2) + p2
        e = vmerge(HL, dE)
    else:
        e = C.qc((lev, 'H'), e_s, elo, ehi)
    _cur[:] = [lev, 'H']; return hmerge(Lc, e + pH)

def ctx_of(prev, L, nv, kH):
    """causal context rows from the reconstructed previous slice (ns, R, C): per 2-D level the last 2 rows of LL and HL."""
    out = {}; A = prev
    for lev in range(1, nv + 1):
        _cur[:] = [lev, 'H']; Lc, dH = hsplit(A); _cur[:] = [lev, 'V']; LL, _ = vsplit(Lc)
        e = dH - pred(Lc, kH); HL, _ = vsplit(e)
        l2 = LL[:, -2:, :] if LL.shape[1] >= 2 else np.concatenate([LL[:, -1:, :]] * 2, 1)
        h2 = HL[:, -2:, :] if HL.shape[1] >= 2 else np.concatenate([HL[:, -1:, :]] * 2, 1)
        out[lev] = (T(l2), T(h2)); A = LL
    return out

def run_coder(C, X, LO, HI, L, nv, kH, kV, causal):
    _slice0[0] = 0
    if not causal:
        return rec_level(C, 1, L, nv, X, LO, HI, kH, kV, None)
    out = np.zeros_like(X); Qall = {}
    for k in range(X.shape[0]):
        _slice0[0] = k - 1; ctx = ctx_of(out[k - 1:k], L, nv, kH) if k > 0 else None
        _slice0[0] = k
        Ck = Coder(C.mode, C.steps, {kk: v[k:k + 1] for kk, v in C.Qin.items()} if C.mode == 'dec' else None)
        out[k:k + 1] = rec_level(Ck, 1, L, nv, X[k:k + 1], LO[k:k + 1], HI[k:k + 1], kH, kV, ctx)
        C.nclamp += Ck.nclamp
        for kk, v in Ck.Q.items(): Qall.setdefault(kk, []).append(v)
    C.Q = {kk: np.concatenate(v, 0) for kk, v in Qall.items()}
    return out

def keys(L, nv):
    ks = []
    for lev in range(1, L + 1): ks += [(lev, b) for b in (('LH', 'HL', 'HH') if lev <= nv else ('H',))]
    return ks + [(L + 1, 'LL')]

def weights(sh, W, L, nv, kH, kV):
    """synthesis energy per band: integer impulse of 4096 with no clamps, one slice, decode mode."""
    big = 1 << 40; w = {}
    ks = keys(L, nv)
    X = np.zeros((1, sh, W), np.int64); LO = np.full(X.shape, -big, np.int64); HI = np.full(X.shape, big, np.int64)
    C0 = Coder('enc', {k: 1 for k in ks}); rec_level(C0, 1, L, nv, X, LO, HI, kH, kV, None)
    for k in ks:
        Qin = {kk: np.zeros_like(v) for kk, v in C0.Q.items()}
        z = Qin[k]; z[(0,) + tuple(s // 2 for s in z.shape[1:])] = 4096
        C = Coder('dec', {kk: 1 for kk in ks}, Qin)
        R = rec_level(C, 1, L, nv, np.zeros_like(X), LO, HI, kH, kV, None)
        w[k] = float((R.astype(float) / 4096) ** 2).sum() if False else float(((R.astype(float) / 4096) ** 2).sum())
    return w

def ent(q):
    q = np.asarray(q).ravel(); _, c = np.unique(q, return_counts=True); p = c / q.size
    return float(-(c * np.log2(p)).sum())

def code_plane(P, sh, L, nv, kH, kV, causal, Qf, kll, lo, hi, depth, wcache):
    H, W = P.shape
    if H % sh and _os.environ.get('HF_SHORTLAST', '1') == '1':
        return code_plane_short(P, sh, L, nv, kH, kV, causal, Qf, kll, lo, hi, depth, wcache)
    Hp = -(-H // sh) * sh
    X = np.vstack([P, np.repeat(P[-1:], Hp - H, 0)]).astype(np.int64).reshape(Hp // sh, sh, W)
    wk = (sh, W, L, nv, kH, kV)
    if wk not in wcache: wcache[wk] = weights(sh, W, L, nv, kH, kV)
    w = dict(wcache[wk]); ks = keys(L, nv); w[ks[-1]] *= 4.0 ** (-kll)
    steps = {k: max(1, int(round(2.0 ** round(Qf - 0.5 * math.log2(w[k]))))) for k in ks}
    LO = np.full(X.shape, lo, np.int64); HI = np.full(X.shape, hi, np.int64)
    C = Coder('enc', steps); Rr = run_coder(C, X, LO, HI, L, nv, kH, kV, causal)
    bits = sum(ent(C.Q[k]) for k in ks)
    R = Rr.reshape(Hp, W)[:H]; oor = int(((R < lo) | (R > hi)).sum())
    if _os.environ.get('HF_FAST'):
        err = np.abs(R - P).astype(float); mse = float((err ** 2).mean())
        ps = 99.0 if mse == 0 else 10 * math.log10(float(2 ** depth - 1) ** 2 / mse)
        return bits, ps, oor, True, True, [float(err[j::sh].mean()) for j in range(sh)], C.nclamp
    # decoder from indices alone must equal the encoder's reconstruction
    Cd = Coder('dec', steps, C.Q); Rd = run_coder(Cd, np.zeros_like(X), LO, HI, L, nv, kH, kV, causal)
    rt0 = bool(np.array_equal(Rd, Rr))
    # generation 2: encode the decoded picture (padded the same way) and compare indices + picture
    Y = np.vstack([R, np.repeat(R[-1:], Hp - H, 0)]).reshape(Hp // sh, sh, W)
    C2 = Coder('enc', steps); R2 = run_coder(C2, Y, LO, HI, L, nv, kH, kV, causal)
    g2 = bool(all(np.array_equal(C2.Q[k], C.Q[k]) for k in ks) and np.array_equal(R2, Rr))
    err = np.abs(R - P).astype(float); mse = float((err ** 2).mean())
    ps = 99.0 if mse == 0 else 10 * math.log10(float(2 ** depth - 1) ** 2 / mse)
    return bits, ps, oor, rt0, g2, [float(err[j::sh].mean()) for j in range(sh)], C.nclamp

def load(path, W, H, fr, fmt):
    cw = W // 2 if fmt == '422' else W; fs = W * H + 2 * cw * H
    d = np.fromfile(path, dtype='<u2', count=fs, offset=fr * fs * 2).astype(np.int64)
    return [d[:W * H].reshape(H, W), d[W * H:W * H + cw * H].reshape(H, cw), d[W * H + cw * H:].reshape(H, cw)]

if __name__ == '__main__':
    path, W, H, fr, sh, fmt, depth, lo, hi, tag = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), \
        int(sys.argv[5]), sys.argv[6], int(sys.argv[7]), int(sys.argv[8]), int(sys.argv[9]), sys.argv[10]
    variants = json.loads(sys.argv[11])     # name: [nv, kH, kV, causal]
    Qfs = json.loads(sys.argv[12]) if len(sys.argv) > 12 else [x / 2 + depth - 10 for x in range(3, 23)]
    kls = json.loads(sys.argv[13]) if len(sys.argv) > 13 else [-2, -1, 0]
    planes = load(path, W, H, fr, fmt)
    for p in planes: np.clip(p, lo, hi, out=p)
    out = {}; wc = {}
    for name, (nv, kH, kV, causal) in variants.items():
        res = {}
        for kll in kls:
            rows = []
            for Qf in Qfs:
                tb, ps, oor, rt0, g2, ph, ncl = 0.0, [], 0, True, True, [], 0
                for P in planes:
                    b, p, o, r0, g, f, nc = code_plane(P, sh, 5, nv, kH, kV, causal, Qf, kll, lo, hi, depth, wc)
                    tb += b; ps.append(p); oor += o; rt0 &= r0; g2 &= g; ph.append(f); ncl += nc
                rows.append((Qf, tb / planes[0].size, ps, oor, rt0, g2, ph, ncl))
            res[str(kll)] = rows; print(tag, name, kll, 'oor', sum(r[3] for r in rows), 'rt0', all(r[4] for r in rows),
                                        'g2', all(r[5] for r in rows), flush=True)
        out[name] = res
    json.dump(out, open(tag + '.json', 'w'))

def code_plane_short(P, sh, L, nv, kH, kV, causal, Qf, kll, lo, hi, depth, wcache):
    """full slices of sh rows + one short last slice of H % sh rows (its own geometry), sequential with causal context;
    same step rule (weights of the full-slice geometry), no padding anywhere."""
    H, W = P.shape; nfull = H // sh; rem = H - nfull * sh
    nv2 = min(nv, int(math.log2(rem)))
    wk = (sh, W, L, nv, kH, kV)
    if wk not in wcache: wcache[wk] = weights(sh, W, L, nv, kH, kV)
    w = dict(wcache[wk]); ks = keys(L, nv); w[ks[-1]] *= 4.0 ** (-kll)
    steps = {k: max(1, int(round(2.0 ** round(Qf - 0.5 * math.log2(w[k]))))) for k in ks}
    ks2 = keys(L, nv2); steps2 = {k: steps.get(k, steps[ks[-1]]) for k in ks2}
    def enc(Pin, Qin=None):
        rec = np.zeros((H, W), np.int64); Q = []
        for k in range(nfull + 1):
            r0 = k * sh; rows = sh if k < nfull else rem
            if rows == 0: break
            nvk = nv if rows == sh else nv2; st = steps if rows == sh else steps2
            X = (Pin[r0:r0 + rows][None] if Qin is None else np.zeros((1, rows, W))).astype(np.int64)
            LO = np.full(X.shape, lo, np.int64); HI = np.full(X.shape, hi, np.int64)
            _slice0[0] = k - 1; ctx = ctx_of(rec[r0 - sh:r0][None], L, nvk, kH) if (k > 0 and causal) else None
            _slice0[0] = k
            C = Coder('enc', st) if Qin is None else Coder('dec', st, Qin[k])
            Z = rec_level(C, 1, L, nvk, X, LO, HI, kH, kV, ctx)
            rec[r0:r0 + rows] = Z[0]; Q.append(C.Q)
        return rec, Q
    R, Q = enc(P)
    bits = 0.0
    allk = sorted(set(k for q in Q for k in q))
    for k in allk: bits += ent(np.concatenate([q[k].ravel() for q in Q if k in q]))
    oor = int(((R < lo) | (R > hi)).sum())
    if _os.environ.get('HF_FAST'):
        rt0 = g2 = True
    else:
        Rd, _ = enc(None, Q); rt0 = bool(np.array_equal(Rd, R))          # decoder from indices alone
        R2, Q2 = enc(R)
        g2 = bool(np.array_equal(R2, R) and all(np.array_equal(a[k], b[k]) for a, b in zip(Q, Q2) for k in a))
    err = np.abs(R - P).astype(float); mse = float((err ** 2).mean())
    ps = 99.0 if mse == 0 else 10 * math.log10(float(2 ** depth - 1) ** 2 / mse)
    return bits, ps, oor, rt0, g2, [float(err[:nfull * sh][j::sh].mean()) for j in range(sh)], 0

def ctx_below(nxt, L, nv, kH):
    """oracle/proxy context BELOW the slice: first 2 lowpass rows (LL, HL) per 2-D level of the rows below."""
    out = {}; A = nxt
    for lev in range(1, nv + 1):
        _cur[:] = [lev, 'H']; Lc, dH = hsplit(A); _cur[:] = [lev, 'V']; LL, _ = vsplit(Lc)
        e = dH - pred(Lc, kH); HL, _ = vsplit(e)
        l2 = LL[:, :2, :] if LL.shape[1] >= 2 else np.concatenate([LL[:, :1, :]] * 2, 1)
        h2 = HL[:, :2, :] if HL.shape[1] >= 2 else np.concatenate([HL[:, :1, :]] * 2, 1)
        out[lev] = (T(l2), T(h2)); A = LL
    return out
