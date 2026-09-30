"""OMC-UC inspection gallery — regenerates every picture the delivery document
cites, from files inside this tree only.

Run:  python3 harness/uc_gallery.py [outdir]      (default: work/uc_gallery)

Produced (all PNG, all at FULL RESOLUTION of the upconverted output; the
constraints require full-frame, full-resolution review, so the frame panels are
never cropped or downscaled):

  full_<clip>_UC2x.png        real footage upconverted 2x by the shipped decoder
  full_<clip>_LANCZOS4.png    the same source through a linear lanczos-4 scaler
  full_<clip>_SRC_nn.png      the source at 2x nearest-neighbour, for reference
  edge_zoom.png               a hard 26.57-degree edge: NN | separable | OMC-UC | truth
  zoneplate_corner.png        near-Nyquist corner: with / without the monotonicity
                              gate, separable spine, and a linear reference
  zoneplate_full.png          the whole band-limited zone plate, four ways
"""
import os
import subprocess
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "harness"))
from uc_verify import (DEC, VEC, W, H, LO, HI, read_frames, ref_down2, ref_up2,
                       render, uc_up)

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "work", "uc_gallery")
os.makedirs(OUT, exist_ok=True)
TMP = "/tmp/omc_uc_gallery"
os.makedirs(TMP, exist_ok=True)


# ---------------------------------------------------------------- colour
def ycbcr_to_rgb8(Y, Cb, Cr, bits=10):
    d = 1 << (bits - 8)
    y = (np.asarray(Y, float) - 16 * d) / (219 * d)
    cb = (np.asarray(Cb, float) - 128 * d) / (224 * d)
    cr = (np.asarray(Cr, float) - 128 * d) / (224 * d)
    r = y + 1.5748 * cr
    b = y + 1.8556 * cb
    g = (y - 0.2126 * r - 0.0722 * b) / 0.7152
    return np.clip(np.round(np.stack([r, g, b], -1) * 255.0), 0, 255).astype(np.uint8)


def up422(C):
    h, w2 = C.shape
    out = np.zeros((h, w2 * 2), np.int64)
    out[:, ::2] = C
    nxt = np.concatenate([C[:, 1:], C[:, -1:]], axis=1)
    out[:, 1::2] = (C + nxt + 1) >> 1
    return out


def frame_panels():
    for clip, vec in (("beach", "c7_static_fill"), ("alpine", "c4_blockmv")):
        raw = os.path.join(TMP, vec + ".yuv")
        subprocess.run([DEC, "-i", os.path.join(VEC, vec + ".omc"), "-o", raw],
                       check=True, capture_output=True)
        fr = read_frames(raw, W, H, 224)[5]
        up = uc_up([fr], W, H, "422", 10)[0]
        Image.fromarray(ycbcr_to_rgb8(up[0], up422(up[1]), up422(up[2]))).save(
            os.path.join(OUT, f"full_{clip}_UC2x.png"))
        l4 = [np.clip(np.round(ref_up2(p.astype(float), "lanczos4")), 0, 1023) for p in fr]
        Image.fromarray(ycbcr_to_rgb8(l4[0], up422(l4[1].astype(np.int64)),
                                      up422(l4[2].astype(np.int64)))).save(
            os.path.join(OUT, f"full_{clip}_LANCZOS4.png"))
        nn = [np.repeat(np.repeat(p, 2, 0), 2, 1) for p in fr]
        Image.fromarray(ycbcr_to_rgb8(nn[0], up422(nn[1]), up422(nn[2]))).save(
            os.path.join(OUT, f"full_{clip}_SRC_nn.png"))
        print("frame panels:", clip)


def edge_zoom(theta=26.57, w=192, h=192):
    t = np.radians(theta)
    nx, ny = np.cos(t), np.sin(t)
    cx, cy = w / 2.0, h / 2.0
    X, Y = np.meshgrid(np.arange(w) + 0.5, np.arange(h) + 0.5)
    src = np.where(((X - cx) * nx + (Y - cy) * ny) > 0, HI, LO).astype(np.int64)
    truth = render(lambda X, Y: (((X - cx) * nx + (Y - cy) * ny) > 0).astype(float),
                   w, h, 2, LO, HI)
    def up(direction):
        return uc_up([(src, src[:, ::2].copy(), src[:, ::2].copy())], w, h, "422", 10,
                     direction=direction)[0][0]
    panels = [np.repeat(np.repeat(src, 2, 0), 2, 1), up(False), up(True), truth]
    strips = []
    for p in panels:
        row = np.asarray(p[2 * 100], float)
        c0 = int(np.argmax(row > (LO + HI) / 2)) - 20
        strips.append(np.clip((np.asarray(p, float)[192:216, c0:c0 + 44] - LO)
                              / (HI - LO) * 255, 0, 255).astype(np.uint8))
    gap = np.full((24, 3), 128, np.uint8)
    s = np.concatenate(sum([[x, gap] for x in strips], [])[:-1], axis=1)
    Image.fromarray(np.repeat(np.repeat(s, 10, 0), 10, 1)).save(
        os.path.join(OUT, "edge_zoom.png"))
    print("edge_zoom.png: nearest | separable spine | OMC-UC | analytic truth")


def zoneplate(w=256):
    cx = cy = w / 2.0
    rmax = np.hypot(cx, cy)
    def f(X, Y):
        r2 = (X - cx) ** 2 + (Y - cy) ** 2
        return 0.5 + 0.5 * np.cos(2 * np.pi * (np.pi * 0.45 * r2 / rmax) / np.pi * 0.5)
    truth = render(f, w, w, 2, LO, HI)
    src = np.clip(np.round(ref_down2(truth)), 0, 1023).astype(np.int64)
    full = uc_up([(src, src[:, ::2].copy(), src[:, ::2].copy())], w, w, "422", 10)[0][0]
    sep = uc_up([(src, src[:, ::2].copy(), src[:, ::2].copy())], w, w, "422", 10,
                direction=False)[0][0]
    lin = np.clip(np.round(ref_up2(src.astype(float), "lanczos4")), 0, 1023)
    n8 = lambda x: np.clip((np.asarray(x, float) - LO) / (HI - LO) * 255, 0, 255).astype(np.uint8)
    gap = np.full((2 * w, 4), 128, np.uint8)
    Image.fromarray(np.concatenate([n8(full), gap, n8(sep), gap, n8(lin), gap,
                                    n8(truth)], axis=1)).save(
        os.path.join(OUT, "zoneplate_full.png"))
    g2 = np.full((128, 3), 128, np.uint8)
    corner = [n8(x)[0:128, 0:128] for x in (full, sep, lin)]
    Image.fromarray(np.repeat(np.repeat(
        np.concatenate(sum([[c, g2] for c in corner], [])[:-1], axis=1), 3, 0), 3, 1)).save(
        os.path.join(OUT, "zoneplate_corner.png"))
    print("zoneplate_full.png: OMC-UC | separable spine | lanczos4 | truth")
    print("zoneplate_corner.png: the near-Nyquist corner at 3x, same order")


if __name__ == "__main__":
    frame_panels()
    edge_zoom()
    zoneplate()
    print("\ngallery written to", OUT)
