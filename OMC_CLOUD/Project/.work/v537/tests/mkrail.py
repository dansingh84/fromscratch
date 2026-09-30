#!/usr/bin/env python3
"""mkrail.py - deterministic rail-heavy synthetic master for the gamut arm of
the baseband matrix.

Content chosen to put committed reconstruction samples OUTSIDE legal range:
hard-clipped white and black plates with sharp edges placed across slice
boundaries (quantization ringing overshoots at the rails), a full-range
horizontal ramp touching 0 and maxv, saturated graphics bars (chroma at the
rails), all drifting 2 px/frame so inter frames exercise the temporal path.

Usage: mkrail.py out.yuv [W H depth frames]   (defaults 1280 720 10 3)
Output: planar Y|Cb|Cr 4:2:2 u16 LE, [0, 2^depth).
Fully deterministic (no RNG).
"""
import sys
import numpy as np

def main():
    out = sys.argv[1]
    W = int(sys.argv[2]) if len(sys.argv) > 2 else 1280
    H = int(sys.argv[3]) if len(sys.argv) > 3 else 720
    depth = int(sys.argv[4]) if len(sys.argv) > 4 else 10
    nf = int(sys.argv[5]) if len(sys.argv) > 5 else 3
    maxv = (1 << depth) - 1
    mid = 1 << (depth - 1)
    with open(out, "wb") as fo:
        for f in range(nf):
            s = 2 * f  # 2 px/frame drift
            y = np.full((H, W), mid, np.int32)
            cb = np.full((H, W), mid, np.int32)
            cr = np.full((H, W), mid, np.int32)
            # full-range horizontal ramp band (touches 0 and maxv)
            y[0:96, :] = (np.arange(W) * maxv // (W - 1))[None, :]
            # hard white plate with sharp edges crossing slice rows 16k
            y[100 + s:250 + s, 200 + s:600 + s] = maxv
            # hard black plate
            y[260 + s:400 + s, 640 + s:1040 + s] = 0
            # saturated graphics bars: chroma at the rails, sharp verticals
            for i, (cbv, crv) in enumerate([(0, maxv), (maxv, 0), (0, 0), (maxv, maxv)]):
                x0 = 80 + 280 * i + s
                y[420 + s:560 + s, x0:x0 + 220] = maxv if i % 2 else 0
                cb[420 + s:560 + s, x0:x0 + 220] = cbv
                cr[420 + s:560 + s, x0:x0 + 220] = crv
            # thin white/black line pair ON a slice boundary (rows 575/576)
            y[575, :] = maxv
            y[576, :] = 0
            # checker of near-rail values (ringing bait)
            yy, xx = np.mgrid[600:704, 0:W]
            y[600:704, :] = np.where((yy + xx + s) % 2 == 0, maxv - 1, 1)
            cbh = ((cb[:, 0::2] + cb[:, 1::2] + 1) // 2)
            crh = ((cr[:, 0::2] + cr[:, 1::2] + 1) // 2)
            fo.write(y.astype("<u2").tobytes())
            fo.write(cbh.astype("<u2").tobytes())
            fo.write(crh.astype("<u2").tobytes())
    print(f"{out}: {nf} frames {W}x{H} 422/{depth}-bit rail-heavy")

if __name__ == "__main__":
    main()
