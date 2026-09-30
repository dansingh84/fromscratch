#!/usr/bin/env python3
"""T2 -- slice structure test (SA13).  Intra, full frame, every plane, numpy.

Arms (5/3 integer lifting everywhere, 5 horizontal levels, same dead-zone quantiser,
band steps D/sqrt(synthesis gain), decoder clip, rate = zeroth-order entropy per band):
  ff   : full-frame 2-D 5/3, 5 vertical levels (continuous vertical transform; the XS-shape
         reference, NOT a candidate: latency/A5)
  sl2  : slice-local vertical 5/3, 2 levels, symmetric extension inside each slice (OMC-shape,
         without OMC's cross-slice term and blend)
  br   : BRACKETED slice: the slice's last row (anchor) is coded first as a 1-D horizontal row;
         the interior rows are a vertical 5/3 on the interval [anchor of the slice above,
         own anchor] with both endpoints FIXED (decoded values, never updated, never mirrored);
         log2(S) vertical levels; then 5 horizontal levels on each vertical-detail row.
Seam check: mean |decode - source| per row phase (row mod S), per plane.

usage: t2_slices.py SRC W H FMT DEPTH FRAME TAG S arms steps
"""
import sys, os, subprocess, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from t1_structure import (_rd, read_frame, H0, quant, recon, f53_1d, i53_1d, fwd53, inv53, gains53,
                          band_list, pad_to, psnr, LO, HI, NEG, SCR)

JH = 5
G1 = gains53(JH)

def hfwd(x):                      # horizontal-only 5/3, JH levels, rows independent
    c = x.copy(); w = c.shape[1]
    for j in range(JH):
        c[:, :w] = f53_1d(c[:, :w], 1); w //= 2
    return c

def hinv(c):
    c = c.copy(); w = c.shape[1] >> (JH - 1)
    for j in range(JH):
        c[:, :w] = i53_1d(c[:, :w], 1); w *= 2
    return c

def hbands(W):                    # (slice, 1-D gain) per horizontal band
    out = []; w = W
    for lev in range(1, JH + 1):
        out.append((slice(w // 2, w), G1[(lev, 'H')])); w //= 2
    out.append((slice(0, w), G1[(JH, 'L')]))
    return out

def qcode_rows(rows, D, gv, key):
    """horizontal transform + quantise (indices pooled per band under key) + inverse"""
    c = hfwd(rows); cq = np.zeros_like(c)
    for sl, gh in hbands(rows.shape[1]):
        Db = D / np.sqrt(gv * gh)
        q = quant(c[:, sl], Db); BAND_Q.setdefault((key, sl.start), []).append(q.ravel())
        cq[:, sl] = recon(q, Db)
    return hinv(cq)

# ---- bracketed vertical 5/3 on positions 0..S with fixed endpoints ----
def levels_pos(S):
    pos = list(range(S + 1)); out = []
    while len(pos) > 2:
        out.append((pos[1::2], pos[0::2])); pos = pos[0::2]
    return out            # list of (odd positions, even positions) per level, fine -> coarse

def br_fwd(X, S):
    X = X.copy()
    for odd, ev in levels_pos(S):
        for k, p in enumerate(odd):
            X[p] = X[p] - _rd(X[ev[k]] + X[ev[k + 1]], 1)
        for k in range(1, len(ev) - 1):
            X[ev[k]] = X[ev[k]] + _rd(X[odd[k - 1]] + X[odd[k]], 2)
    return X

def br_inv(X, S):
    X = X.copy()
    for odd, ev in reversed(levels_pos(S)):
        for k in range(1, len(ev) - 1):
            X[ev[k]] = X[ev[k]] - _rd(X[odd[k - 1]] + X[odd[k]], 2)
        for k, p in enumerate(odd):
            X[p] = X[p] + _rd(X[ev[k]] + X[ev[k + 1]], 1)
    return X

def br_gains(S):
    """float synthesis energy of a unit coefficient at each interior position (endpoints 0),
    and of a unit endpoint (anchor) summed over both slices it brackets."""
    def inv(X):
        X = X.astype(float).copy()
        for odd, ev in reversed(levels_pos(S)):
            for k in range(1, len(ev) - 1):
                X[ev[k]] -= (X[odd[k - 1]] + X[odd[k]]) / 4
            for k, p in enumerate(odd):
                X[p] += (X[ev[k]] + X[ev[k + 1]]) / 2
        return X
    g = {}
    for p in range(1, S):
        X = np.zeros(S + 1); X[p] = 1; g[p] = float((inv(X) ** 2).sum())
    X = np.zeros(S + 1); X[S] = 1; y = inv(X)
    g['anchor'] = (1.0 + 2 * float((y[1:S] ** 2).sum())) / float(os.environ.get('AM', '1')) ** 2
    return g

def code_br(x, D, S):
    Hh, W = x.shape
    g = br_gains(S)
    rec = np.zeros_like(x)
    # frame top: a virtual row -1 = source row 0, coded as an anchor (bits counted)
    above = qcode_rows(x[0:1], D, g['anchor'], 'A')
    for s in range(Hh // S):
        r0 = s * S
        a = qcode_rows(x[r0 + S - 1:r0 + S], D, g['anchor'], 'A')
        X = np.zeros((S + 1, W), dtype=np.int64)
        X[0] = above[0]; X[S] = a[0]; X[1:S] = x[r0:r0 + S - 1]
        C = br_fwd(X, S)
        Cq = C.copy()
        for p in range(1, S):
            Cq[p] = qcode_rows(C[p:p + 1], D, g[p], p & -p)[0]
        Y = br_inv(Cq, S)
        rec[r0:r0 + S - 1] = Y[1:S]; rec[r0 + S - 1] = a[0]
        above = a
    return np.clip(rec, LO, HI), 0.0

BAND_Q = {}

def code_bp(x, D, S):
    """bracketed, vertical closed-loop interpolation (no vertical update): rows coded coarse
    to fine, each = clamp(average of two decoded rows + horizontal-5/3-coded residual row)."""
    Hh, W = x.shape
    AMB = float(os.environ.get('AMB', '2'))
    RR = float(os.environ.get('RR', '1.0'))
    rec = np.zeros_like(x)
    above = np.clip(qcode_rows(x[0:1], D / AMB, 1.0, 'A'), LO, HI)
    order = []
    d = S // 2
    while d >= 1:
        order.append([(p, d) for p in range(d, S, 2 * d)]); d //= 2
    for s in range(Hh // S):
        r0 = s * S
        a = np.clip(qcode_rows(x[r0 + S - 1:r0 + S], D / AMB, 1.0, 'A'), LO, HI)
        Y = np.zeros((S + 1, W), dtype=np.int64); Y[0] = above[0]; Y[S] = a[0]
        for lev, grp in enumerate(order):
            Dl = D * RR ** (len(order) - 1 - lev)
            for p, dd in grp:
                pred = (Y[p - dd] + Y[p + dd] + 1) >> 1
                res = x[r0 + p - 1:r0 + p] - pred
                Y[p] = np.clip(pred + qcode_rows(res, Dl, 1.0, dd)[0], LO, HI)
        rec[r0:r0 + S - 1] = Y[1:S]; rec[r0 + S - 1] = a[0]
        above = a
    return rec, 0.0

def code_sl2(x, D, S):
    Hh, W = x.shape
    # gains: 2-D gains of a 2-vertical-level 5/3 on an S-row slice (interior approximation)
    bits = 0.0; rec = np.zeros_like(x)
    allq = {}
    for s in range(Hh // S):
        blk = x[s * S:(s + 1) * S]
        c = blk.copy()
        c = f53_1d(c, 0); c[:S // 2] = f53_1d(c[:S // 2], 0)       # 2 vertical levels
        c = hfwd(c)
        cq = np.zeros_like(c)
        vb = [(slice(S // 2, S), G1[(1, 'H')]), (slice(S // 4, S // 2), G1[(2, 'H')]),
              (slice(0, S // 4), G1[(2, 'L')])]
        for vs, gv in vb:
            for hs, gh in hbands(W):
                Db = D / np.sqrt(gv * gh)
                q = quant(c[vs, hs], Db); allq.setdefault((vs.start, hs.start), []).append(q.ravel())
                cq[vs, hs] = recon(q, Db)
        y = hinv(cq)
        y[:S // 2] = i53_1d(y[:S // 2], 0); y = i53_1d(y, 0)
        rec[s * S:(s + 1) * S] = y
    for k, v in allq.items():
        bits += H0(np.concatenate(v))
    return np.clip(rec, LO, HI), bits

def code_ff(x, D):
    c = fwd53(x, JH); cq = np.zeros_like(c); bits = 0.0
    for lev, name, rs, cs in band_list(c.shape, JH):
        gv = G1[(lev, 'L' if name[1] == 'L' else 'H')] if name != 'LL' else G1[(JH, 'L')]
        gh = G1[(lev, 'L' if name[0] == 'L' else 'H')] if name != 'LL' else G1[(JH, 'L')]
        Db = D / np.sqrt(gv * gh)
        q = quant(c[rs, cs], Db); bits += H0(q); cq[rs, cs] = recon(q, Db)
    return np.clip(inv53(cq, JH), LO, HI), bits

def run(arm, planes, D, S):
    recs, bits = [], 0.0
    for p in planes:
        H, W = p.shape
        if arm == 'ff':
            r, b = code_ff(pad_to(p, 32, 32, 0), D)
        elif arm == 'sl2':
            r, b = code_sl2(pad_to(p, S, 32, 0), D, S)
        elif arm == 'bp':
            BAND_Q.clear()
            r, b = code_bp(pad_to(p, S, 32, 0), D, S)
            b += sum(H0(np.concatenate(v)) for v in BAND_Q.values())
        else:
            BAND_Q.clear()
            r, b = code_br(pad_to(p, S, 32, 0), D, S)
            b += sum(H0(np.concatenate(v)) for v in BAND_Q.values())
        recs.append(r[:H, :W]); bits += b
    return recs, bits

def main():
    src, W, H, fmt, dep, fr, tag, S = sys.argv[1:9]
    W, H, fr, S = int(W), int(H), int(fr), int(S)
    arms = sys.argv[9].split(',')
    steps = [float(v) for v in sys.argv[10].split(',')]
    planes = read_frame(src, W, H, fmt, fr)
    sp = f'{SCR}/sa13_{tag}_src.yuv'
    np.concatenate([p.ravel() for p in planes]).astype('<u2').tofile(sp)
    for arm in arms:
        for D in steps:
            recs, bits = run(arm, planes, D, S)
            dp = f'{SCR}/sa13_{tag}_dec.yuv'
            np.concatenate([r.ravel() for r in recs]).astype('<u2').tofile(dp)
            out = subprocess.run(['bash', NEG, sp, dp, str(W), str(H), fmt, dep, '1'],
                                 capture_output=True, text=True)
            if out.returncode != 0:
                print('NEG FAILED', out.stderr[-300:]); sys.exit(2)
            neg = out.stdout.strip().split()[-1]
            ph = []
            for k in range(3):
                e = np.abs(recs[k] - planes[k]).astype(float)
                rp = np.array([e[j::S].mean() for j in range(S)])
                ph.append(f'{rp[0]:.2f}/{rp[1:S-1].mean():.2f}/{rp[S-1]:.2f}')
            print(f'{tag} {arm:3s} S={S} D={D:5.1f} bpp={bits/(W*H):.3f} '
                  f'Y={psnr(recs[0],planes[0]):.2f} Cb={psnr(recs[1],planes[1]):.2f} '
                  f'Cr={psnr(recs[2],planes[2]):.2f} NEG={neg} '
                  f'rowphase(first/mid/last) Y {ph[0]} Cb {ph[1]} Cr {ph[2]}', flush=True)
            if os.environ.get('KEEP'):
                os.replace(dp, f'{SCR}/sa13_{tag}_{arm}_D{int(D)}.yuv')
            else:
                os.remove(dp)
    if not os.environ.get('KEEP'): os.remove(sp)

if __name__ == '__main__':
    main()
