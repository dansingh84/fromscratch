"""boundary-step excess on ONE frame (index f) of a seq.py decode: (step at slice boundary - step at half-slice) / other rows,
per plane; optionally restricted to the boundaries of given slices (refresh group).  usage: intrastep.py src dec W H sh f [k0 k1]"""
import sys, numpy as np
src, dec, W, H, sh, f = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6])
fs = W * H * 2; s = np.fromfile(src, dtype='<u2', count=fs, offset=f * fs * 2).astype(np.int64); d = np.fromfile(dec, dtype='<u2', count=fs, offset=f * fs * 2).astype(np.int64)
out = []
for pl, (o, w) in enumerate(((0, W), (W * H, W // 2), (W * H + W * H // 2, W // 2))):
    e = (d[o:o + w * H] - s[o:o + w * H]).reshape(H, w); dy = np.abs(np.diff(e, axis=0)); ys = np.arange(1, H)
    oth = dy[(ys % sh != 0) & (ys % sh != sh // 2)].mean()
    bmask = ys % sh == 0
    if len(sys.argv) > 8:
        k0, k1 = int(sys.argv[7]), int(sys.argv[8]); bmask = bmask & ((ys == k0 * sh) | (ys == (k1 + 1) * sh))
    out.append('%s %+.2f' % ('Y Cb Cr'.split()[pl], (dy[bmask].mean() - dy[ys % sh == sh // 2].mean()) / oth))
print(' '.join(out))
