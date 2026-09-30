#!/usr/bin/env python3
"""T8 -- steady-state INTER model of BSC-1 (SA13).  numpy, every plane, zeroth-order entropy.

Bracketed slices (S rows; anchor = last row, coded first as a 1-D 5-level 5/3 row; interior =
vertical 5/3 on [decoded anchor above .. own decoded anchor] + 5 horizontal levels).
Temporal: one reference (previous decoded frame).  Per 32-sample block a motion vector that the
ENCODER derives from decoded data only (anchor rows vs reference), transmitted (bits counted as
the zeroth-order entropy of the vector differences to the block's vector in the previous frame).
  - anchor row of slice k : vector of the same block in slice k-1 (this frame), refined +-1 on the
    previous slice's decoded anchor; slice 0: previous frame's vector
  - interior of slice k   : full search +-R (x), +-R/2 (y) minimising SAD of BOTH decoded bracket
    anchors against the displaced reference
Rolling refresh: slice s is intra in frame f when f == 0 or s % P == f % P.
Rounding: 'even' = round-half-to-even in every lifting step (unbiased), 'floor' = plain floors.
Dead zone: zero threshold dz*step; cells [(q-1+dz)D, (q+dz)D); recon (q-1+dz+0.375)D.
Picture = clip(pred + decoded residual) (natural content: the projection is inactive, T7).

usage: t8_inter.py SRC W H FMT NF TAG S D [--round even|floor] [--dz 1.0] [--still] [--zeromv]
                   [--out DEC.yuv] [--P 8] [--R 8]
"""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from t1_structure import read_frame, H0, LO, HI
from t2_slices import br_gains, levels_pos

a = sys.argv[1:]
def opt(k, d, cast=str):
    return cast(a[a.index(k) + 1]) if k in a else d
src, W, H, fmt, NF, tag, S, D = a[0], int(a[1]), int(a[2]), a[3], int(a[4]), a[5], int(a[6]), float(a[7])
RND = opt('--round', 'even'); DZ = opt('--dz', 1.0, float); DZI = opt('--dzi', DZ, float); LAM = opt('--lam', 0.0, float); P = opt('--P', 8, int); R = opt('--R', 8, int)
STILL = '--still' in a; SRCMV = '--srcmv' in a; ZMV = '--zeromv' in a; OUT = opt('--out', None)
AM = float(os.environ.get('AM', '3')); JH = 5; BW = 32; BETA = 0.375

def rdiv(v, k):                         # v / 2^k rounded
    if RND == 'floor' or k == 0:
        return v >> k
    q = v >> k; r = v - (q << k); h = 1 << (k - 1)
    return q + ((r > h) | ((r == h) & ((q & 1) == 1)))

def P2(a_, b_): return rdiv(a_ + b_, 1)
def U4(a_, b_): return rdiv(a_ + b_, 2)

def f1(x, ax):
    x = np.moveaxis(x, ax, 0); e, o = x[0::2].copy(), x[1::2].copy()
    en = np.concatenate([e[1:], e[-1:]], 0); d = o - P2(e, en)
    dp = np.concatenate([d[:1], d[:-1]], 0); s = e + U4(dp, d)
    return np.moveaxis(np.concatenate([s, d], 0), 0, ax)

def i1(y, ax):
    y = np.moveaxis(y, ax, 0); n = y.shape[0] // 2; s, d = y[:n], y[n:]
    dp = np.concatenate([d[:1], d[:-1]], 0); e = s - U4(dp, d)
    en = np.concatenate([e[1:], e[-1:]], 0); o = d + P2(e, en)
    x = np.empty_like(y); x[0::2], x[1::2] = e, o
    return np.moveaxis(x, 0, ax)

def hf(x):
    c = x.copy(); w = c.shape[1]
    for _ in range(JH): c[:, :w] = f1(c[:, :w], 1); w //= 2
    return c

def hi_(c):
    c = c.copy(); w = c.shape[1] >> (JH - 1)
    for _ in range(JH): c[:, :w] = i1(c[:, :w], 1); w *= 2
    return c

def bf(X):
    X = X.copy()
    for odd, ev in levels_pos(S):
        for k, p in enumerate(odd): X[p] = X[p] - P2(X[ev[k]], X[ev[k + 1]])
        for k in range(1, len(ev) - 1): X[ev[k]] = X[ev[k]] + U4(X[odd[k - 1]], X[odd[k]])
    return X

def bi(X):
    X = X.copy()
    for odd, ev in reversed(levels_pos(S)):
        for k in range(1, len(ev) - 1): X[ev[k]] = X[ev[k]] - U4(X[odd[k - 1]], X[odd[k]])
        for k, p in enumerate(odd): X[p] = X[p] + P2(X[ev[k]], X[ev[k + 1]])
    return X

G = br_gains(S)
from t2_slices import G1
def hb(Wp):
    out = []; w = Wp
    for lev in range(1, JH + 1): out.append((slice(w // 2, w), G1[(lev, 'H')])); w //= 2
    out.append((slice(0, w), G1[(JH, 'L')])); return out

CUR = {'dz': DZ}
def quant(c, Dm):
    DZ = CUR['dz']
    t = np.abs(c) / Dm
    q = np.where(t >= DZ, np.floor(t - DZ) + 1, 0)
    return (np.sign(c) * q).astype(np.int64)

def recon(q, Dm, beta=None):
    DZ = CUR['dz']; aq = np.abs(q); b = BETA if beta is None else beta
    return (np.sign(q) * np.floor((aq - 1 + DZ + b) * Dm + 0.5) * (aq > 0)).astype(np.int64)
LLB = float(os.environ.get('LLB', '0.5'))   # reconstruction offset of the anchor LL band (carries the DC)

POOL = {}
def pool(key, q): POOL.setdefault(key, []).append(q.ravel())

def code_rows(res, gv, key):
    """1-D horizontal coding of residual rows sharing vertical gain gv"""
    c = hf(res); cq = np.zeros_like(c)
    for sl, gh in hb(res.shape[1]):
        Dm = D / np.sqrt(gv * gh); q = quant(c[:, sl], Dm); pool((key, sl.start), q)
        cq[:, sl] = recon(q, Dm, LLB if sl.start == 0 else None)
    return hi_(cq)

def shifted(ref, r, dy, dx, bx, w):
    """reference samples for row r, columns bx..bx+w-1, displaced by (dy, dx), edge-clamped"""
    rr = min(max(r + dy, 0), ref.shape[0] - 1)
    cols = np.clip(np.arange(bx + dx, bx + dx + w), 0, ref.shape[1] - 1)
    return ref[rr, cols]

def pred_rows(ref, rows, mv, Wp):
    out = np.zeros((len(rows), Wp), dtype=np.int64)
    for b in range(Wp // BW):
        dy, dx = mv[b]
        for i, r in enumerate(rows): out[i, b*BW:(b+1)*BW] = shifted(ref, r, dy, dx, b*BW, BW)
    return out

def derive(ref, anchors, rws, Wp, start):
    """encoder-side derivation from decoded rows only; fixed order, smallest |v| wins ties"""
    mv = []
    cands = sorted([(dy, dx) for dy in range(-R // 2, R // 2 + 1) for dx in range(-R, R + 1)],
                   key=lambda v: (abs(v[0]) + abs(v[1]), v))
    for b in range(Wp // BW):
        if start is not None:
            cands_b = [(start[b][0] + dy, start[b][1] + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)]
            cands_b.sort(key=lambda v: (abs(v[0]) + abs(v[1]), v))
        else:
            cands_b = cands
        best = None
        for v in cands_b:
            sad = sum(int(np.abs(an[b*BW:(b+1)*BW] - shifted(ref, r, v[0], v[1], b*BW, BW)).sum())
                      for an, r in zip(anchors, rws)) + (LAM * BW * len(rws) if v != (0, 0) else 0)
            if best is None or sad < best[0]: best = (sad, v)
        mv.append(best[1])
    return mv

frames = []
nfr_src = NF
for f in range(NF):
    frames.append(read_frame(src, W, H, fmt, 0 if STILL else f))
out_planes = [[None] * 3 for _ in range(NF)]
prevmv = [dict() for _ in range(3)]
mvbits = []
for k in range(3):
    ref = None
    for f in range(NF):
        x = frames[f][k]; Hh = -(-x.shape[0] // S) * S; Wp = -(-x.shape[1] // 32) * 32
        x = np.pad(x, ((0, Hh - x.shape[0]), (0, Wp - x.shape[1])), mode='edge')
        rec = np.zeros_like(x); nsl = Hh // S; curmv = {}
        above = None; above_mv = None
        for s in range(-1, nsl):
            intra = (f == 0) or ((s % P) == (f % P)) or ZMV and False
            if f == 0: intra = True
            arow = 0 if s < 0 else s * S + S - 1
            if intra or ref is None:
                mva = [(0, 0)] * (Wp // BW); pa = np.zeros((1, Wp), dtype=np.int64)
            else:
                if ZMV: mva = [(0, 0)] * (Wp // BW)
                elif above_mv is not None: mva = derive(ref, [above[0]], [arow - S], Wp, above_mv)
                else: mva = prevmv[k].get(('A', s), [(0, 0)] * (Wp // BW))
                pa = pred_rows(ref, [arow], mva, Wp)
            CUR['dz'] = DZ if (intra or ref is None) else DZI
            ra = code_rows(x[arow:arow + 1] - pa, G['anchor'] * AM ** -2 if False else G['anchor'] / AM ** 2,
                           ('A', intra))
            a_ = np.clip(pa + ra, LO, HI)
            if s < 0:
                above = a_; above_mv = None; continue
            r0 = s * S
            if intra or ref is None:
                mvi = [(0, 0)] * (Wp // BW)
            elif ZMV:
                mvi = [(0, 0)] * (Wp // BW)
            else:
                if SRCMV:   # control: vectors searched on the SOURCE rows of the slice (not canonical)
                    mvi = derive(ref, [x[r] for r in range(r0, r0 + S)], list(range(r0, r0 + S)), Wp, None)
                else:
                    mvi = derive(ref, [above[0], a_[0]], [r0 - 1, arow], Wp, None)
                prev = prevmv[k].get(s, [(0, 0)] * (Wp // BW))
                mvbits.extend([m[0] - p[0] for m, p in zip(mvi, prev)] + [m[1] - p[1] for m, p in zip(mvi, prev)])
            curmv[s] = mvi; curmv[('A', s + 1)] = mvi
            rows = list(range(r0 - 1, r0 + S))                        # bracket positions 0..S
            pr = pred_rows(ref, rows, mvi, Wp) if not (intra or ref is None) else np.zeros((S + 1, Wp), np.int64)
            X = np.zeros((S + 1, Wp), dtype=np.int64)
            X[0] = above[0] - pr[0]; X[S] = a_[0] - pr[S]; X[1:S] = x[r0:r0 + S - 1] - pr[1:S]
            C = bf(X); K = hf(C[1:S]); Kq = np.zeros_like(K)
            for p in range(1, S):
                for sl, gh in hb(Wp):
                    Dm = D / np.sqrt(G[p] * gh); q = quant(K[p - 1:p, sl], Dm)
                    pool(((p & -p), sl.start, intra), q); Kq[p - 1:p, sl] = recon(q, Dm)
            Z = X.copy(); Z[1:S] = hi_(Kq); Y = bi(Z)
            rec[r0:r0 + S - 1] = np.clip(pr[1:S] + Y[1:S], LO, HI); rec[r0 + S - 1] = a_[0]
            above = a_; above_mv = mvi
        prevmv[k] = curmv
        ref = rec
        out_planes[f][k] = rec[:frames[f][k].shape[0], :frames[f][k].shape[1]]

bits = sum(H0(np.concatenate(v)) for v in POOL.values()) + (H0(np.array(mvbits)) if mvbits else 0)
bpp = bits / (W * H * NF)
def ps(a_, b_):
    m = np.mean((a_.astype(float) - b_) ** 2); return 99.0 if m == 0 else 10 * np.log10(1023 ** 2 / m)
line = f'{tag} S={S} D={D} round={RND} dz={DZ} still={STILL} zeromv={ZMV} bpp={bpp:.3f} (mv {100*(H0(np.array(mvbits)) if mvbits else 0)/bits:.2f} %)'
for k, nm in enumerate(('Y', 'Cb', 'Cr')):
    p2 = np.mean([ps(out_planes[f][k], frames[f][k]) for f in range(2, NF)])
    off = np.mean([np.mean(out_planes[f][k].astype(float) - frames[f][k]) for f in range(8, NF)]) if NF > 8 else float('nan')
    e = np.concatenate([np.abs(out_planes[f][k] - frames[f][k]).astype(float) for f in range(8, NF)], 0) if NF > 8 else None
    rp = ''
    if e is not None:
        ph = np.array([e[j::S].mean() for j in range(S)])
        rp = f' rowph first/mid/last {ph[0]:.2f}/{ph[1:S-1].mean():.2f}/{ph[S-1]:.2f}'
    line += f' | {nm} PSNR(f2+) {p2:.2f} offset(f8+) {off:+.3f}{rp}'
print(line, flush=True)
if os.environ.get('PERFRAME'):
    for f in range(NF):
        print('  f%d' % f, ' '.join('%+.3f' % np.mean(out_planes[f][k].astype(float) - frames[f][k]) for k in range(3)))
if OUT:
    np.concatenate([np.concatenate([out_planes[f][k].ravel() for k in range(3)]) for f in range(NF)]).astype('<u2').tofile(OUT)
    if STILL:
        np.concatenate([np.concatenate([frames[f][k].ravel() for k in range(3)]) for f in range(NF)]).astype('<u2').tofile(OUT + '.src')
