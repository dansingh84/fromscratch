#!/usr/bin/env python3
"""Test campaign 3 — TCQ (union-of-cosets, 8-state) on real band coefficients.

Marcellin-Fischer style: reconstruction alphabet = the existing lattice
(multiples of D = 2^s), split into cosets A0 (even multiples) / A1 (odd
multiples); an 8-state rate-1/2 trellis (next = ((state<<1)|b)&7, coset =
parity(state) xor b) constrains which coset each coefficient may use; Viterbi
minimizes D_mse + lambda*R with integer costs. No side bits (path implicit).

Tests:
  R  rate-distortion vs scalar deadzone quant at matched empirical entropy,
     real band data from real masters via the (fixed) perfect-reconstruction
     transform, across content kinds incl. matte + noise adversarial
  G  THE DECISIVE ONE - generation replay: quantize -> reconstruct -> re-run
     TCQ on the reconstruction (same D, same lambda): % of indices that
     change, over 3 simulated generations; also with a +/-1-perturbed input
  O  op-count audit (adds/compares per coefficient)
"""
import os, sys
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../omc2/harness"))
import proto

W_ = os.path.dirname(os.path.abspath(__file__))

def load_bands(name, W, H, fmt, depth, frame=2):
    cw = W//2 if fmt == 422 else W
    fw = W*H + 2*cw*H
    d = np.fromfile(os.path.join(W_, f"m_{name}.yuv"), dtype="<u2",
                    offset=frame*fw*2, count=fw)
    y = d[:W*H].reshape(H, W).astype(np.int32) - (1 << (depth-1))
    out = []
    for y0 in range(0, min(H, 512), 16):
        out.append(proto.slice_fwd2(y[y0:y0+16].astype(np.int32)))
    return out  # list of band dicts

def entropy_bits(q):
    """v4.4-model-class empirical rate: 16-state magnitude ctx conditional
    entropy + raw (cat-1 + sign) bits. Same estimator for both arms."""
    a = np.abs(q)
    cat = np.zeros_like(a)
    nz = a > 0
    cat[nz] = np.floor(np.log2(a[nz])).astype(a.dtype) + 1
    def q2(x): return np.clip(np.where(x==0,0,np.where(x==1,1,np.where(x<=3,2,3))),0,3)
    l = np.zeros_like(a); l[:,1:] = a[:,:-1]
    up = np.zeros_like(a); up[1:,:] = a[:-1,:]
    ctx = q2(l)*4 + q2(up)
    tot = 0.0
    for cx in range(16):
        m = ctx == cx
        n = int(m.sum())
        if n == 0: continue
        h = np.bincount(cat[m].ravel().astype(np.int64), minlength=20).astype(np.float64)
        p = h[h>0]/n
        tot += -(p*np.log2(p)).sum()*n
    return tot + float(cat.sum())

def scalar_q(c, s, dz9=True):
    a = np.abs(c); bias = 1 << (s-1)
    q = (a + bias) >> s
    if dz9:
        q = np.where((q == 1) & ((a.astype(np.int64) << 4) < (9 << s)), 0, q)
    return (np.sign(c)*q).astype(np.int64)

# --- TCQ ---
NEXT = np.array([[ (st*2+b) & 7 for b in (0,1)] for st in range(8)])
def coset_of(st, b): return (st & 1) ^ b

def tcq_quant(c_row, s, lam):
    """Viterbi over one row. Returns q indices (multiples of D=2^s)."""
    D = 1 << s
    n = len(c_row)
    INF = float("inf")
    cost = np.full(8, 0.0); cost[1:] = INF
    back = np.zeros((n, 8), np.int8)
    qidx = np.zeros((n, 8), np.int64)
    for i, c in enumerate(c_row):
        newc = np.full(8, INF); nb = np.zeros(8, np.int8); nq = np.zeros(8, np.int64)
        for st in range(8):
            if cost[st] == INF: continue
            for b in (0, 1):
                cs = coset_of(st, b)
                # nearest lattice point of parity cs to c (deadzone-ish: also test 0 when cs==0)
                k = int(np.round(c / (2.0*D)))*2 + cs if cs else int(np.round(c/(2.0*D)))*2
                cands = [k, k-2, k+2] if cs == 0 else [k, k-2, k+2]
                best = None
                for kk in cands:
                    if cs == 1 and kk % 2 == 0: kk += 1
                    if cs == 0 and kk % 2 == 1: kk += 1
                    d2 = float(c - kk*D)**2
                    r = 1 + (abs(kk).bit_length() if kk else 0)  # category-cost proxy
                    val = d2 + lam*r
                    if best is None or val < best[0]: best = (val, kk)
                ns = NEXT[st][b]
                tot = cost[st] + best[0]
                if tot < newc[ns]:
                    newc[ns] = tot; nb[ns] = st; nq[ns] = best[1]
        cost = newc; back[i] = nb; qidx[i] = nq
    # traceback
    st = int(np.argmin(cost))
    out = np.zeros(n, np.int64)
    for i in range(n-1, -1, -1):
        out[i] = qidx[i, st]
        st = int(back[i, st])
    return out

def run_rd():
    CLIPS = [("beach",2048,1152,422,10), ("cow",4480,3096,444,12),
             ("aerial",2048,1152,422,10), ("talking",1280,720,422,10)]
    for name, W, H, fmt, depth in CLIPS:
        slices = load_bands(name, W, H, fmt, depth)
        # use HL1 (band 8) rows, s=4
        s = 4
        rows = []
        for bands in slices[:8]:
            rows.append(bands[8])
        C = np.vstack(rows)[:64]
        qs = scalar_q(C, s)
        sc_bits = entropy_bits(qs); sc_d = float(((C - (qs << s))**2).sum())
        # lambda search to match rate
        lam_lo, lam_hi = 1.0, 100000.0
        for _ in range(18):
            lam = (lam_lo*lam_hi)**0.5
            qt = np.vstack([tcq_quant(r.astype(np.float64), s, lam) for r in C])
            t_bits = entropy_bits(qt)
            if t_bits > sc_bits: lam_lo = lam
            else: lam_hi = lam
        t_d = float(((C - (qt << s))**2).sum())
        gain_db = 10*np.log10(sc_d/t_d) if t_d > 0 else float('inf')
        print(f"{name:8s} band HL1 s={s}: scalar {sc_bits/1e3:7.1f}kb D={sc_d:.3e} | "
              f"TCQ {t_bits/1e3:7.1f}kb D={t_d:.3e} -> {gain_db:+.2f} dB at matched rate", flush=True)

def run_gen():
    name, W, H, fmt, depth = "beach", 2048, 1152, 422, 10
    slices = load_bands(name, W, H, fmt, depth)
    s, lam = 4, 3000.0
    C = np.vstack([b[8] for b in slices[:8]])[:64].astype(np.float64)
    q1 = np.vstack([tcq_quant(r, s, lam) for r in C])
    rec1 = (q1 << s).astype(np.float64)
    q2_ = np.vstack([tcq_quant(r, s, lam) for r in rec1])
    rec2 = (q2_ << s).astype(np.float64)
    q3_ = np.vstack([tcq_quant(r, s, lam) for r in rec2])
    ch12 = int((q1 != q2_).sum()); ch23 = int((q2_ != q3_).sum())
    n = q1.size
    d12 = float(np.abs(rec1 - rec2).mean());
    print(f"GEN replay: q changes gen1->2: {ch12}/{n} ({100*ch12/n:.2f}%), gen2->3: {ch23}/{n} ({100*ch23/n:.2f}%); mean |rec drift| g1->2 = {d12:.3f} codes", flush=True)
    # perturbed input (simulating upstream gen-2 noise)
    rng = np.random.default_rng(5)
    Cp = C.copy()
    m = rng.random(C.shape) < 0.01
    Cp[m] += rng.choice([-1.0, 1.0], int(m.sum()))
    qp = np.vstack([tcq_quant(r, s, lam) for r in Cp])
    print(f"PERTURB 1% +/-1: q changes vs clean: {int((qp!=q1).sum())}/{n} ({100*(qp!=q1).sum()/n:.2f}%)", flush=True)

if __name__ == "__main__":
    if sys.argv[1:] == ["G"]:
        run_gen()
    else:
        run_rd()
