"""Entropy-floor study (achievability bound for the memo response).

Question: at the quality JPEG XS delivers at 4.0 bpp on the hardest frame
(cow f0: Y 58.8 / Cb 59.4 / Cr 60.2 dB), how many bits would an IDEAL entropy
coder need — zero coding redundancy, strong 2D conditional context model —
for the quantized wavelet representation of that quality?

Method: sweep a continuous quantizer-step scale over the codec's band ladder,
quantize the full frame's slice-transform coefficients, and for each point
compute (a) reconstruction PSNR per plane and (b) a conditional-entropy
estimate: per band, magnitude-category symbols conditioned on the categories
of the left and above neighbours (capped at 3), plus (cat-1) magnitude LSBs
and 1 sign bit per significant coefficient (near-uniform at these rates),
LL coded as row-DPCM. This is a *generous* model — better than the shipping
codec's — so the resulting rate is a floor estimate for transform coding of
this class, not a property of any implementation.

Run: python3 harness/entropy_floor.py
"""

import json

import numpy as np

from common import MASTERS_DIR, read_yuv
from proto import slice_fwd2, slice_inv2

# band ladder (relative step weights ~ the codec's balanced allocation)
BAND_W = {0: 0.25, 1: 0.5, 2: 0.5, 3: 1.0, 4: 2.0, 5: 2.0, 6: 4.0, 7: 4.0, 8: 4.0, 9: 8.0}


def quant_round(c, step):
    return np.sign(c) * ((np.abs(c) + step // 2) // step)


def cats_of(v):
    a = np.abs(v).astype(np.int64)
    cat = np.zeros(a.shape, dtype=np.int64)
    nz = a > 0
    cat[nz] = np.floor(np.log2(a[nz])).astype(np.int64) + 1
    return cat


def cond_entropy_bits(v, dpcm_w=None):
    """Conditional entropy of cat symbols given (left,above) cats + raw bits."""
    if dpcm_w is not None:
        v = np.diff(v, axis=-1, prepend=0)
    cat = cats_of(v)
    C = np.minimum(cat, 3)
    left = np.zeros_like(C); left[:, 1:] = C[:, :-1]
    above = np.zeros_like(C); above[1:, :] = C[:-1, :]
    ctx = left * 4 + above
    total = 0.0
    for cx in range(16):
        m = ctx == cx
        n = int(m.sum())
        if n == 0:
            continue
        hist = np.bincount(cat[m], minlength=20).astype(np.float64)
        p = hist[hist > 0] / n
        total += -(p * np.log2(p)).sum() * n
    raw = int(cat.sum())  # (cat-1) LSBs + 1 sign per nonzero
    return total + raw


def frame_point(fr, scale, sh=16):
    planes = []
    tot_bits = 0.0
    for p, plane in enumerate(fr):
        h, w = plane.shape
        rec = np.zeros_like(plane, dtype=np.int32)
        for y0 in range(0, h, sh):
            tile = plane[y0:y0 + sh].astype(np.int32) - 512
            bands = slice_fwd2(tile)
            rb = {}
            for b in range(10):
                step = max(1, int(round(BAND_W[b] * scale)))
                q = quant_round(bands[b].astype(np.int64), step)
                tot_bits += cond_entropy_bits(q, dpcm_w=True if b == 0 else None)
                rb[b] = (q * step).astype(np.int32)
            rec[y0:y0 + sh] = slice_inv2(rb)
        out = np.clip(rec + 512, 0, 1023).astype(np.uint16)
        planes.append(out)
    return planes, tot_bits


def main():
    w, h = 4480, 3072
    fr = read_yuv(f"{MASTERS_DIR}/cow_422_10.yuv", w, h, w // 2, nframes=1)[0]
    npix = w * h
    out = []
    for scale in (1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0):
        planes, bits = frame_point(fr, scale)
        def psnr(a, b):
            mse = np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2)
            return 10 * np.log10(1023 * 1023 / mse) if mse else 99.0
        p = [psnr(fr[i], planes[i]) for i in range(3)]
        bpp = bits / npix
        out.append(dict(scale=scale, bpp=bpp, Y=p[0], Cb=p[1], Cr=p[2]))
        print(f"scale {scale:4.1f}: ideal-coder rate {bpp:.3f} bpp  "
              f"PSNR {p[0]:.2f}/{p[1]:.2f}/{p[2]:.2f}", flush=True)
    json.dump(out, open(f"{MASTERS_DIR}/entropy_floor_cow.json", "w"), indent=1)


if __name__ == "__main__":
    main()
