"""Synthetic stress content for fill-safety validation (round 4.5).

Three known risk classes for the v4 grain fill, each with exact ground truth:

  textcrawl : broadcast-style lower third + scrolling ticker text over a
              gradient background, 6 px/frame - continuous synthetic motion.
              Risk: fill speckle on/near glyph edges (the LL activity gate
              fires on text); structure softening under motion.
  starfield : dim-to-bright point sources (1-3 px) on near-black, slow 2
              px/frame pan. Risk: sub-threshold stars erased and replaced by
              fill noise (fake stars), or fill speckle around bright stars.
  graphics  : flat panels, sharp edges, smooth gradients, thin lines - the
              Section G banding/edge stress. Risk: any fill at all (flat
              regions must stay exactly clean).

64 frames, 1920x1056, BT.709 limited range, 10-bit 4:2:2.
Usage: build_stress.py <textcrawl|starfield|graphics> <out.yuv>
"""
import sys, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import write_yuv

W, H, N = 1920, 1056, 64
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def rgb_to_yuv422_10(rgb):
    r, g, b = [rgb[..., i].astype(np.float64) / 255.0 for i in range(3)]
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    cb = (b - y) / 1.8556
    cr = (r - y) / 1.5748
    Y = np.clip(64 + y * (940 - 64), 0, 1023).round().astype(np.uint16)
    Cb = np.clip(512 + cb * 896, 0, 1023)
    Cr = np.clip(512 + cr * 896, 0, 1023)
    Cbs = ((Cb[:, 0::2] + Cb[:, 1::2]) / 2).round().astype(np.uint16)
    Crs = ((Cr[:, 0::2] + Cr[:, 1::2]) / 2).round().astype(np.uint16)
    return (Y, Cbs, Crs)


def textcrawl():
    big = ImageFont.truetype(FONT, 46)
    small = ImageFont.truetype(FONT, 34)
    ticker = ("BREAKING: OMC v4 grain fill must never touch text edges +++ "
              "QUICK BROWN FOXES JUMP 0123456789 +++ thin serifs, sharp stems, "
              "high contrast +++ ") * 4
    frames = []
    for i in range(N):
        img = Image.new("RGB", (W, H))
        d = ImageDraw.Draw(img)
        # gradient background (banding tripwire under everything)
        g = np.linspace(30, 120, H).astype(np.uint8)
        img.paste(Image.fromarray(np.dstack([np.tile(g[:, None], (1, W))] * 3)), (0, 0))
        # static lower third panel
        d.rectangle([60, H - 260, W - 60, H - 150], fill=(20, 40, 90))
        d.rectangle([60, H - 260, W - 60, H - 150], outline=(240, 240, 240), width=3)
        d.text((90, H - 245), "STATIC LOWER THIRD - fine text 12345", font=big,
               fill=(250, 250, 250))
        # scrolling ticker, 6 px/frame
        d.rectangle([0, H - 120, W, H - 40], fill=(10, 10, 10))
        d.text((W - (i * 6) % 4000, H - 105), ticker, font=small, fill=(230, 210, 60))
        # small moving logo box
        x = 100 + i * 4
        d.rectangle([x, 100, x + 220, 190], fill=(180, 30, 30))
        d.text((x + 14, 120), "LIVE", font=big, fill=(255, 255, 255))
        frames.append(rgb_to_yuv422_10(np.asarray(img)))
    return frames


def starfield():
    rng = np.random.RandomState(7)
    ns = 900
    sx = rng.uniform(0, W + 128, ns)
    sy = rng.uniform(0, H, ns)
    amp = rng.uniform(6, 500, ns)  # dim (sub-threshold) to bright, 10-bit codes
    frames = []
    for i in range(N):
        Y = np.full((H, W), 68.0)  # near-black, just above legal floor
        ox = i * 2.0  # 2 px/frame pan
        for x0, y0, a in zip(sx, sy, amp):
            x = x0 - ox
            if not (1 <= x < W - 1 and 1 <= y0 < H - 1):
                continue
            xi, yi = int(x), int(y0)
            fx, fy = x - xi, y0 - yi
            # bilinear splat = sub-pixel star motion
            for dy in (0, 1):
                for dx in (0, 1):
                    w = (fx if dx else 1 - fx) * (fy if dy else 1 - fy)
                    Y[yi + dy, xi + dx] += a * w
        Y = np.clip(Y, 64, 940).round().astype(np.uint16)
        C = np.full((H, W // 2), 512, dtype=np.uint16)
        frames.append((Y, C.copy(), C.copy()))
    return frames


def graphics():
    frames = []
    for i in range(N):
        img = Image.new("RGB", (W, H))
        d = ImageDraw.Draw(img)
        # large smooth horizontal gradient (G2 stress)
        g = np.linspace(16, 235, W).astype(np.uint8)
        img.paste(Image.fromarray(np.dstack([np.tile(g[None, :], (H, 1))] * 3)), (0, 0))
        # flat saturated panels with sharp edges
        d.rectangle([200, 120, 800, 500], fill=(200, 40, 40))
        d.rectangle([900, 120, 1700, 500], fill=(40, 160, 60))
        # thin 1px lines, moving 1 px/frame (sub-pixel-free structure)
        for k in range(30):
            x = (120 + k * 55 + i) % (W - 4)
            d.line([x, 620, x, 1000], fill=(255, 255, 255), width=1)
        d.ellipse([500 + i, 640, 900 + i, 990], outline=(0, 0, 0), width=2)
        frames.append(rgb_to_yuv422_10(np.asarray(img)))
    return frames


def main(which, out):
    frames = {"textcrawl": textcrawl, "starfield": starfield,
              "graphics": graphics}[which]()
    write_yuv(out, frames)
    print(which, len(frames), "frames ->", out)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
