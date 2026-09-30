#!/usr/bin/env python3
"""Measure each master's sensor-grain level and what it does to PSNR (note d).

Method:
  sigma_grain: robust noise estimate from the finest diagonal wavelet band
  (HH via one 5/3 level, both directions), sigma = MAD/0.6745, CALIBRATED by
  running the identical transform on synthetic N(0,1) noise so the filter gain
  cancels. Estimated per frame over 3 frames, median across frames.
  Spatial guard: MAD is computed only over low-activity samples (|HL|+|LH|
  below their own medians) so real texture inflates it less.

  temporal check: for near-static clips, sigma_t = MAD(frame_t - frame_{t-1})
  / (0.6745 * sqrt(2)) over low-motion pixels (|diff| < 6*sigma_est guard).

  PSNR_grain_floor = 10*log10(peak^2 / sigma^2): what a codec that output the
  EXACT grain-free signal would score against the grainy source. This is the
  number that bounds how much of any PSNR gap is attributable to (not) coding
  grain realization.
"""
import json, os
import numpy as np

W_ = os.path.dirname(os.path.abspath(__file__))

CLIPS = [
    ("beach",    2048, 1152, 422, 10),
    ("heli",     2048, 1152, 422, 10),
    ("aerial",   2048, 1152, 422, 10),
    ("trees",    4096, 2160, 422, 10),
    ("soccer",   3840, 2160, 422, 10),
    ("confetti", 3840, 2160, 422, 10),
    ("talking",  1280,  720, 422, 10),
    ("graincell",1920, 1080, 422, 10),
    ("couch",    1920, 1080, 444, 12),
    ("manwalk",  3840, 2160, 444, 12),
    ("mms",      4480, 1856, 444, 12),
    ("water",    3840, 1608, 444, 12),
    ("cow",      4480, 3096, 444, 12),
    ("8k",       7680, 4320, 422, 10),
]

def wav1(x):
    """One 2D 5/3 level -> (LL, HL, LH, HH) float."""
    x = x.astype(np.float64)
    def split(a, axis):
        s = np.take(a, range(0, a.shape[axis] & ~1, 2), axis=axis)
        d = np.take(a, range(1, a.shape[axis], 2), axis=axis)
        n = min(s.shape[axis], d.shape[axis])
        s = np.take(s, range(n), axis=axis); d = np.take(d, range(n), axis=axis)
        s2 = np.roll(s, -1, axis=axis)
        d = d - (s + s2) / 2
        dl = np.roll(d, 1, axis=axis)
        s = s + (dl + d) / 4
        return s, d
    L, H = split(x, 1)
    LL, LH = split(L, 0)
    HL, HH = split(H, 0)
    return LL, HL, LH, HH

# calibration: filter gain of HH on white N(0,1)
rng = np.random.default_rng(7)
_, _, _, HHn = wav1(rng.normal(0, 1, (512, 512)))
CAL = np.median(np.abs(HHn)) / 0.6745  # sigma reported by MAD on unit noise

def sigma_frame(y):
    LL, HL, LH, HH = wav1(y)
    act = np.abs(HL)[:HH.shape[0], :HH.shape[1]] + np.abs(LH)[:HH.shape[0], :HH.shape[1]]
    thr = np.median(act)
    sel = np.abs(HH)[act <= thr]
    return np.median(sel) / 0.6745 / CAL

def main():
    out = {}
    for name, W, H, fmt, depth in CLIPS:
        p = os.path.join(W_, f"m_{name}.yuv")
        if not os.path.exists(p):
            continue
        cw = W // 2 if fmt == 422 else W
        fw = W * H + 2 * cw * H
        data = np.fromfile(p, dtype="<u2")
        n = len(data) // fw
        peak = float((1 << depth) - 1)
        sigs, tsigs = [], []
        for f in range(min(4, n)):
            y = data[f * fw : f * fw + W * H].reshape(H, W).astype(np.float64)
            sigs.append(sigma_frame(y))
            if f > 0:
                y0 = data[(f - 1) * fw : (f - 1) * fw + W * H].reshape(H, W).astype(np.float64)
                d = y - y0
                guard = np.abs(d) < max(6 * sigs[-1], 8)
                if guard.sum() > 1000:
                    tsigs.append(np.median(np.abs(d[guard])) / 0.6745 / np.sqrt(2))
        sig = float(np.median(sigs))
        tsig = float(np.median(tsigs)) if tsigs else None
        floor = 10 * np.log10(peak * peak / (sig * sig)) if sig > 0 else 99.0
        out[name] = {
            "sigma_wavelet": round(sig, 3),
            "sigma_temporal": round(tsig, 3) if tsig else None,
            "psnr_if_grain_free": round(floor, 2),
            "depth": depth, "fmt": fmt,
        }
        print(f"{name:10s} sigma_HH={sig:6.2f}  sigma_temp={tsig if tsig else float('nan'):6.2f} "
              f" PSNR-if-grain-free={floor:6.2f} dB ({depth}-bit)", flush=True)
    json.dump(out, open(os.path.join(W_, "grain_measure.json"), "w"), indent=1)

if __name__ == "__main__":
    main()
