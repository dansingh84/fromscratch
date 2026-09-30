#!/usr/bin/env python3
"""T1 -- intra structure test (SA13).  Full frame, every plane, numpy only.

Arms (all at the same dead-zone quantiser  q = sgn(r) floor(|r|/D),  recon (|q|+beta)D):
  b53  : integer 5/3 lifting, 5 levels 2-D separable (Mallat), band steps D/sqrt(G_b),
         decoder CLIPS to [lo,hi] (the incumbent-style open-loop transform; not legal-exact)
  sep  : closed-loop hierarchical interpolation, separable order (row 2-tap, then column 2-tap)
         = the falsified predict-only family (control)
  qx   : closed-loop hierarchical, quincunx order: centre from 4 diagonal corners, then the
         two axial phases from their 4 axial neighbours (all final)
  qxd  : as qx, but each phase picks the neighbour pair with the smaller difference
Closed-loop arms: every sample = clamp(pred + R(q), lo, hi); nothing else.
Rate = sum over groups (band / level-phase) of zeroth-order entropy of the indices.

usage: t1_structure.py SRC.yuv W H FMT DEPTH FRAME TAG [arms] [steps]
"""
import sys, os, subprocess, numpy as np

LO, HI = int(os.environ.get('LEG_LO', 4)), int(os.environ.get('LEG_HI', 1019))   # legal range (env for full-range arms)
BETA = 0.375
NEG = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/shared_tools/negscore.sh'
SCR = os.environ.get('SCR', '/tmp')

def read_frame(path, W, H, fmt, f):
    cw = W if fmt == '444' else W // 2
    n = W * H + 2 * cw * H
    a = np.fromfile(path, dtype='<u2', count=n, offset=2 * n * f).astype(np.int64)
    return [a[:W*H].reshape(H, W), a[W*H:W*H+cw*H].reshape(H, cw), a[W*H+cw*H:].reshape(H, cw)]

def H0(q):
    if q.size == 0: return 0.0
    _, c = np.unique(q, return_counts=True)
    p = c / q.size
    return float(-(c * np.log2(p)).sum())

def quant(r, D):
    q = np.sign(r) * np.floor(np.abs(r) / D)
    return q.astype(np.int64)

def recon(q, D):
    return (np.sign(q) * np.floor((np.abs(q) + BETA) * D + 0.5)).astype(np.int64)

# ---------------- 5/3 ----------------
RNDE = os.environ.get('RND', 'floor') == 'even'
def _rd(v, k):                    # v / 2^k : floor, or round-half-to-even when RND=even
    if not RNDE:
        return v >> k
    q = v >> k; r = v - (q << k); h = 1 << (k - 1)
    return q + ((r > h) | ((r == h) & ((q & 1) == 1)))

def f53_1d(x, ax):
    x = np.moveaxis(x, ax, 0)
    e, o = x[0::2].copy(), x[1::2].copy()
    en = np.concatenate([e[1:], e[-1:]], 0)
    d = o - _rd(e + en, 1)
    dp = np.concatenate([d[:1], d[:-1]], 0)
    s = e + _rd(dp + d, 2)
    return np.moveaxis(np.concatenate([s, d], 0), 0, ax)

def i53_1d(y, ax):
    y = np.moveaxis(y, ax, 0)
    n = y.shape[0] // 2
    s, d = y[:n], y[n:]
    dp = np.concatenate([d[:1], d[:-1]], 0)
    e = s - _rd(dp + d, 2)
    en = np.concatenate([e[1:], e[-1:]], 0)
    o = d + _rd(e + en, 1)
    x = np.empty_like(y)
    x[0::2], x[1::2] = e, o
    return np.moveaxis(x, 0, ax)

def fwd53(x, J):
    c = x.copy()
    h, w = c.shape
    for j in range(J):
        c[:h, :w] = f53_1d(f53_1d(c[:h, :w], 1), 0)
        h //= 2; w //= 2
    return c

def inv53(c, J):
    c = c.copy()
    h, w = c.shape[0] >> (J - 1), c.shape[1] >> (J - 1)
    for j in range(J):
        c[:h, :w] = i53_1d(i53_1d(c[:h, :w], 0), 1)
        h *= 2; w *= 2
    return c

def gains53(J):
    # synthesis energy gain of each band, float lifting on a 1-D impulse (separable product)
    def inv1(y):
        n = len(y) // 2; s, d = y[:n], y[n:]
        dp = np.concatenate([d[:1], d[:-1]]); e = s - (dp + d) / 4
        en = np.concatenate([e[1:], e[-1:]]); o = d + (e + en) / 2
        x = np.empty(2 * n); x[0::2], x[1::2] = e, o; return x
    N = 1024
    g1 = {}
    for lev in range(1, J + 1):
        for kind in ('L', 'H'):
            y = np.zeros(N)
            ln = N >> lev
            pos = ln // 2 + (ln if kind == 'H' else 0)
            y[pos] = 1.0
            # inverse from level lev up
            for l in range(lev, 0, -1):
                n = N >> (l - 1)
                y[:n] = inv1(y[:n])
            g1[(lev, kind)] = float((y ** 2).sum())
    return g1

def band_list(shape, J):
    h, w = shape; out = []
    for lev in range(1, J + 1):
        h2, w2 = h >> lev, w >> lev
        out += [(lev, 'HL', slice(0, h2), slice(w2, 2*w2)), (lev, 'LH', slice(h2, 2*h2), slice(0, w2)),
                (lev, 'HH', slice(h2, 2*h2), slice(w2, 2*w2))]
    out.append((J, 'LL', slice(0, h >> J), slice(0, w >> J)))
    return out

def code_b53(x, D, J=5):
    c = fwd53(x, J)
    g = gains53(J)
    bits = 0.0; cq = np.zeros_like(c)
    for lev, name, rs, cs in band_list(c.shape, J):
        gv = g[(lev, 'L' if name[1] == 'L' else 'H')] if name != 'LL' else g[(J, 'L')]
        gh = g[(lev, 'L' if name[0] == 'L' else 'H')] if name != 'LL' else g[(J, 'L')]
        Db = D / np.sqrt(gv * gh)
        q = quant(c[rs, cs], Db)
        bits += H0(q)
        cq[rs, cs] = recon(q, Db)
    rec = np.clip(inv53(cq, J), LO, HI)
    return rec, bits

# ---------------- closed-loop hierarchical ----------------
def code_hcl(x, D, mode, ramp=1.0, S=32):
    Hp, Wp = x.shape
    rec = np.zeros_like(x)
    bits = 0.0
    # coarsest grid: raster DPCM (pred = left, first column pred = above, first = 512)
    Dt = D * ramp ** 5
    g = x[::S, ::S]
    gr = np.zeros_like(g); qs = []
    for i in range(g.shape[0]):
        for j in range(g.shape[1]):
            p = gr[i, j-1] if j > 0 else (gr[i-1, j] if i > 0 else 512)
            r = g[i, j] - p
            q = int(np.sign(r) * np.floor(abs(r) / Dt)); qs.append(q)
            v = p + int(np.sign(q) * np.floor((abs(q) + BETA) * Dt + 0.5))
            gr[i, j] = min(max(v, LO), HI)
    bits += H0(np.array(qs)); rec[::S, ::S] = gr
    s = S; lev = 5
    while s > 1:
        h = s // 2; Dl = D * ramp ** (lev - 1)
        def put(rs, cs, pred):
            nonlocal bits
            r = x[rs, cs] - pred
            q = quant(r, Dl); bits += H0(q)
            rec[rs, cs] = np.clip(pred + recon(q, Dl), LO, HI)
        if mode == 'sep':
            # rows on the coarse grid, midpoints between columns
            L = rec[0:Hp:s, 0:Wp-1:s]; R = rec[0:Hp:s, s::s]
            put((slice(0, Hp, s)), slice(h, Wp, s), (L + R + 1) >> 1)
            U = rec[0:Hp-1:s, 0:Wp:h]; Dn = rec[s::s, 0:Wp:h]
            put(slice(h, Hp, s), slice(0, Wp, h), (U + Dn + 1) >> 1)
        else:
            a = rec[0:Hp-1:s, 0:Wp-1:s]; b = rec[0:Hp-1:s, s::s]
            c = rec[s::s, 0:Wp-1:s];     d = rec[s::s, s::s]
            if mode == 'qxd':
                pdg = np.where(np.abs(a - d) <= np.abs(b - c), (a + d + 1) >> 1, (b + c + 1) >> 1)
            else:
                pdg = (a + b + c + d + 2) >> 2
            put(slice(h, Hp, s), slice(h, Wp, s), pdg)
            # axial R: (s i, s j + h): left/right coarse, up/down diag (mirror at frame edge)
            Lr = rec[0:Hp:s, 0:Wp-1:s]; Rr = rec[0:Hp:s, s::s]
            dg = rec[h:Hp:s, h:Wp:s]                       # rows s i + h
            Up = np.concatenate([dg[:1], dg], 0); Dn = np.concatenate([dg, dg[-1:]], 0)
            # axial C: (s i + h, s j): up/down coarse, left/right diag
            Uc = rec[0:Hp-1:s, 0:Wp:s]; Dc = rec[s::s, 0:Wp:s]
            Lc = np.concatenate([dg[:, :1], dg], 1); Rc = np.concatenate([dg, dg[:, -1:]], 1)
            if mode == 'qxd':
                pR = np.where(np.abs(Lr - Rr) <= np.abs(Up - Dn), (Lr + Rr + 1) >> 1, (Up + Dn + 1) >> 1)
                pC = np.where(np.abs(Uc - Dc) <= np.abs(Lc - Rc), (Uc + Dc + 1) >> 1, (Lc + Rc + 1) >> 1)
            else:
                pR = (Lr + Rr + Up + Dn + 2) >> 2
                pC = (Uc + Dc + Lc + Rc + 2) >> 2
            put(slice(0, Hp, s), slice(h, Wp, s), pR)
            put(slice(h, Hp, s), slice(0, Wp, s), pC)
        s = h; lev -= 1
    return rec, bits

def pad_to(x, mh, mw, extra):
    H, W = x.shape
    Hp = -(-H // mh) * mh + extra; Wp = -(-W // mw) * mw + extra
    return np.pad(x, ((0, Hp - H), (0, Wp - W)), mode='edge')

def psnr(a, b, peak=1023):
    m = np.mean((a.astype(float) - b) ** 2)
    return 99.0 if m == 0 else 10 * np.log10(peak * peak / m)

def run(arm, planes, D, ramp):
    recs, bits = [], 0.0
    for p in planes:
        H, W = p.shape
        if arm == 'b53':
            r, b = code_b53(pad_to(p, 32, 32, 0), D)
        else:
            r, b = code_hcl(pad_to(p, 32, 32, 1), D, arm, ramp)
        recs.append(r[:H, :W]); bits += b
    return recs, bits

def main():
    src, W, H, fmt, dep, fr, tag = sys.argv[1:8]
    W, H, fr = int(W), int(H), int(fr)
    arms = (sys.argv[8] if len(sys.argv) > 8 else 'b53,sep,qx,qxd').split(',')
    steps = [float(v) for v in (sys.argv[9] if len(sys.argv) > 9 else '6,10,16,26,40').split(',')]
    planes = read_frame(src, W, H, fmt, fr)
    sp = f'{SCR}/sa13_{tag}_src.yuv'
    np.concatenate([p.ravel() for p in planes]).astype('<u2').tofile(sp)
    for arm in arms:
        for ramp in ([1.0] if arm == 'b53' else [1.0, 0.8]):
            for D in steps:
                recs, bits = run(arm, planes, D, ramp)
                dp = f'{SCR}/sa13_{tag}_dec.yuv'
                np.concatenate([r.ravel() for r in recs]).astype('<u2').tofile(dp)
                out = subprocess.run(['bash', NEG, sp, dp, str(W), str(H), fmt, dep, '1'],
                                     capture_output=True, text=True)
                if out.returncode != 0:
                    print('NEG FAILED', out.stderr[-300:]); sys.exit(2)
                neg = out.stdout.strip().split()[-1]
                oob = sum(int(((r < LO) | (r > HI)).sum()) for r in recs)
                # row-phase (mod 32) and col-phase mean |err|, luma
                e = np.abs(recs[0] - planes[0])
                rp = np.array([e[k::32].mean() for k in range(32)])
                cp = np.array([e[:, k::32].mean() for k in range(32)])
                print(f'{tag} {arm:4s} ramp={ramp:.1f} D={D:5.1f} bpp={bits/(W*H):.3f} '
                      f'Y={psnr(recs[0],planes[0]):.2f} Cb={psnr(recs[1],planes[1]):.2f} '
                      f'Cr={psnr(recs[2],planes[2]):.2f} NEG={neg} oob={oob} '
                      f'rowph={rp.min():.2f}-{rp.max():.2f} colph={cp.min():.2f}-{cp.max():.2f}', flush=True)
                os.remove(dp)
    os.remove(sp)

if __name__ == '__main__':
    main()
