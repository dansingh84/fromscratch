#!/usr/bin/env python3
"""Dictionary capacity study — testing the "bigger tables are dead" claim myself.

Axes swept (all on real dumped OMC symbol streams, train/test split):
  - context states: 4 (binary sig), 16 (magnitude), 64 (finer magnitude),
    64p (magnitude x parent-band class for finest bands — my scheme)
  - table-group bank size K: 1..64, Lloyd-trained on TRAIN, with per-record
    best-group selection on TEST charged at ceil(log2 K) bits per record —
    exactly the codec's real per-slice-band selection mechanism, scaled.
  - oracle: tables fitted to the TEST clips themselves (the absolute ceiling
    of any table-based dictionary for this footage).
Table probabilities quantized to 1/1024 (tANS realism) before scoring.
"""
import json, os
import numpy as np

W_ = os.path.dirname(os.path.abspath(__file__))
TRAIN = ["beach", "aerial", "couch", "soccer"]
TEST = ["heli", "graincell", "mms", "cow"]
NSYM = 17
CATB = (2 ** np.arange(1, 17)).astype(np.int64)

def cat_of(a): return np.searchsorted(CATB, a, side="right").astype(np.int64) + (a > 0)
def q2(a): return np.clip(np.where(a == 0, 0, np.where(a == 1, 1, np.where(a <= 3, 2, 3))), 0, 3)
def q3(a):
    out = np.zeros_like(a)
    for lo, hi, v in ((1,1,1),(2,2,2),(3,4,3),(5,7,4),(8,13,5),(14,25,6),(26,1<<30,7)):
        out = np.where((a >= lo) & (a <= hi), v, out)
    return out

def load(clip, max_frames=3):
    """Memory-frugal: cap frames per clip (dumps up to 1 GB otherwise)."""
    p = os.path.join(W_, f"dump2_{clip}.bin")
    buf = np.fromfile(p, dtype=np.uint8)
    off = 0; recs = []
    while off + 32 <= len(buf):
        hdr = buf[off:off+32].view(np.int32)
        frame, sl, plane, band, shift, w, n, mode = [int(x) for x in hdr]
        off += 32
        if n <= 0 or w <= 0 or off + 4*n > len(buf): break
        if frame >= max_frames:
            off += 4*n; continue
        v = buf[off:off+2*n].view(np.int16).astype(np.int64); off += 4*n
        h = n // w
        recs.append(dict(frame=frame, sl=sl, plane=plane, band=band,
                         v=v[:h*w].reshape(h, w)))
    return recs

PARENT = {7: 4, 8: 5, 9: 6}

def rec_ctx(recs, i, scheme):
    r = recs[i]; a = np.abs(r["v"])
    l = np.zeros_like(a); l[:, 1:] = a[:, :-1]
    up = np.zeros_like(a); up[1:, :] = a[:-1, :]
    if scheme == "ctx4":   return (l > 0) * 1 + (up > 0) * 2, 4
    if scheme == "ctx16":  return q2(l) * 4 + q2(up), 16
    if scheme == "ctx64":  return q3(l) * 8 + q3(up), 64
    if scheme == "ctx64p":
        base = q2(l) * 4 + q2(up)
        par = np.zeros_like(a)
        if r["band"] in PARENT:
            for j in range(max(0, i - 8), i):
                rp = recs[j]
                if (rp["frame"], rp["sl"], rp["plane"], rp["band"]) == \
                   (r["frame"], r["sl"], r["plane"], PARENT[r["band"]]):
                    pv = np.abs(rp["v"]); h, w = a.shape
                    par = pv[np.minimum(np.arange(h) // 2, pv.shape[0]-1)][:, np.minimum(np.arange(w) // 2, pv.shape[1]-1)]
                    break
        return base * 4 + q2(par), 64
    raise ValueError(scheme)

def build_hists(clips, scheme):
    out = []
    for c in clips:
        recs = load(c)
        for i, r in enumerate(recs):
            ctx, nctx = rec_ctx(recs, i, scheme)
            cat = np.minimum(cat_of(np.abs(r["v"])), NSYM - 1)
            h = np.zeros((nctx, NSYM), dtype=np.int64)
            np.add.at(h, (ctx.ravel(), cat.ravel()), 1)
            raw = int(np.where(cat > 0, cat, 0).sum())
            out.append((h, raw))
    H = np.stack([x[0] for x in out]).astype(np.float32)
    raws = np.array([x[1] for x in out], dtype=np.int64)
    return H, raws

def lloyd(H, K, iters=8):
    n = len(H)
    energy = (H * np.arange(NSYM)).sum(axis=(1, 2)) / np.maximum(H.sum(axis=(1, 2)), 1)
    order = np.argsort(energy)
    assign = np.zeros(n, dtype=np.int64)
    for k in range(K):
        assign[order[k * n // K:(k + 1) * n // K]] = k
    for _ in range(iters):
        tabs = np.stack([-(np.log2((H[assign == k].sum(axis=0) + 1) /
                                   (H[assign == k].sum(axis=0) + 1).sum(axis=1, keepdims=True)))
                         if (assign == k).any() else np.full(H.shape[1:], np.log2(NSYM))
                         for k in range(K)])
        costs = np.einsum("rcs,kcs->rk", H, tabs)
        new = costs.argmin(axis=1)
        if (new == assign).all(): break
        assign = new
    # quantized final tables
    tabs = []
    for k in range(K):
        g = H[assign == k].sum(axis=0) + 1 if (assign == k).any() else np.ones(H.shape[1:])
        cc = np.maximum(np.round(g / g.sum(axis=1, keepdims=True) * 1024), 1)
        tabs.append(-np.log2(cc / cc.sum(axis=1, keepdims=True)))
    return np.stack(tabs)

def eval_bank(Htest, raws, tabs, K):
    costs = np.einsum("rcs,kcs->rk", Htest, tabs)
    best = costs.min(axis=1).sum()
    sel = len(Htest) * max(1, int(np.ceil(np.log2(max(K, 2)))))
    return best + raws.sum() + sel

def main():
    import os as _os
    results = json.load(open(os.path.join(W_,"capacity_study.json"))) if _os.path.exists(os.path.join(W_,"capacity_study.json")) else {}
    base = results.get("ctx4/K1",{}).get("total")
    import sys
    schemes = sys.argv[1:] or ["ctx4", "ctx16", "ctx64", "ctx64p"]
    for scheme in schemes:
        Htr, _ = build_hists(TRAIN, scheme)
        Hte, raws = build_hists(TEST, scheme)
        for K in [1, 4, 8, 16, 64]:
            tabs = lloyd(Htr, K)
            total = eval_bank(Hte, raws, tabs, K)
            rom_kb = K * tabs.shape[1] * 16 * 2 / 1024.0
            exp_kb = K * tabs.shape[1] * 6304 / 1024.0
            if base is None: base = total
            key = f"{scheme}/K{K}"
            results[key] = dict(total=float(total), vs_base=100*(1-total/base),
                                count_rom_kb=rom_kb, expanded_kb=exp_kb)
            print(f"{key:12s} total={total/1e6:8.2f}Mb vs ctx4/K1: {100*(1-total/base):+.2f}%  "
                  f"countROM={rom_kb:7.1f}KB expanded={exp_kb/1024:6.2f}MB", flush=True)
        # oracle: fit to the test clips themselves (ceiling), K=8
        tabs_o = lloyd(Hte, 8)
        total_o = eval_bank(Hte, raws, tabs_o, 8)
        key = f"{scheme}/ORACLE8"
        results[key] = dict(total=float(total_o), vs_base=100*(1-total_o/base))
        print(f"{key:12s} total={total_o/1e6:8.2f}Mb vs ctx4/K1: {100*(1-total_o/base):+.2f}%  (fit-to-test ceiling)", flush=True)
    json.dump(results, open(os.path.join(W_, "capacity_study.json"), "w"), indent=1)

if __name__ == "__main__":
    main()
