"""Gate-1's design evidence: does a RELATIVE test separate aligned from misaligned?

Finding B2: the delivery document cites `work/tf_stats.py` three times -- for
section 17.3's aligned/misaligned block table and section 18.1's "a per-pixel |d|
gate admitted 97.8%" -- and the file exists nowhere.  That is the single most
load-bearing design measurement in Part II with no reproducible provenance, so
it is reconstructed here from the description in the document.

The claim under test: an ABSOLUTE threshold on the compensated difference |d|
cannot tell "this block matches" from "this block is quiet", because in a smooth
region everything matches everything.  What discriminates is the difference
RELATIVE to the local structure -- misalignment by d pixels produces a
difference proportional to the local gradient, and coding noise does not.

Run:  OMC_CINE_DIR=/path/to/footage python3 harness/tf_stats.py
"""

import os
import sys

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CINE = os.environ.get("OMC_CINE_DIR", os.path.join(ROOT, "work", "cine"))
BW, BH = 8, 4                      # OMC_TF_BW, OMC_TF_BH


def load():
    """Any two consecutive frames in OMC_CINE_DIR, whatever they are called.

    The delivery document hardcoded one filename and one geometry; that is
    finding 2 of this review, so this loader derives both from the directory.
    """
    names = sorted(f for f in os.listdir(CINE) if f.lower().endswith(".png"))
    if len(names) < 2:
        sys.exit("need at least two PNG frames in %s" % CINE)
    a = np.asarray(Image.open(os.path.join(CINE, names[0])).convert("L"), np.int32)
    b = np.asarray(Image.open(os.path.join(CINE, names[1])).convert("L"), np.int32)
    return a, b, names[:2]


def blocks(x):
    h, w = x.shape
    h, w = h // BH * BH, w // BW * BW
    return x[:h, :w].reshape(h // BH, BH, w // BW, BW).transpose(0, 2, 1, 3)


def stats(cur, prev, shift):
    """Compare `cur` against `prev` displaced by `shift` px horizontally."""
    p = np.roll(prev, shift, axis=1)
    lo, hi = max(0, shift), cur.shape[1] + min(0, shift)
    c, p = cur[:, lo:hi], p[:, lo:hi]
    d = np.abs(c - p)
    # activity = the block's own gradient sum, forward differences only
    act = np.abs(np.diff(c, axis=1, append=c[:, -1:])) + \
          np.abs(np.diff(c, axis=0, append=c[-1:, :]))
    sb, ab = blocks(d).sum(axis=(2, 3)), blocks(act).sum(axis=(2, 3))
    n = BW * BH
    return {
        "mean |cur-prev| per px": float(sb.sum()) / (sb.size * n),
        "mean ratio to activity": float(np.mean(sb / np.maximum(ab, float(n)))),
        "blocks passing sad*2 <= act": 100.0 * float(np.mean(sb * 2 <= ab)),
        "samples an ABSOLUTE |d| gate admits": 100.0 * float(np.mean(d <= 16)),
    }


def main():
    a, b, names = load()
    print("frames: %s, %s   %dx%d\n" % (names[0], names[1], a.shape[1], a.shape[0]))
    # "aligned" = the true consecutive pair; "misaligned" = the same pair with a
    # displacement no transmitted vector could express.
    al = stats(b, a, 0)
    mis = stats(b, a, 36)
    print("  %-38s %12s %12s" % ("per %dx%d block" % (BW, BH), "aligned", "misaligned"))
    for k in al:
        print("  %-38s %12.3f %12.3f" % (k, al[k], mis[k]))
    print()
    print("  The RELATIVE test separates the two cases; the ABSOLUTE one does not:")
    print("  it admits %.1f%% of a picture that is misaligned by 36 px, which is the"
          % mis["samples an ABSOLUTE |d| gate admits"])
    print("  defect section 18.1 records as costing 4.28 VMAF.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
