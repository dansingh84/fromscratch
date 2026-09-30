"""Build the temporal-filter test corpus from the supplied cine footage.

INPUT (the second zip supplied with this project):
    cine_A005C021_frame000.png, cine_A005C021_frame001.png
    2048x1152 8-bit RGB, two CONSECUTIVE frames of graded (non-raw) cine
    footage: beach at sunset, hand-held with a ~2 px/frame horizontal drift,
    independent pedestrian motion, non-rigid surf, and a large smooth sky.

Point the loader at the unpacked folder with OMC_CINE_DIR (default:
work/cine relative to the repository root).

OUTPUT (masters written to work/tf/):
    Every sequence is BT.709 limited-range 10-bit 4:2:2 planar LE16, the
    codec's broadcast-native format (B1/B2).  Sequences are chosen to span
    the whole motion range a temporal filter has to survive, INCLUDING
    velocities beyond the codec's own +/-31 px vector range:

      static    frame000 repeated          zero motion  - the ceiling on gain
      real      frame000, frame001         real motion  - the honest headline
      pingpong  000,001,000,001,...        real motion, 6 frames, steady state
      pan08      8 px/frame  integer       ordinary broadcast pan
      pan24     24 px/frame  integer       SOCCER-GRADE pan, inside MV range
      pan36     36 px/frame  integer       BEYOND MV range - do-no-harm proof
      panfrac    8.5 px/frame fractional   half-pel stress

The pan sequences slide a window across the still, so the motion is exactly
known and the ground truth is pristine.  `panfrac` is resampled with Lanczos
on the 8-bit RGB before conversion, so it is very slightly softer than the
others; its ground truth is the resampled picture, so the comparison stays
fair.  Real non-rigid motion (surf) exists only in `real`/`pingpong` - that
is the case no motion model can track, and it is measured separately.

Run:  python3 harness/tf_prep.py
"""

import os

import numpy as np
from PIL import Image

from common import downsample_422, rgb8_to_ycbcr, write_yuv

Image.MAX_IMAGE_PIXELS = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CINE = os.environ.get("OMC_CINE_DIR", os.path.join(ROOT, "work", "cine"))
OUT = os.path.join(ROOT, "work", "tf")

# Full-frame sequences use the native size (2048x1152; both already multiples
# of 32, so no crop is needed).  Pan sequences slide a smaller window so that
# the pan reveals genuinely new content instead of wrapping.
PAN_W, PAN_H = 1536, 1024
NPAN = 6


def load(idx):
    p = os.path.join(CINE, "cine_A005C021_frame%03d.png" % idx)
    return np.array(Image.open(p).convert("RGB"))


def to422(rgb):
    """8-bit RGB -> (Y, Cb, Cr) 10-bit 4:2:2 uint16 planes."""
    Y, Cb, Cr = rgb8_to_ycbcr(rgb, bits=10)
    return [Y, downsample_422(Cb), downsample_422(Cr)]


def emit(name, rgb_frames):
    os.makedirs(OUT, exist_ok=True)
    frames = [to422(f) for f in rgb_frames]
    path = os.path.join(OUT, name + ".yuv")
    write_yuv(path, frames)
    h, w = rgb_frames[0].shape[:2]
    print("  %-9s %4dx%-5d %d frame(s)  %s" % (name, w, h, len(frames), path))
    return w, h, len(frames)


def lanczos_shift(rgb, dx):
    """Sub-pixel horizontal shift by Lanczos-3 resampling (test rig only).

    out[x] = sum_k in[x + k] * L3(k - dx),  k in [-2 .. 3], edge-clamped.
    Float arithmetic is fine here: this builds the MASTER, it is not codec code.
    """
    ks = np.arange(-2, 4)
    t = ks - dx
    with np.errstate(invalid="ignore", divide="ignore"):
        w = np.where(t == 0, 1.0,
                     np.sinc(t) * np.sinc(t / 3.0) * (np.abs(t) < 3.0))
    w = w / w.sum()
    h, wid = rgb.shape[:2]
    src = rgb.astype(np.float64)
    acc = np.zeros_like(src)
    for k, wk in zip(ks, w):
        idx = np.clip(np.arange(wid) + k, 0, wid - 1)
        acc += wk * src[:, idx]
    return np.clip(np.round(acc), 0, 255).astype(np.uint8)


def main():
    f0, f1 = load(0), load(1)
    print("cine masters -> %s" % OUT)

    manifest = {}
    manifest["static"] = emit("static", [f0] * 6)
    manifest["real"] = emit("real", [f0, f1])
    manifest["pingpong"] = emit("pingpong", [f0, f1, f0, f1, f0, f1])

    for name, vel in (("pan08", 8), ("pan24", 24), ("pan36", 36)):
        seq = [f0[:PAN_H, i * vel:i * vel + PAN_W] for i in range(NPAN)]
        manifest[name] = emit(name, seq)

    # fractional pan: 8.5 px/frame.  Resample the FULL still once per frame
    # phase, then window it, so every frame carries the same resampling loss.
    seq = []
    for i in range(NPAN):
        pos = i * 8.5
        ip, fp = int(pos), pos - int(pos)
        src = f0 if fp == 0.0 else lanczos_shift(f0, fp)
        seq.append(src[:PAN_H, ip:ip + PAN_W])
    manifest["panfrac"] = emit("panfrac", seq)

    print("\nmotion budget vs the codec's transmitted vectors "
          "(+/-31 px h, +/-15 px v):")
    for name, vel in (("pan08", 8), ("pan24", 24), ("pan36", 36),
                      ("panfrac", 8.5)):
        print("  %-9s %5.1f px/frame  %s" %
              (name, vel, "inside" if vel <= 31 else "OUTSIDE - do-no-harm case"))
    return manifest


if __name__ == "__main__":
    main()
