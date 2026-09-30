#!/usr/bin/env python3
"""My own entropy/context study on OMC2's real dumped symbol streams.

Ground rules (learned from this project's falsification history):
  - 2-fold cross-validation: tables trained on TRAIN clips, bits scored on
    TEST clips (held out). In-sample numbers are reported only for reference.
  - Table realism: probabilities are quantized to k/1024 (k>=1) before
    scoring, so the tANS table-quantization loss is included.
  - Model granularity is IDENTICAL across schemes: one table set per
    (band-class 0..9) x (luma/chroma) = 20 classes, times the scheme's
    context count. Raw bits (cat-1 LSBs + sign) are counted identically in
    schemes 1-7 so deltas isolate the conditioning question.

Schemes:
  base4    ctx = sig(left) + 2*sig(above)                     (today's codec)
  mag16    ctx = q2|left| * 4 + q2|above|                     (R2 16-state)
  mag64    ctx = q3|left| * 8 + q3|above|                     (R2 64-state)
  fwd72    3-bit block-64 scale x 9-state causal (R2c), side cost charged
  par16    bands 7-9: ctx = q2|left| * 4 + q2|parent|  (MY: inter-scale ctx,
           decoder-derivable, zero side bits; other bands use mag16)
  pred16   ctx = base4 x q2|predmag| (MY: prediction-magnitude context for
           inter bands, decoder-derivable; intra bands use base4)
  mag64p   mag16 x q2|predmag| (64 states; MY combination)
Extras (raw-bit side, measured separately):
  sign9    P(sign | sgn(left), sgn(above)) per class vs 1.0 bit raw
  mant     P(top mantissa bit | cat, q2|left|) vs 1.0 bit raw
"""
import json, os, sys
import numpy as np

W_ = os.path.dirname(os.path.abspath(__file__))
TRAIN = ["beach", "aerial", "couch", "soccer"]
TEST = ["heli", "graincell", "mms", "cow"]

CATB = (2 ** np.arange(1, 17)).astype(np.int64)

def cat_of(a):
    return np.searchsorted(CATB, a, side="right").astype(np.int64) + (a > 0)

def q2(a):
    return np.clip(np.where(a == 0, 0, np.where(a == 1, 1, np.where(a <= 3, 2, 3))), 0, 3)

def q3(a):
    out = np.zeros_like(a)
    for lo, hi, v in ((1,1,1),(2,2,2),(3,4,3),(5,7,4),(8,13,5),(14,25,6),(26,1<<30,7)):
        out = np.where((a >= lo) & (a <= hi), v, out)
    return out

def qn3(a):  # 3-level for the causal-9 of fwd72
    return np.where(a == 0, 0, np.where(a <= 2, 1, 2))

def load(clip):
    """Yield per-band records: dict with v (2D), pred (2D), plane, band, shift, mode."""
    p = os.path.join(W_, f"dump2_{clip}.bin")
    buf = np.fromfile(p, dtype=np.uint8)
    off = 0
    recs = []
    while off + 32 <= len(buf):
        hdr = buf[off:off+32].view(np.int32)
        frame, sl, plane, band, shift, w, n, mode = [int(x) for x in hdr]
        off += 32
        if n <= 0 or w <= 0 or off + 4*n > len(buf):
            break
        v = buf[off:off+2*n].view(np.int16).astype(np.int64); off += 2*n
        pm = buf[off:off+2*n].view(np.int16).astype(np.int64); off += 2*n
        h = n // w
        recs.append(dict(frame=frame, sl=sl, plane=plane, band=band, shift=shift,
                         mode=mode, v=v[:h*w].reshape(h, w), pm=pm[:h*w].reshape(h, w)))
    return recs

def neigh(x):
    l = np.zeros_like(x); l[:, 1:] = x[:, :-1]
    a = np.zeros_like(x); a[1:, :] = x[:-1, :]
    return l, a

def parent_map(recs):
    """Index parent (level-2) record per (frame, sl, plane) for bands 7-9."""
    idx = {}
    for i, r in enumerate(recs):
        idx[(r["frame"], r["sl"], r["plane"], r["band"])] = i
    return idx

PARENT = {7: 4, 8: 5, 9: 6}

def contexts(recs, scheme):
    """Yield (class_id, ctx array, cat array, nraw array) per record."""
    pidx = parent_map(recs)
    for r in recs:
        v = r["v"]; a = np.abs(v)
        cat = cat_of(a)
        klass = r["band"] * 2 + (1 if r["plane"] > 0 else 0)
        l, up = neigh(a)
        if scheme == "base4":
            ctx = (l > 0) * 1 + (up > 0) * 2; nctx = 4
        elif scheme == "mag16":
            ctx = q2(l) * 4 + q2(up); nctx = 16
        elif scheme == "mag64":
            ctx = q3(l) * 8 + q3(up); nctx = 64
        elif scheme == "fwd72":
            flat = a.ravel()
            nb = (len(flat) + 63) // 64
            pad = np.zeros(nb * 64, dtype=np.int64); pad[:len(flat)] = flat
            mean = pad.reshape(nb, 64).mean(axis=1)
            s = np.clip(np.round(np.log2(np.maximum(mean, 0.25))) + 2, 0, 7).astype(np.int64)
            sfull = np.repeat(s, 64)[:len(flat)].reshape(a.shape)
            ctx = sfull * 9 + qn3(l) * 3 + qn3(up); nctx = 72
            r["_scost"] = s  # side info, charged below
        elif scheme == "par16":
            if r["band"] in PARENT:
                pk = (r["frame"], r["sl"], r["plane"], PARENT[r["band"]])
                if pk in pidx:
                    pv = np.abs(recs[pidx[pk]]["v"])
                    h, w = a.shape
                    pr = pv[np.minimum(np.arange(h) // 2, pv.shape[0]-1)][:, np.minimum(np.arange(w) // 2, pv.shape[1]-1)]
                    ctx = q2(l) * 4 + q2(pr); nctx = 16
                else:
                    ctx = q2(l) * 4 + q2(up); nctx = 16
            else:
                ctx = q2(l) * 4 + q2(up); nctx = 16
        elif scheme == "pred16":
            pm = r["pm"]
            ctx = ((l > 0) * 1 + (up > 0) * 2) * 4 + q2(pm); nctx = 16
        elif scheme == "mag64p":
            pm = r["pm"]
            ctx = (q2(l) * 4 + q2(up)) * 4 + q2(pm); nctx = 64
        else:
            raise ValueError(scheme)
        nraw = np.where(cat > 0, cat, 0)  # (cat-1) LSBs + 1 sign
        yield klass, nctx, ctx.ravel(), cat.ravel(), nraw.ravel(), r

NSYM = 17  # cat 0..16 guard

def accumulate(clips, scheme):
    hists = {}
    scost_hist = {}
    for c in clips:
        recs = load(c)
        for klass, nctx, ctx, cat, nraw, r in contexts(recs, scheme):
            key = klass
            if key not in hists:
                hists[key] = np.zeros((nctx, NSYM), dtype=np.int64)
            np.add.at(hists[key], (ctx, np.minimum(cat, NSYM-1)), 1)
            if scheme == "fwd72" and "_scost" in r:
                d = np.diff(r["_scost"], prepend=0) + 8
                h = scost_hist.setdefault(klass, np.zeros(17, dtype=np.int64))
                np.add.at(h, np.clip(d, 0, 16), 1)
    return hists, scost_hist

def quantize_tables(hists):
    tabs = {}
    for k, h in hists.items():
        t = np.maximum(h, 0) + 1
        counts = np.maximum((t / t.sum(axis=1, keepdims=True) * 1024).round(), 1)
        p = counts / counts.sum(axis=1, keepdims=True)
        tabs[k] = -np.log2(p)
    return tabs

def score(clips, scheme, tabs, scost_tabs=None):
    bits = 0.0; raw = 0.0; nsym = 0; side = 0.0
    for c in clips:
        recs = load(c)
        for klass, nctx, ctx, cat, nraw, r in contexts(recs, scheme):
            t = tabs.get(klass)
            if t is None or t.shape[0] != nctx:
                t = np.full((nctx, NSYM), np.log2(NSYM))
            bits += t[ctx, np.minimum(cat, NSYM-1)].sum()
            raw += nraw.sum()
            nsym += len(cat)
            if scheme == "fwd72" and "_scost" in r and scost_tabs:
                st = scost_tabs.get(klass)
                d = np.clip(np.diff(r["_scost"], prepend=0) + 8, 0, 16)
                if st is not None:
                    side += st[d].sum()
                else:
                    side += 3.0 * len(d)
    return bits, raw, side, nsym

def sign_mant_study(train, test):
    """Raw-bit-side headroom: sign given neighbor signs; top mantissa bit."""
    def acc(clips):
        sh = {}; mh = {}
        for c in clips:
            for r in load(c):
                v = r["v"]; a = np.abs(v)
                klass = r["band"] * 2 + (1 if r["plane"] > 0 else 0)
                l, up = neigh(v)
                sgn = lambda x: np.where(x > 0, 2, np.where(x < 0, 0, 1))
                ctx = sgn(l) * 3 + sgn(up)
                neg = (v < 0).astype(np.int64)
                m = a > 0
                h = sh.setdefault(klass, np.zeros((9, 2), dtype=np.int64))
                np.add.at(h, (ctx[m], neg[m]), 1)
                cat = cat_of(a)
                m2 = cat >= 2
                if m2.sum():
                    bit = ((a[m2] >> (cat[m2] - 2)) & 1).astype(np.int64)
                    ctx2 = np.minimum(cat[m2], 15) * 4 + q2(np.abs(l)[m2])
                    h2 = mh.setdefault(klass, np.zeros((64, 2), dtype=np.int64))
                    np.add.at(h2, (ctx2, bit), 1)
        return sh, mh
    sh_t, mh_t = acc(train)
    def q(t):
        t = t + 1
        c = np.maximum((t / t.sum(axis=1, keepdims=True) * 64).round(), 1)
        p = c / c.sum(axis=1, keepdims=True)
        return -np.log2(p)
    stabs = {k: q(v) for k, v in sh_t.items()}
    mtabs = {k: q(v) for k, v in mh_t.items()}
    sbits = sraw = mbits = mraw = 0.0
    for c in test:
        for r in load(c):
            v = r["v"]; a = np.abs(v)
            klass = r["band"] * 2 + (1 if r["plane"] > 0 else 0)
            l, up = neigh(v)
            sgn = lambda x: np.where(x > 0, 2, np.where(x < 0, 0, 1))
            ctx = sgn(l) * 3 + sgn(up)
            neg = (v < 0).astype(np.int64)
            m = a > 0
            if klass in stabs and m.sum():
                sbits += stabs[klass][ctx[m], neg[m]].sum(); sraw += m.sum()
            cat = cat_of(a)
            m2 = cat >= 2
            if klass in mtabs and m2.sum():
                bit = ((a[m2] >> (cat[m2] - 2)) & 1).astype(np.int64)
                ctx2 = np.minimum(cat[m2], 15) * 4 + q2(np.abs(l)[m2])
                mbits += mtabs[klass][ctx2, bit].sum(); mraw += m2.sum()
    return sbits, sraw, mbits, mraw

def main():
    train = [c for c in TRAIN if os.path.exists(f"{W_}/dump2_{c}.bin")]
    test = [c for c in TEST if os.path.exists(f"{W_}/dump2_{c}.bin")]
    print(f"train={train} test={test}", flush=True)
    results = {}
    base_total = None
    for scheme in ["base4", "mag16", "mag64", "fwd72", "par16", "pred16", "mag64p"]:
        h, sh = accumulate(train, scheme)
        tabs = quantize_tables(h)
        stabs = {k: -np.log2(np.maximum((v+1)/ (v+1).sum() ,1e-9)) for k, v in sh.items()} if sh else None
        bits, raw, side, nsym = score(test, scheme, tabs, stabs)
        total = bits + raw + side
        if scheme == "base4":
            base_total = total
        results[scheme] = dict(cat_bits=bits, raw_bits=raw, side_bits=side,
                               total=total, vs_base=100*(1 - total/base_total))
        print(f"{scheme:7s} cat={bits/1e6:8.2f}Mb raw={raw/1e6:8.2f}Mb side={side/1e6:6.2f}Mb "
              f"total={total/1e6:8.2f}Mb  vs base4: {100*(1-total/base_total):+.2f}%", flush=True)
    sb, sr, mb, mr = sign_mant_study(train, test)
    print(f"sign9  : {sb/1e6:.2f}Mb for {sr/1e6:.2f}M signs -> saves {100*(1-sb/sr):+.2f}% of sign bits "
          f"= {(sr-sb)/1e6:.2f}Mb ({100*(sr-sb)/base_total:+.2f}% of base total)", flush=True)
    print(f"mantMSB: {mb/1e6:.2f}Mb for {mr/1e6:.2f}M bits -> saves {100*(1-mb/mr):+.2f}% "
          f"= {(mr-mb)/1e6:.2f}Mb ({100*(mr-mb)/base_total:+.2f}% of base total)", flush=True)
    json.dump({k: {kk: float(vv) for kk, vv in v.items()} for k, v in results.items()},
              open(f"{W_}/entropy_study.json", "w"), indent=1)

if __name__ == "__main__":
    main()
