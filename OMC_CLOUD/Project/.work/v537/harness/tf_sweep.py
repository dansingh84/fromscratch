"""Sweep the gate-1 strictness constant K (C6: measure, then choose).

K is the alignment test's strictness: a block is filtered only if
    sad * K <= act + afloor * n
so a LARGER K demands stronger proof that the block really is the same content.
Too small and chaotic texture (surf, crowds) is blended and VMAF falls even as
PSNR rises; too large and the filter stops earning anything.

Reports every plane and both VMAF variants, on the whole corpus, so the choice
is made against the constraint that matters (C5: never luma-only).

Run:  python3 harness/tf_sweep.py [--ks 2,3,4,6] [--bpp 0.5]
"""

import argparse
import os
import sys

import tf_verify as V


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ks", default="2,3,4,6")
    ap.add_argument("--bpp", type=float, default=0.5)
    ap.add_argument("--seqs", default=",".join(V.SEQS))
    a = ap.parse_args()
    ks = [int(x) for x in a.ks.split(",")]
    seqs = [s for s in a.seqs.split(",") if s]

    base = {}
    for s in seqs:
        w, h, _ = V.SEQS[s]
        base[s] = V.measure(s, w, h, a.bpp, 0)

    print("gate-1 strictness sweep @ %.2f bpp (deltas vs filter off)\n" % a.bpp)
    print("%-9s %-3s %8s %8s %8s %8s %8s" %
          ("seq", "K", "dY", "dCb", "dCr", "dVMAF", "dNEG"))
    print("-" * 62)
    tot = {}
    for k in ks:
        os.environ["OMC_TF_K"] = str(k)
        worst_v = 99.0
        agg = [0.0] * 5
        for s in seqs:
            w, h, _ = V.SEQS[s]
            r = V.measure(s, w, h, a.bpp, 1)
            b = base[s]
            d = (r["Y"] - b["Y"], r["Cb"] - b["Cb"], r["Cr"] - b["Cr"],
                 r["vmaf"] - b["vmaf"], r["vmaf_neg"] - b["vmaf_neg"])
            agg = [x + y for x, y in zip(agg, d)]
            worst_v = min(worst_v, d[3], d[4])
            print("%-9s %-3d %+8.3f %+8.3f %+8.3f %+8.3f %+8.3f" % ((s, k) + d))
        tot[k] = (worst_v, [x / len(seqs) for x in agg])
        print("%-9s %-3d %+8.3f %+8.3f %+8.3f %+8.3f %+8.3f   worst perceptual %+.3f" %
              (("MEAN", k) + tuple(tot[k][1]) + (worst_v,)))
        print()
    os.environ.pop("OMC_TF_K", None)

    print("summary: K -> (worst VMAF/NEG delta on any sequence, mean dY, mean dVMAF)")
    for k in ks:
        wv, m = tot[k]
        print("   K=%-2d  worst %+.3f   mean dY %+.3f   mean dVMAF %+.3f   mean dNEG %+.3f"
              % (k, wv, m[0], m[3], m[4]))
    good = [k for k in ks if tot[k][0] >= 0.0]
    print("\nK values that never lose on any sequence, on either VMAF variant: %s"
          % (good if good else "NONE"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
