#!/usr/bin/env python3
"""[SA1-I6] LEVEL MAP render: decode level map minus source level map, computed
EXACTLY as Subagents/shared_tools/smudgegroups.py computes it -- block mean of
(decode - source) over blocks of (slice_h/4) rows x 32 columns -- rendered
signed, red = decode above source, blue = decode below, full scale +-20 codes,
upsampled 1:1 so one output pixel is one source pixel.  Nothing algorithmic is
drawn: no boxes, no thresholds, no group outlines.  Per plane.
usage: i6_levelmap.py SRC DEC W H FMT DEPTH FRAME OUTPREFIX [--sh 16]"""
import sys, numpy as np
from PIL import Image
a = sys.argv[1:]
sh = 16
if '--sh' in a:
    i = a.index('--sh'); sh = int(a[i+1]); del a[i:i+2]
src, dec, W, H, fmt, dep, f, outp = a[0], a[1], int(a[2]), int(a[3]), a[4], int(a[5]), int(a[6]), a[7]
Wc = W if fmt == '444' else W // 2
fw = W*H + 2*Wc*H
def planes(p):
    d = np.fromfile(p, dtype=np.uint16)[f*fw:(f+1)*fw].astype(np.float64)
    if d.size < fw: sys.exit("frame %d not present in %s" % (f, p))
    return d[:W*H].reshape(H, W), d[W*H:W*H+Wc*H].reshape(H, Wc), d[W*H+Wc*H:].reshape(H, Wc)
S = planes(src); D = planes(dec)
bh, bw = sh//4, 32
FS = 20.0
print("LEVELMAP %s frame %d  block %dx%d  full scale +-%g codes  (red = decode ABOVE source)"
      % (outp, f, bh, bw, FS))
for pi, name in enumerate(("Y", "Cb", "Cr")):
    s = S[pi]; d = D[pi]; hh, ww = s.shape
    nh, nw = hh//bh, ww//bw
    e = (d-s)[:nh*bh, :nw*bw].reshape(nh, bh, nw, bw).mean(axis=(1, 3))
    big = np.repeat(np.repeat(e, bh, 0), bw, 1)
    im = np.zeros((nh*bh, nw*bw, 3), np.uint8)
    im[..., 0] = (np.clip(big/FS, 0, 1)*255).astype(np.uint8)
    im[..., 2] = (np.clip(-big/FS, 0, 1)*255).astype(np.uint8)
    Image.fromarray(im).save("%s_%s.png" % (outp, name))
    err = (d-s)
    print("  %-3s blocks %dx%d  blockmean min %+.1f max %+.1f  |blockmean|>20: %.3f%%   "
          "per-sample: mean %+.3f sd %.3f min %+d max %+d |e|>16 %.2f%%"
          % (name, nh, nw, e.min(), e.max(), 100.0*(np.abs(e) > FS).mean(),
             err.mean(), err.std(), int(err.min()), int(err.max()),
             100.0*(np.abs(err) > 16).mean()))
