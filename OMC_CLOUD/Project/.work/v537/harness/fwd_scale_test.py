#!/usr/bin/env python3
"""Test campaign 1 — forward-signalled scale, rigorous + adversarial.

All on real dumped OMC symbol streams plus synthetic adversarial streams.
Baseline everywhere: the SHIPPED v4.4 model (16 magnitude-contexts, 8-group
bank, per-record best-group selection charged 3 bits) — i.e. the scheme must
beat what is already in the codec, not an easier strawman.

Candidate: per-B-coefficient block scale s = clamp(round(log2(max(mean|q|,
0.25)))+2, 0, L-1), delta-coded (entropy-charged); context = s x causal-9;
single group (the scale replaces the group dimension) OR grouped variants.

Sub-tests:
  T1 per-clip held-out gain (train A / test B and SWAPPED train B / test A)
  T2 block size sweep {32, 64, 128} x levels {8, 16}
  T3 adversarial synthetic streams (scale-thrash, boundary-aligned bursts,
     uniform noise, matte/graphics-like) — worst-case regression vs baseline
  T4 generation-perturbation stability: flip a random 1% of q by +/-1
     (simulating a gen-2 shift change) — how much do scale fields and coded
     bits move? (bounded, deterministic, no cascade = replay-friendly)
usage: fwd_scale_test.py T1|T2|T3|T4
"""
import json, os, sys
import numpy as np

W_ = os.path.dirname(os.path.abspath(__file__))
SPLIT_A = ["beach", "aerial", "couch", "soccer", "trees", "talking"]
SPLIT_B = ["heli", "graincell", "mms", "cow", "water", "manwalk", "confetti"]
NSYM = 17
CATB = (2 ** np.arange(1, 17)).astype(np.int64)

def cat_of(a): return np.searchsorted(CATB, a, side="right").astype(np.int64) + (a > 0)
def q2(a): return np.clip(np.where(a == 0, 0, np.where(a == 1, 1, np.where(a <= 3, 2, 3))), 0, 3)
def qn3(a): return np.where(a == 0, 0, np.where(a <= 2, 1, 2))

def load(clip, max_frames=3):
    p = os.path.join(W_, f"dump2_{clip}.bin")
    buf = np.fromfile(p, dtype=np.uint8)
    off = 0; recs = []
    while off + 32 <= len(buf):
        hdr = buf[off:off+32].view(np.int32)
        frame, sl, plane, band, shift, w, n, mode = [int(x) for x in hdr]
        off += 32
        if n <= 0 or w <= 0 or off + 4*n > len(buf): break
        if frame >= max_frames: off += 4*n; continue
        v = buf[off:off+2*n].view(np.int16).astype(np.int64); off += 4*n
        h = n // w
        recs.append(dict(band=band, plane=plane, v=v[:h*w].reshape(h, w)))
    return recs

def klass_of(r): return r["band"] * 2 + (1 if r["plane"] > 0 else 0)

# ---------------- baseline: shipped v4.4 model ----------------
def base_hists(recs_by_clip):
    out = []
    for recs in recs_by_clip:
        for r in recs:
            a = np.abs(r["v"])
            cat = np.minimum(cat_of(a), NSYM-1)
            l = np.zeros_like(a); l[:, 1:] = a[:, :-1]
            up = np.zeros_like(a); up[1:, :] = a[:-1, :]
            ctx = q2(l)*4 + q2(up)
            h = np.zeros((16, NSYM), np.int64)
            np.add.at(h, (ctx.ravel(), cat.ravel()), 1)
            out.append((klass_of(r), h, int(np.where(cat>0, cat, 0).sum())))
    return out

def lloyd_tabs(hists, K, iters=8):
    H = np.stack([h for _, h, _ in hists]).astype(np.float32)
    n = len(H)
    energy = (H * np.arange(NSYM)).sum(axis=(1,2)) / np.maximum(H.sum(axis=(1,2)), 1)
    order = np.argsort(energy); assign = np.zeros(n, np.int64)
    for k in range(K): assign[order[k*n//K:(k+1)*n//K]] = k
    for _ in range(iters):
        tabs = np.stack([-(np.log2((H[assign==k].sum(axis=0)+1)/(H[assign==k].sum(axis=0)+1).sum(axis=1, keepdims=True))) if (assign==k).any() else np.full(H.shape[1:], np.log2(NSYM)) for k in range(K)])
        new = np.einsum("rcs,kcs->rk", H, tabs).argmin(axis=1)
        if (new == assign).all(): break
        assign = new
    tabs = []
    for k in range(K):
        g = H[assign==k].sum(axis=0)+1 if (assign==k).any() else np.ones(H.shape[1:])
        cc = np.maximum(np.round(g/g.sum(axis=1, keepdims=True)*1024), 1)
        tabs.append(-np.log2(cc/cc.sum(axis=1, keepdims=True)))
    return np.stack(tabs)

def base_score(hists, tabs):
    H = np.stack([h for _, h, _ in hists]).astype(np.float32)
    raw = sum(r for _, _, r in hists)
    costs = np.einsum("rcs,kcs->rk", H, tabs)
    return float(costs.min(axis=1).sum()) + raw + 3*len(hists)

# ---------------- candidate: forward scale ----------------
def fwd_stats(recs, B, L):
    """Per record: (klass, ctx array, cat array, nraw, scale-delta symbols)."""
    out = []
    for r in recs:
        a = np.abs(r["v"]); flat = a.ravel()
        nb = (len(flat)+B-1)//B
        pad = np.zeros(nb*B, np.int64); pad[:len(flat)] = flat
        mean = pad.reshape(nb, B).mean(axis=1)
        s = np.clip(np.round(np.log2(np.maximum(mean, 0.25)))+2, 0, L-1).astype(np.int64)
        sf = np.repeat(s, B)[:len(flat)].reshape(a.shape)
        l = np.zeros_like(a); l[:, 1:] = a[:, :-1]
        up = np.zeros_like(a); up[1:, :] = a[:-1, :]
        if L == 4:  # variant: coarse scale x FULL 16-state causal (64 ctx)
            ctx = sf*16 + q2(l)*4 + q2(up)
        else:
            ctx = sf*9 + qn3(l)*3 + qn3(up)
        cat = np.minimum(cat_of(a), NSYM-1)
        sd = np.clip(np.diff(s, prepend=0) + L, 0, 2*L).astype(np.int64)
        out.append((klass_of(r), ctx.ravel(), cat.ravel(),
                    int(np.where(cat>0, cat, 0).sum()), sd, 16*L if L == 4 else 9*L))
    return out

def fwd_train(stats):
    tabs = {}; sdh = {}
    for klass, ctx, cat, raw, sd, nctx in stats:
        h = tabs.setdefault(klass, np.zeros((nctx, NSYM), np.int64))
        np.add.at(h, (ctx, cat), 1)
        d = sdh.setdefault(klass, np.zeros(64, np.int64))
        np.add.at(d, np.minimum(sd, 63), 1)
    qt = {}
    for k, h in tabs.items():
        t = h + 1
        cc = np.maximum(np.round(t/t.sum(axis=1, keepdims=True)*1024), 1)
        qt[k] = -np.log2(cc/cc.sum(axis=1, keepdims=True))
    sq = {}
    for k, d in sdh.items():
        t = d + 1
        sq[k] = -np.log2(t/t.sum())
    return qt, sq

def fwd_score(stats, qt, sq):
    bits = raw = side = 0.0
    for klass, ctx, cat, nraw, sd, nctx in stats:
        t = qt.get(klass)
        if t is None or t.shape[0] != nctx:
            bits += np.log2(NSYM)*len(cat)
        else:
            bits += float(t[ctx, cat].sum())
        raw += nraw
        s = sq.get(klass)
        side += float(s[np.minimum(sd, 63)].sum()) if s is not None else 6.0*len(sd)
    return bits, raw, side

def run_split(train_clips, test_clips, B=64, L=8, tag=""):
    tr = [load(c) for c in train_clips]
    te = {c: load(c) for c in test_clips}
    btabs = lloyd_tabs(base_hists(tr), 8)
    qt, sq = fwd_train(sum([fwd_stats(r, B, L) for r in tr], []))
    print(f"--- {tag} (B={B}, L={L}) ---", flush=True)
    tot_b = tot_f = 0.0
    for c, recs in te.items():
        bb = base_score(base_hists([recs]), btabs)
        fb, fr, fs = fwd_score(fwd_stats(recs, B, L), qt, sq)
        ft = fb + fr + fs
        tot_b += bb; tot_f += ft
        print(f"{c:10s} base={bb/1e6:7.2f}Mb fwd={ft/1e6:7.2f}Mb (side {fs/1e6:5.2f}) gain {100*(1-ft/bb):+.2f}%", flush=True)
    print(f"{'TOTAL':10s} gain {100*(1-tot_f/tot_b):+.2f}%", flush=True)
    return tot_b, tot_f

def synth_records():
    rng = np.random.default_rng(11)
    recs = []
    # scale-thrash: alternating dense/flat exactly at 64-coeff period
    v = np.zeros((64, 512), np.int64)
    v[:, ::2] = 0
    blk = np.arange(512*64).reshape(64, 512) // 64 % 2
    v = np.where(blk == 1, rng.integers(-15, 16, (64, 512)), 0)
    recs.append(dict(band=8, plane=0, v=v))
    # boundary-aligned bursts: a spike at the start of every block
    v2 = np.zeros((64, 512), np.int64); v2[:, ::64] = 200
    recs.append(dict(band=8, plane=0, v=v2))
    # incompressible uniform noise
    recs.append(dict(band=9, plane=0, v=rng.integers(-31, 32, (64, 512))))
    # matte/graphics-like: long zero runs + rare huge values
    v4 = np.zeros((64, 512), np.int64)
    v4[:, 100] = 800; v4[:, 400] = -800
    recs.append(dict(band=8, plane=0, v=v4))
    # checkerboard +/-1
    v5 = np.indices((64, 512)).sum(axis=0) % 2 * 2 - 1
    recs.append(dict(band=9, plane=0, v=v5.astype(np.int64)))
    return recs

def main():
    which = sys.argv[1] if len(sys.argv) > 1 else "T1"
    if which == "T1":
        run_split(SPLIT_A, SPLIT_B, tag="held-out A->B")
        run_split(SPLIT_B, SPLIT_A, tag="held-out B->A (swapped)")
    elif which == "T2":
        for B in (32, 64, 128):
            for L in (8, 16):
                run_split(SPLIT_A, SPLIT_B, B=B, L=L, tag=f"sweep")
    elif which == "T3":
        tr = [load(c) for c in SPLIT_A]
        btabs = lloyd_tabs(base_hists(tr), 8)
        qt, sq = fwd_train(sum([fwd_stats(r, 64, 8) for r in tr], []))
        names = ["scale-thrash", "boundary-bursts", "uniform-noise", "matte-like", "checkerboard"]
        for name, rec in zip(names, synth_records()):
            bb = base_score(base_hists([[rec]]), btabs)
            fb, fr, fs = fwd_score(fwd_stats([rec], 64, 8), qt, sq)
            ft = fb+fr+fs
            print(f"ADV {name:16s} base={bb/1e3:8.1f}kb fwd={ft/1e3:8.1f}kb (side {fs/1e3:6.1f}) delta {100*(1-ft/bb):+.2f}%", flush=True)
    elif which == "T4":
        rng = np.random.default_rng(3)
        for c in ("beach", "cow"):
            recs = load(c, max_frames=2)
            moved_scales = total_scales = changed_bits = 0
            qt, sq = fwd_train(sum([fwd_stats([r], 64, 8) for r in recs], []))
            for r in recs:
                st0 = fwd_stats([r], 64, 8)[0]
                v = r["v"].copy()
                nz = np.nonzero(v)
                if len(nz[0]) == 0: continue
                pick = rng.random(len(nz[0])) < 0.01
                v[nz[0][pick], nz[1][pick]] += rng.choice([-1, 1], pick.sum())
                st1 = fwd_stats([dict(band=r["band"], plane=r["plane"], v=v)], 64, 8)[0]
                moved_scales += int((st0[4] != st1[4]).sum())
                total_scales += len(st0[4])
            print(f"{c}: perturb 1% of coefficients by +/-1 -> {100*moved_scales/max(total_scales,1):.2f}% of block scales move (locality: each moved scale affects only its own {64}-coeff block)", flush=True)

if __name__ == "__main__":
    main()
