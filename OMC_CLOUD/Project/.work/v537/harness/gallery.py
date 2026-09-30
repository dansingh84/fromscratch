"""Generate the Section-G inspection gallery.

For every sequence (worst frame = frame 0, full frame, full resolution):
  - <seq>_src.png            source master (converted back to RGB for viewing)
  - <seq>_omc.png            OMC-1 decoded output at the delivery rate
  - <seq>_omc_g1.png         G1 method: brightness-boosted + 32x32 grid overlay
  - <seq>_src_g1.png         same method applied to the source (for comparison)
plus synthetic gradient renders (G2 banding check, brightness-boosted).

Viewing conversion: BT.709 limited-range -> 8-bit RGB, chroma up-sampled
(4:2:2) with the co-sited linear filter. The codec itself never touches RGB.

Run: python3 harness/gallery.py [--fmt 422] [--bpp 2.0]
"""

import argparse
import json
import os
import subprocess

import numpy as np
from PIL import Image

from common import (MASTERS_DIR, SCRATCH, SEQUENCES, read_yuv, upsample_422,
                    write_yuv, ycbcr_to_rgb8)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAL = os.path.join(SCRATCH, "gallery")


def to_rgb(frame, fmt):
    Y, Cb, Cr = frame
    if fmt == "422":
        Cb, Cr = upsample_422(Cb), upsample_422(Cr)
    return ycbcr_to_rgb8(Y, Cb, Cr, bits=10)


def g1_method(rgb):
    """Brightness boost + 32x32 grid overlay (G1 identification method)."""
    boosted = np.clip(rgb.astype(np.int32) * 2 + 16, 0, 255).astype(np.uint8)
    out = boosted.copy()
    h, w = out.shape[:2]
    out[31::32, :, :] = np.clip(out[31::32, :, :].astype(int) + 70, 0, 255)
    out[:, 31::32, :] = np.clip(out[:, 31::32, :].astype(int) + 70, 0, 255)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fmt", default="422", choices=["422", "444"])
    ap.add_argument("--bpp", type=float, default=2.0)
    args = ap.parse_args()
    fmt = args.fmt
    os.makedirs(GAL, exist_ok=True)
    mani = json.load(open(os.path.join(MASTERS_DIR, "manifest.json")))

    for name in SEQUENCES:
        w, h = mani[name]["w"], mani[name]["h"]
        cw = w // 2 if fmt == "422" else w
        src = os.path.join(MASTERS_DIR, f"{name}_{fmt}_10.yuv")
        bs = os.path.join(GAL, "t.omc")
        dc = os.path.join(GAL, "t.yuv")
        subprocess.run([os.path.join(REPO, "omc_enc"), "-i", src, "-o", bs,
                        "-w", str(w), "-h", str(h), "--fmt", fmt,
                        "--bpp", str(args.bpp)], check=True, capture_output=True)
        subprocess.run([os.path.join(REPO, "omc_dec"), "-i", bs, "-o", dc],
                       check=True, capture_output=True)
        sfs = read_yuv(src, w, h, cw)
        dfs = read_yuv(dc, w, h, cw)
        srgb = to_rgb(sfs[0], fmt)
        drgb = to_rgb(dfs[0], fmt)
        Image.fromarray(srgb).save(os.path.join(GAL, f"{name}_{fmt}_src.png"))
        Image.fromarray(drgb).save(os.path.join(GAL, f"{name}_{fmt}_omc.png"))
        Image.fromarray(g1_method(drgb)).save(os.path.join(GAL, f"{name}_{fmt}_omc_g1.png"))
        Image.fromarray(g1_method(srgb)).save(os.path.join(GAL, f"{name}_{fmt}_src_g1.png"))
        # steady-state frame (rev.3: last available frame) for temporal review
        li = len(dfs) - 1
        if li >= 1:
            Image.fromarray(to_rgb(sfs[li], fmt)).save(
                os.path.join(GAL, f"{name}_{fmt}_src_f{li}.png"))
            drgb_l = to_rgb(dfs[li], fmt)
            Image.fromarray(drgb_l).save(os.path.join(GAL, f"{name}_{fmt}_omc_f{li}.png"))
            Image.fromarray(g1_method(drgb_l)).save(
                os.path.join(GAL, f"{name}_{fmt}_omc_f{li}_g1.png"))
        os.unlink(bs); os.unlink(dc)
        print(name, "done", flush=True)

    # G2: synthetic smooth gradients (subtle 10-bit ramps), rendered boosted
    w, hh = 1920, 512
    x = np.linspace(0, 1, w)
    y = np.linspace(0, 1, hh)[:, None]
    Y = (256 + 300 * (0.6 * x[None, :] + 0.4 * y)).astype(np.uint16)
    Cb = (512 + 60 * x[None, :] * np.ones((hh, 1))).astype(np.uint16)
    Cr = (512 - 40 * y * np.ones((1, w))).astype(np.uint16)
    if fmt == "422":
        frame = (Y, Cb[:, ::2].copy(), Cr[:, ::2].copy())
    else:
        frame = (Y, Cb, Cr)
    p = os.path.join(GAL, "grad.yuv")
    write_yuv(p, [frame])
    bs = os.path.join(GAL, "grad.omc")
    dc = os.path.join(GAL, "grad_dec.yuv")
    subprocess.run([os.path.join(REPO, "omc_enc"), "-i", p, "-o", bs, "-w", str(w),
                    "-h", str(hh), "--fmt", fmt, "--bpp", str(args.bpp)],
                   check=True, capture_output=True)
    subprocess.run([os.path.join(REPO, "omc_dec"), "-i", bs, "-o", dc],
                   check=True, capture_output=True)
    gsrc = read_yuv(p, w, hh, w // 2 if fmt == "422" else w, nframes=1)[0]
    gdec = read_yuv(dc, w, hh, w // 2 if fmt == "422" else w, nframes=1)[0]
    for tag, fr in (("src", gsrc), ("omc", gdec)):
        rgb = to_rgb(fr, fmt)
        boosted = np.clip(rgb.astype(np.int32) * 3 - 200, 0, 255).astype(np.uint8)
        Image.fromarray(rgb).save(os.path.join(GAL, f"gradient_{fmt}_{tag}.png"))
        Image.fromarray(boosted).save(os.path.join(GAL, f"gradient_{fmt}_{tag}_boost.png"))
    for f in (p, bs, dc):
        os.unlink(f)
    print("gradient done")


if __name__ == "__main__":
    main()
