#!/usr/bin/env python3
"""chromaview.py SRC.yuv W H FRAME OUT.png [--fmt][--depth][--gain 3.0]

THE CHROMA-ONLY VIEW.

Needed because the per-plane deadzone candidate (OMC_DZ_PLANE=1) puts ALL of
its gain in chroma -- +27% Cb and +17% Cr true detail -- and an ordinary render
is luma-dominated.  A viewer comparing two ordinary renders can easily see "no
difference" and be wrong, which is the worst possible outcome for a decision
made by eye.

So: luma is REPLACED by a flat mid-grey, the chroma is amplified about its
neutral point by `gain`, and the result is converted to RGB.  What remains on
screen is the colour signal and nothing else.  Amplifying is honest here
precisely because nothing is being ranked on amplitude -- the question is
whether the colour DETAIL survives, and it has to be visible to be judged.
"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yuvio
from PIL import Image

a = sys.argv
src, W, H, F, out = a[1], int(a[2]), int(a[3]), int(a[4]), a[5]
fmt   = a[a.index('--fmt')+1]        if '--fmt'   in a else '422'
depth = int(a[a.index('--depth')+1]) if '--depth' in a else 10
gain  = float(a[a.index('--gain')+1]) if '--gain' in a else 3.0

y, cb, cr = yuvio.planes(src, W, H, F, fmt, depth)
mid = 1 << (depth - 1)
cbf = yuvio.upchroma(cb, W, fmt); crf = yuvio.upchroma(cr, W, fmt)
u = (cbf - mid) * gain
v = (crf - mid) * gain
flat = np.full_like(y, float(mid))          # luma removed
r = flat + 1.5748 * v
g = flat - 0.1873 * u - 0.4681 * v
b = flat + 1.8556 * u
img = np.stack([r, g, b], -1) / float((1 << depth) - 1)
img = np.clip(img, 0, 1) ** (1 / 2.2)
Image.fromarray((img * 255).astype(np.uint8)).save(out)
print("%s: chroma-only, luma removed, chroma x%.1f" % (out, gain))
