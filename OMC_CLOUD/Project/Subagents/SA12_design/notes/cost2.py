"""Item 3: real-coder rate model.  Normative static table FAMILY: 64 tables per band = P(0) in 8 values x geometric
decay r in 8 values for |q| >= 1 (sign 1 bit), |q| > 14 escape + Exp-Golomb.  Encoder picks the cheapest table per
(frame, plane, band, intra/inter) [coarser than the design's per-slice choice -> conservative] and pays 6 bits per band
per SLICE.  No contexts (conservative).  Plus packet overhead per slice: 8 B header + 4 lanes x 2 B flush.
Ideal-code-length (tANS within ~0.1-0.5 % of it with 2^11-state tables).  usage: cost2.py hist.pkl W H nslices"""
import sys, pickle, math, numpy as np
H_ = pickle.load(open(sys.argv[1], 'rb')); W, H, ns = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
Z = [0.2, 0.4, 0.55, 0.7, 0.8, 0.88, 0.94, 0.98]; Rr = [0.1, 0.25, 0.4, 0.55, 0.68, 0.78, 0.86, 0.93]
def eg(n): return 2 * int(math.floor(math.log2(n + 1))) + 1
tables = []
for z in Z:
    for r in Rr:
        m = np.arange(1, 15); pm = (1 - z) * (1 - r) * r ** (m - 1); pesc = (1 - z) * r ** 14
        tables.append((z, pm, pesc))
out = []
for fr in H_:
    bits = ent = 0.0; nb = 0
    for k, (v, c) in fr.items():
        a = np.abs(v).astype(np.int64); best = None
        for z, pm, pesc in tables:
            b = 0.0
            for aa, cc in zip(a, c):
                if aa == 0: b += cc * -math.log2(z)
                elif aa <= 14: b += cc * (-math.log2(pm[aa - 1]) + 1)
                else: b += cc * (-math.log2(pesc) + eg(aa - 15) + 1)
            best = b if best is None or b < best else best
        bits += best; nb += 1
        n = c.sum(); ent += float(-(c * np.log2(c / n)).sum())
    side = ns * (16 * 8 + 6 * 36)   # per slice: header+flush 128 bits, table index 6 bits x 12 bands x 3 planes
    out.append((ent / (W * H), bits / (W * H), (bits + side) / (W * H)))
e = np.array(out)
print('%s f2+: entropy %.4f | table-family (mismatch only) %.4f (x%.3f) | + headers & table indices %.4f (x%.3f) bpp' % (sys.argv[1], e[2:, 0].mean(), e[2:, 1].mean(), e[2:, 1].mean() / e[2:, 0].mean(), e[2:, 2].mean(), e[2:, 2].mean() / e[2:, 0].mean()))
