"""Adversarial constant sweep: were the UNSWEPT constants actually right?

K was chosen by measurement (harness/tf_sweep.py).  Three other constants were
not — they were reasoned to, which is exactly the kind of decision C6 says to
distrust:

    OMC_TF_ACT_FLOOR (4)   how much a structureless block may differ and still
                           be filtered — the flat-block allowance
    c1, c2 (2, 4)          the self-scaling gate-2 multipliers, in units of the
                           block's own mean compensated difference

This sweeps each around its shipped value on the whole corpus, reporting every
plane and both VMAF variants, and states plainly whether the shipped value wins.
A sweep that confirms the shipped value is not a wasted sweep: it converts a
guess into a measurement.

Run:  python3 harness/tf_tune.py [--bpp 0.5]
"""

import argparse
import os
import sys

import tf_verify as V


def sweep(name, values, seqs, bpp, base):
    print("\n=== %s ===" % name)
    print("%-14s %8s %8s %8s %8s %8s   %s"
          % ("value", "dY", "dCb", "dCr", "dVMAF", "dNEG", "worst"))
    rows = {}
    for val in values:
        for k, v in val.items():
            os.environ[k] = str(v)
        agg = [0.0] * 5
        worst = 99.0
        for s in seqs:
            w, h, _ = V.SEQS[s]
            r = V.measure(s, w, h, bpp, 1)
            b = base[s]
            d = (r["Y"] - b["Y"], r["Cb"] - b["Cb"], r["Cr"] - b["Cr"],
                 r["vmaf"] - b["vmaf"], r["vmaf_neg"] - b["vmaf_neg"])
            agg = [x + y for x, y in zip(agg, d)]
            worst = min(worst, d[3], d[4])
        m = [x / len(seqs) for x in agg]
        label = ",".join("%s=%s" % (k.split("_")[-1], v) for k, v in val.items())
        rows[label] = (m, worst)
        print("%-14s %+8.3f %+8.3f %+8.3f %+8.3f %+8.3f   %+.3f"
              % (label, m[0], m[1], m[2], m[3], m[4], worst))
        for k in val:
            os.environ.pop(k, None)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bpp", type=float, default=0.5)
    ap.add_argument("--seqs", default="static,real,pingpong,pan24,pan36,panfrac")
    a = ap.parse_args()
    seqs = [s for s in a.seqs.split(",") if s]

    base = {}
    for s in seqs:
        w, h, _ = V.SEQS[s]
        base[s] = V.measure(s, w, h, a.bpp, 0)

    print("OMC-TF constant sweep @ %.2f bpp (deltas vs filter off; shipped "
          "values marked *)" % a.bpp)

    sweep("ACT_FLOOR  (shipped 4*)",
          [{"OMC_TF_AFLOOR": v} for v in (0, 2, 4, 8, 16)], seqs, a.bpp, base)
    sweep("gate-2 multipliers c1,c2  (shipped 2,4*)",
          [{"OMC_TF_C1": c1, "OMC_TF_C2": c2}
           for (c1, c2) in ((1, 2), (2, 4), (3, 6), (2, 8), (4, 4))],
          seqs, a.bpp, base)
    return 0


if __name__ == "__main__":
    sys.exit(main())
