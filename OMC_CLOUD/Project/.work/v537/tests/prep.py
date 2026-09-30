#!/usr/bin/env python3
"""prep.py - convert the provided PNG footage into raw planar u16 LE masters
for the OMC codec.

Usage:
  prep.py --out out.yuv --fmt 444|422 --depth 8|10|12 frame0.png [frame1.png ...]

4:4:4: planes are R, G, B taken directly from the PNG (the codec carries
colour transparently; no matrix loss enters the chain).
4:2:2: BT.709 limited-range Y'CbCr; chroma decimated horizontally by
averaging pairs (deterministic; outside the codec).

Depth conversion from the PNG's native depth (8 or 16 bits) is by bit shift
(deterministic, no rounding surprises): 16-bit source >> (16-depth);
8-bit source << (depth-8).

Output: for each frame, planes concatenated (Y|Cb|Cr or R|G|B), u16 LE,
values in [0, 2^depth).
"""
import argparse
import sys
import numpy as np
from PIL import Image

def load_rgb(path):
    im = Image.open(path)
    arr = np.array(im)
    if arr.ndim != 3 or arr.shape[2] < 3:
        sys.exit(f"{path}: not RGB")
    native = 16 if arr.dtype == np.uint16 else 8
    return arr[:, :, :3].astype(np.int64), native

def to_depth(a, native, depth):
    if native > depth:
        return a >> (native - depth)
    return a << (depth - native)

def rgb_to_ycbcr422(rgb, depth):
    # BT.709 limited range, integer-friendly but done in float64 then rounded:
    # deterministic across runs/platforms for these value ranges.
    maxv = (1 << depth) - 1
    r = rgb[:, :, 0].astype(np.float64)
    g = rgb[:, :, 1].astype(np.float64)
    b = rgb[:, :, 2].astype(np.float64)
    sc = maxv / ((1 << depth) - 1)  # 1.0; kept for clarity
    kr, kb = 0.2126, 0.0722
    y = kr * r + (1 - kr - kb) * g + kb * b
    cb = (b - y) / (2 * (1 - kb))
    cr = (r - y) / (2 * (1 - kr))
    d8 = depth - 8
    ys = np.clip(np.round(y / maxv * (219 << d8) + (16 << d8)), 0, maxv)
    cbs = np.clip(np.round(cb / maxv * (224 << d8) + (128 << d8)), 0, maxv)
    crs = np.clip(np.round(cr / maxv * (224 << d8) + (128 << d8)), 0, maxv)
    # 4:2:2: average horizontal pairs
    cbh = ((cbs[:, 0::2] + cbs[:, 1::2] + 1) // 2)
    crh = ((crs[:, 0::2] + crs[:, 1::2] + 1) // 2)
    return ys.astype(np.uint16), cbh.astype(np.uint16), crh.astype(np.uint16)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--fmt", required=True, choices=["444", "422"])
    ap.add_argument("--depth", required=True, type=int, choices=[8, 10, 12])
    ap.add_argument("--resize", default=None,
                    help="WxH: Lanczos-resize the PNG before conversion "
                         "(e.g. 1280x720 to derive 720p masters)")
    ap.add_argument("pngs", nargs="+")
    args = ap.parse_args()

    rsz = None
    if args.resize:
        w, h = args.resize.split("x")
        rsz = (int(w), int(h))

    with open(args.out, "wb") as fo:
        for path in args.pngs:
            if rsz:
                im = Image.open(path)
                im = im.resize(rsz, Image.LANCZOS)
                arr = np.array(im)
                native = 16 if arr.dtype == np.uint16 else 8
                rgb = arr[:, :, :3].astype(np.int64)
            else:
                rgb, native = load_rgb(path)
            rgb = to_depth(rgb, native, args.depth)
            if args.fmt == "444":
                for c in range(3):
                    fo.write(rgb[:, :, c].astype("<u2").tobytes())
            else:
                y, cb, cr = rgb_to_ycbcr422(rgb, args.depth)
                fo.write(y.astype("<u2").tobytes())
                fo.write(cb.astype("<u2").tobytes())
                fo.write(cr.astype("<u2").tobytes())
    h, w = rgb.shape[0], rgb.shape[1]
    print(f"{args.out}: {len(args.pngs)} frames {w}x{h} fmt={args.fmt} depth={args.depth}")

if __name__ == "__main__":
    main()
