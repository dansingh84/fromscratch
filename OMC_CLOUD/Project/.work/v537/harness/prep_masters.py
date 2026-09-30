"""Prepare test masters from the uploaded ProRes-master PNGs.

For every sequence:
  - crop to a multiple of 32 in both dimensions (per corpus README),
  - convert once to BT.709 limited-range 10-bit Y'CbCr,
  - emit 4:4:4 and 4:2:2 planar raws (.yuv, LE16) and .y4m (for vmaf),
  - record a manifest (masters/manifest.json).

Run:  python3 harness/prep_masters.py
"""

import glob
import json
import os

import numpy as np
from PIL import Image

from common import (FOOTAGE_DIR, MASTERS_DIR, SEQUENCES, downsample_422,
                    rgb8_to_ycbcr, write_y4m, write_yuv)


def main():
    os.makedirs(MASTERS_DIR, exist_ok=True)
    manifest = {}
    for name, rel in SEQUENCES.items():
        files = sorted(glob.glob(os.path.join(FOOTAGE_DIR, rel, "f_*.png")))
        assert files, f"no frames for {name}"
        frames444, frames422 = [], []
        w = h = None
        for fp in files:
            rgb = np.asarray(Image.open(fp).convert("RGB"))
            H, W = rgb.shape[:2]
            H32, W32 = H // 32 * 32, W // 32 * 32
            rgb = rgb[:H32, :W32]
            h, w = H32, W32
            Y, Cb, Cr = rgb8_to_ycbcr(rgb, bits=10)
            frames444.append((Y, Cb, Cr))
            frames422.append((Y, downsample_422(Cb), downsample_422(Cr)))
        base = os.path.join(MASTERS_DIR, name)
        write_yuv(base + "_444_10.yuv", frames444)
        write_yuv(base + "_422_10.yuv", frames422)
        write_y4m(base + "_444_10.y4m", frames444, fmt="444", bits=10)
        write_y4m(base + "_422_10.y4m", frames422, fmt="422", bits=10)
        manifest[name] = {"w": w, "h": h, "frames": len(files), "bits": 10}
        print(f"{name}: {w}x{h} x{len(files)} frames")
    with open(os.path.join(MASTERS_DIR, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)


if __name__ == "__main__":
    main()
