"""Where does the temporal filter stop helping, and why?

The filter assumes the previous frame is an INDEPENDENT noisy observation of the
same truth, so averaging attenuates the noise.  In OMC-1 that assumption is only
true when the codec is rate-starved.  Given enough rate, inter prediction
REFINES: each frame is a strictly better estimate than the last (DESIGN.md 1b,
"prediction refines toward transparency").  Averaging a better estimate with a
worse one makes it worse, so above some rate the filter brakes the codec's own
convergence instead of removing noise.

Measured on `static` at 2.0 bpp, per frame, Y PSNR:
    filter off   48.06  52.88  55.25  56.42  57.81  58.18   <- converging
    filter on    48.06  52.14  54.25  55.01  55.30  55.38   <- braked

This script finds the crossover rate so the operating envelope can be enforced
rather than guessed.  PSNR-only by design: it is a boundary finder, and the
chosen boundary is then re-confirmed with the full per-plane + VMAF harness.

Run:  python3 harness/tf_rate.py
"""

import os
import subprocess
import sys

import numpy as np

from common import psnr_all, read_yuv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TF = os.path.join(ROOT, "work", "tf")
SEQS = {"static": (4480, 1856, 6), "pingpong": (4480, 1856, 6),
        "real": (4480, 1856, 2), "pan24": (1536, 1024, 6)}
RATES = [0.4, 0.5, 0.75, 1.0, 1.25, 1.5, 2.0]


def run(seq, w, h, n, bpp, s):
    env = dict(os.environ, OMC_TF=str(s))
    bs, dec = "/tmp/r.omc", "/tmp/r_%d.yuv" % s
    for cmd in ([os.path.join(ROOT, "omc_enc"), "-i", os.path.join(TF, seq + ".yuv"),
                 "-o", bs, "-w", str(w), "-h", str(h), "--fmt", "422",
                 "--depth", "10", "--bpp", str(bpp)],
                [os.path.join(ROOT, "omc_dec"), "-i", bs, "-o", dec]):
        r = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if r.returncode:
            raise SystemExit("failed: %s" % r.stderr[-300:])
    src = read_yuv(os.path.join(TF, seq + ".yuv"), w, h, w // 2, n)
    out = read_yuv(dec, w, h, w // 2, n)
    lo = 1 if n > 1 else 0
    p = [psnr_all(src[i], out[i], 10) for i in range(lo, n)]
    return tuple(float(np.mean([q[k] for q in p])) for k in ("Y", "Cb", "Cr"))


def main():
    print("OMC-TF operating envelope: filter-minus-baseline PSNR by rate\n")
    print("%-9s %6s %8s %8s %8s   %s" % ("seq", "bpp", "dY", "dCb", "dCr", "verdict"))
    print("-" * 62)
    boundary = {}
    for seq, (w, h, n) in SEQS.items():
        last_good = None
        for bpp in RATES:
            b = run(seq, w, h, n, bpp, 0)
            f = run(seq, w, h, n, bpp, 1)
            d = tuple(f[i] - b[i] for i in range(3))
            good = min(d) >= -0.02
            if good:
                last_good = bpp
            print("%-9s %6.2f %+8.3f %+8.3f %+8.3f   %s"
                  % (seq, bpp, d[0], d[1], d[2], "helps" if good else "HARMS"))
        boundary[seq] = last_good
        print()
    print("highest rate at which the filter does no harm, per sequence:")
    for k, v in boundary.items():
        print("   %-9s %s" % (k, ("%.2f bpp" % v) if v else "never"))
    ok = [v for v in boundary.values() if v]
    print("\nenvelope = min over sequences = %s"
          % (("%.2f bpp" % min(ok)) if len(ok) == len(boundary) else
             "UNDEFINED (a sequence never benefits)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
