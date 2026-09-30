#!/usr/bin/env python3
"""gamut_probe.py - per-cell gamut evidence for the baseband matrix.

Usage: gamut_probe.py g1.cdr depth

Reads a CDR (biased u16 LE), prints the committed sample range in true codes
and the out-of-legal-range count: "range=[lo..hi] oob=N".  oob=0 is the
measured meaning of "in-gamut" for a baseband-matrix row.
"""
import sys
import numpy as np

def main():
    a = np.fromfile(sys.argv[1], dtype='<u2').astype(np.int64) - 2048
    maxv = (1 << int(sys.argv[2])) - 1
    oob = int((a < 0).sum() + (a > maxv).sum())
    print(f"range=[{a.min()}..{a.max()}] oob={oob}")

if __name__ == "__main__":
    main()
