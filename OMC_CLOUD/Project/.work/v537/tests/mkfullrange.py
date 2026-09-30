#!/usr/bin/env python3
"""Make a FULL-RANGE master from a limited-range one.

The baseband hand-off is exact only while the committed picture stays inside
the container's legal range, so the exposed content class is material that is
mastered hard to the container rails rather than to broadcast legal range.
The project's own cinema masters are limited-range (they leave ~60 codes of
headroom below black and ~83 above white at 10 bit), which is exactly why they
show no out-of-gamut samples.  This tool converts one of them into the other
class WITHOUT inventing content: it applies the standard limited->full range
expansion (the same transform a grade-to-full-range does), per plane, with
saturation.  The result is ordinary camera footage that touches 0 and maxv.

  mkfullrange.py <in.yuv> <out.yuv> <W> <H> <422|444> <depth> [anchors|auto]

`anchors` (the default) applies the nominal limited->full expansion.  `auto`
normalises the clip's OWN measured luma extremes to 0 and maxv, which is what a
colourist does when grading to full range, and is the mode that actually puts
content on the rails: a master whose luma never reaches the nominal anchors
(most do not) comes out of `anchors` still short of them.

Planar YUV, little-endian 16-bit words, one plane after another, as every
other master in tests/raw.
"""
import sys, numpy as np

src, dst, W, H, fmt, depth = (sys.argv[1], sys.argv[2], int(sys.argv[3]),
                              int(sys.argv[4]), sys.argv[5], int(sys.argv[6]))
mode = sys.argv[7] if len(sys.argv) > 7 else 'anchors'
Wc = W if fmt == '444' else W // 2
maxv = (1 << depth) - 1
# ITU-R BT.601/709 limited-range anchors, scaled to the coded depth
sc = 1 << (depth - 8)
y_lo, y_hi = 16 * sc, 235 * sc
c_lo, c_hi = 16 * sc, 240 * sc

a = np.fromfile(src, dtype='<u2')
fw = W * H + 2 * Wc * H
if mode == 'auto':
    b = a.reshape(-1, fw)
    y_lo, y_hi = int(b[:, :W * H].min()), int(b[:, :W * H].max())
    cs = b[:, W * H:]
    c_lo, c_hi = int(cs.min()), int(cs.max())
    print("auto: luma [%d..%d] chroma [%d..%d] -> [0..%d]" %
          (y_lo, y_hi, c_lo, c_hi, maxv))
assert a.size % fw == 0, "file is not a whole number of frames"
a = a.reshape(-1, fw)
out = np.empty_like(a)
for f in range(a.shape[0]):
    fr = a[f]
    y = fr[:W * H].astype(np.float64)
    y = (y - y_lo) * (maxv / (y_hi - y_lo))
    out[f, :W * H] = np.clip(np.rint(y), 0, maxv).astype('<u2')
    off = W * H
    for _ in range(2):
        c = fr[off:off + Wc * H].astype(np.float64)
        c = (c - (c_lo + c_hi) / 2.0) * (maxv / (c_hi - c_lo)) + (maxv + 1) / 2.0
        out[f, off:off + Wc * H] = np.clip(np.rint(c), 0, maxv).astype('<u2')
        off += Wc * H
out.tofile(dst)
print("wrote %s: %d frames %dx%d %s/%d-bit, full range" %
      (dst, a.shape[0], W, H, fmt, depth))
