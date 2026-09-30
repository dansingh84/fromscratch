"""Shared helpers for the OMC-1 test harness.

This module is TEST INSTRUMENTATION only — it prepares masters and measures results.
It is not part of the codec (the codec is the C implementation in src/), so it is free
to use floating point. The codec itself never sees RGB: masters are converted once,
up front, to Y'CbCr and every codec input/output from then on is Y'CbCr planar.

Conversion convention (documented for reproducibility):
  - Source PNGs are 8-bit full-range R'G'B' (BT.709 primaries assumed for HD/UHD masters).
  - BT.709 matrix, limited ("video") range quantization:
      Y'  in [64 .. 940]   (10-bit),  [256 .. 3760] (12-bit)
      C'bC'r in [64 .. 960] centered at 512 (10-bit), [256 .. 3840] c. 2048 (12-bit)
  - 4:2:2 chroma: horizontal co-sited [1,2,1]/4 downsample (even sites), edge-clamped.
"""

import os
import subprocess
import numpy as np

# v5.1: the default was a hard-coded scratch path from the machine this harness
# was first written on, so every checkout without OMC_SCRATCH set pointed at a
# directory that does not exist.  The default is now the tree's own `work/`
# directory, which is machine-independent; OMC_SCRATCH still overrides it.
SCRATCH = os.environ.get(
    "OMC_SCRATCH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "work"),
)
FOOTAGE_DIR = os.path.join(SCRATCH, "footage")
MASTERS_DIR = os.path.join(SCRATCH, "masters")
VMAF_BIN = os.path.join(SCRATCH, "vmaf")

SEQUENCES = {
    "cow": "pf1_cow/cow",
    "fence": "pf2_fence/fence",
    "alpine": "pf3_alpine_city_forest/alpine",
    "city": "pf3_alpine_city_forest/city",
    "forest4k": "pf3_alpine_city_forest/forest4k",
    "beach": "pf4_couch12_beach/beach",
    "couch12": "pf4_couch12_beach/couch12",
}


# ---------------------------------------------------------------- color

def rgb8_to_ycbcr(rgb, bits=10):
    """Full-range 8-bit R'G'B' -> BT.709 limited-range Y'CbCr at `bits` depth (4:4:4).

    Returns (Y, Cb, Cr) as uint16 arrays of the same H x W shape.
    """
    r = rgb[..., 0].astype(np.float64) / 255.0
    g = rgb[..., 1].astype(np.float64) / 255.0
    b = rgb[..., 2].astype(np.float64) / 255.0
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    cb = (b - y) / 1.8556
    cr = (r - y) / 1.5748
    d = 1 << (bits - 8)
    ymax, ymin = 219 * d, 16 * d
    cmid, cspan = 128 * d, 224 * d
    Y = np.clip(np.round(ymin + ymax * y), 0, (1 << bits) - 1).astype(np.uint16)
    Cb = np.clip(np.round(cmid + cspan * cb), 0, (1 << bits) - 1).astype(np.uint16)
    Cr = np.clip(np.round(cmid + cspan * cr), 0, (1 << bits) - 1).astype(np.uint16)
    return Y, Cb, Cr


def ycbcr_to_rgb8(Y, Cb, Cr, bits=10):
    """Inverse of rgb8_to_ycbcr for viewing/galleries (limited-range BT.709 -> 8-bit RGB)."""
    d = 1 << (bits - 8)
    y = (Y.astype(np.float64) - 16 * d) / (219 * d)
    cb = (Cb.astype(np.float64) - 128 * d) / (224 * d)
    cr = (Cr.astype(np.float64) - 128 * d) / (224 * d)
    r = y + 1.5748 * cr
    b = y + 1.8556 * cb
    g = (y - 0.2126 * r - 0.0722 * b) / 0.7152
    rgb = np.stack([r, g, b], axis=-1)
    return np.clip(np.round(rgb * 255.0), 0, 255).astype(np.uint8)


def downsample_422(C):
    """Horizontal co-sited [1,2,1]/4 downsample of one chroma plane (H x W -> H x W/2)."""
    Cf = C.astype(np.int32)
    left = np.pad(Cf, ((0, 0), (1, 0)), mode="edge")[:, :-1]
    right = np.pad(Cf, ((0, 0), (0, 1)), mode="edge")[:, 1:]
    filt = (left + 2 * Cf + right + 2) >> 2
    return filt[:, ::2].astype(np.uint16)


def upsample_422(C):
    """Linear co-sited upsample of one chroma plane (H x W/2 -> H x W), for viewing only."""
    h, w2 = C.shape
    out = np.zeros((h, w2 * 2), dtype=np.uint16)
    out[:, ::2] = C
    nxt = np.pad(C.astype(np.int32), ((0, 0), (0, 1)), mode="edge")[:, 1:]
    out[:, 1::2] = ((C.astype(np.int32) + nxt + 1) >> 1).astype(np.uint16)
    return out


# ---------------------------------------------------------------- planar IO

def write_yuv(path, frames):
    """frames: list of (Y, Cb, Cr) uint16 planes -> little-endian 16-bit planar raw."""
    with open(path, "wb") as f:
        for (Y, Cb, Cr) in frames:
            f.write(Y.astype("<u2").tobytes())
            f.write(Cb.astype("<u2").tobytes())
            f.write(Cr.astype("<u2").tobytes())


def read_yuv(path, w, h, cw, nframes=None):
    """Read LE 16-bit planar raw. cw = chroma width. Returns list of (Y,Cb,Cr)."""
    fsz = os.path.getsize(path)
    frame_words = w * h + 2 * cw * h
    total = fsz // (2 * frame_words)
    if nframes is not None:
        total = min(total, nframes)
    out = []
    with open(path, "rb") as f:
        for _ in range(total):
            buf = np.frombuffer(f.read(2 * frame_words), dtype="<u2")
            Y = buf[: w * h].reshape(h, w).copy()
            Cb = buf[w * h : w * h + cw * h].reshape(h, cw).copy()
            Cr = buf[w * h + cw * h :].reshape(h, cw).copy()
            out.append((Y, Cb, Cr))
    return out


def write_y4m(path, frames, fmt="422", bits=10, fps=(50, 1)):
    """Write Y4M (for vmaf). fmt in {'422','444'}; frames = list of (Y,Cb,Cr)."""
    Y0 = frames[0][0]
    h, w = Y0.shape
    cs = {"422": f"C422p{bits}", "444": f"C444p{bits}"}[fmt]
    with open(path, "wb") as f:
        f.write(f"YUV4MPEG2 W{w} H{h} F{fps[0]}:{fps[1]} Ip A1:1 {cs}\n".encode())
        for (Y, Cb, Cr) in frames:
            f.write(b"FRAME\n")
            f.write(Y.astype("<u2").tobytes())
            f.write(Cb.astype("<u2").tobytes())
            f.write(Cr.astype("<u2").tobytes())


# ---------------------------------------------------------------- metrics

def psnr_plane(a, b, bits=10):
    a = a.astype(np.float64)
    b = b.astype(np.float64)
    mse = np.mean((a - b) ** 2)
    if mse == 0:
        return float("inf")
    peak = float((1 << bits) - 1)
    return 10.0 * np.log10(peak * peak / mse)


def psnr_all(ref, dist, bits=10):
    """Per-plane PSNR dict for one frame tuple (Y,Cb,Cr)."""
    return {
        "Y": psnr_plane(ref[0], dist[0], bits),
        "Cb": psnr_plane(ref[1], dist[1], bits),
        "Cr": psnr_plane(ref[2], dist[2], bits),
    }


def ssim_plane(a, b, bits=10):
    """Standard single-scale SSIM (Gaussian 11x11, sigma 1.5) on one plane."""
    from scipy.ndimage import gaussian_filter

    L = (1 << bits) - 1
    c1 = (0.01 * L) ** 2
    c2 = (0.03 * L) ** 2
    x = a.astype(np.float64)
    y = b.astype(np.float64)
    mx = gaussian_filter(x, 1.5)
    my = gaussian_filter(y, 1.5)
    mxx = gaussian_filter(x * x, 1.5)
    myy = gaussian_filter(y * y, 1.5)
    mxy = gaussian_filter(x * y, 1.5)
    vx = mxx - mx * mx
    vy = myy - my * my
    cxy = mxy - mx * my
    s = ((2 * mx * my + c1) * (2 * cxy + c2)) / ((mx * mx + my * my + c1) * (vx + vy + c2))
    return float(np.mean(s))


def chroma_spread_tripwire(ref, dist, bits=10):
    """Detect chroma collapse (desaturation / starvation) that PSNR can hide.

    Returns dict with:
      - dPSNR_spread: Y PSNR minus min(chroma PSNR) (dB). Large -> chroma starved.
      - sat_ratio: mean |C-mid| of dist / ref. << 1.0 -> desaturation collapse.
    """
    p = psnr_all(ref, dist, bits)
    mid = float(1 << (bits - 1))
    def sat(fr):
        return (np.mean(np.abs(fr[1].astype(np.float64) - mid))
                + np.mean(np.abs(fr[2].astype(np.float64) - mid)))
    sref = sat(ref)
    sdist = sat(dist)
    finite = [v for v in (p["Y"], p["Cb"], p["Cr"]) if v != float("inf")]
    spread = 0.0 if len(finite) < 2 else p["Y"] - min(p["Cb"], p["Cr"])
    return {
        "dPSNR_spread": spread,
        "sat_ratio": (sdist / sref) if sref > 0 else 1.0,
        "psnr": p,
    }


def run_vmaf(ref_y4m, dist_y4m, threads=4):
    """Run the (aarch64, qemu-emulated) official vmaf CLI. Returns pooled + per-frame VMAF."""
    import json
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        out_json = tf.name
    cmd = [
        "qemu-aarch64-static", "-L", "/usr/aarch64-linux-gnu", VMAF_BIN,
        "--reference", ref_y4m, "--distorted", dist_y4m,
        "--model", "version=vmaf_v0.6.1",
        "--threads", str(threads),
        "--json", "--output", out_json,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    with open(out_json) as f:
        data = json.load(f)
    os.unlink(out_json)
    frames = [fr["metrics"]["vmaf"] for fr in data["frames"]]
    return {"min": min(frames), "mean": sum(frames) / len(frames), "frames": frames}
