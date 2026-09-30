"""Item 3 (fairness): cost of a seq.py run under STATIC tables trained on a DIFFERENT sequence, instead of the
per-frame adaptive zeroth-order entropy.  Alphabet: |q| <= 14 plus ESC; escapes = ESC + Exp-Golomb(|q|-15, k=0) +
sign; add-1/2 smoothing; one table per (plane class Y/C, intra/inter, band).  No contexts (conservative: the design's
8 neighbour/parent contexts would lower it).  Plus packet overhead per slice: header 8 B + 4 tANS lane flushes x 2 B.
usage: cost.py train.hist.pkl test.hist.pkl W H nslices"""
import sys, pickle, math, numpy as np, ast
tr, te = pickle.load(open(sys.argv[1], 'rb')), pickle.load(open(sys.argv[2], 'rb'))
W, H, ns = int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
def cls(k):
    pi, intra, rows, band = ast.literal_eval(k); return (pi > 0, intra, band)
def eg(n): return 2 * int(math.floor(math.log2(n + 1))) + 1
tab = {}
for fr in tr:
    for k, (v, c) in fr.items():
        t = tab.setdefault(cls(k), np.zeros(30))
        for vv, cc in zip(v, c): t[29 if abs(vv) > 14 else int(vv) + 14] += cc
out = []
for fr in te:
    bits = 0.0; ent = 0.0
    for k, (v, c) in fr.items():
        t = tab.get(cls(k), np.zeros(30)) + 0.5; p = t / t.sum()
        for vv, cc in zip(v, c):
            if abs(vv) > 14: bits += cc * (-math.log2(p[29]) + eg(abs(int(vv)) - 15) + 1)
            else: bits += cc * -math.log2(p[int(vv) + 14])
        n = c.sum(); ent += float(-(c * np.log2(c / n)).sum())
    bits += ns * 16 * 8
    out.append((ent / (W * H), bits / (W * H)))
e = np.array(out)
print('frames 2+: adaptive-entropy bpp %.4f | static-table + overhead bpp %.4f | ratio %.3f' % (e[2:, 0].mean(), e[2:, 1].mean(), e[2:, 1].mean() / e[2:, 0].mean()))
print('per frame (entropy->static):', ' '.join('%.3f->%.3f' % tuple(x) for x in out))
