#!/usr/bin/env python3
"""seam_repair.py - measure what the always-on XSL boundary edit repairs.

The T5 edit is exactly reversible, so the pre-edit picture is recoverable
from the decode itself: un-blending the CDR yields the committed
reconstruction as it would look with the boundary edit skipped (the
cross-slice wavelet term kept - the correct A/B, per XSL.md).

Usage: seam_repair.py dec.cdr unblended.cdr W Hcoded fmt depth slice_h refresh_r

Prints the slice-boundary step excess (mean |row-to-row| luma step at
boundaries minus interior; codes) for the edited and un-edited pictures.
Frame indices matter for the barrier phases, so both files carry the same
frame count.  Values are in the biased domain; differences cancel the bias.
"""
import sys
import numpy as np

def main():
    dfile, ufile, W, H, fmt, depth, sh, R = sys.argv[1:9]
    W, H, sh = int(W), int(H), int(sh)
    Wc = W if fmt == "444" else W // 2
    fw = W*H + 2*Wc*H
    d = np.fromfile(dfile, dtype='<u2')
    u = np.fromfile(ufile, dtype='<u2')
    nf = min(d.size // fw, u.size // fw)
    for f in range(nf):
        rows = []
        for name, buf in (("edited", d), ("no-edit", u)):
            y = buf[f*fw:f*fw+W*H].reshape(H, W).astype(np.float64)
            step = np.abs(np.diff(y, axis=0)).mean(axis=1)
            bmask = np.zeros(H-1, bool)
            bmask[sh-1::sh] = True
            rows.append(step[bmask].mean() - step[~bmask].mean())
        print(f"frame {f}: seam excess edited {rows[0]:+.3f}  no-edit {rows[1]:+.3f} "
              f"(codes; repair = {rows[1]-rows[0]:+.3f})")

if __name__ == "__main__":
    main()
