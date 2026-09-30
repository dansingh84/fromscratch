#!/usr/bin/env python3
"""pitch.py SRC DEC W H NFRAMES [--fmt][--depth][--sh 16][--label X][--cb 16]

PITCH POWER -- is the horizontal structure LOCKED TO THE CODING GRID?

h/line15.py's LINE INDEX (max row phase / median row phase) says a row phase is
special.  It cannot say whether that is the CODEC or the CONTENT: a picture with
a real horizontal edge every sixteen rows would score the same, and JPEG XS
scores 2.24 on this arm with its peaks on phases 5, 8, 9, 12 -- arbitrary
positions that move with the content -- against OMC's 2.56 with its peaks on
phase 0 and phases 13-15, which are the slice seam and the slice bottom.

So this measures PERIODICITY directly.  Take the per-row mean of the row-step
excess over the whole frame, subtract its mean, and take the magnitude of its
discrete Fourier component at exactly the slice frequency (one cycle per
slice_h rows), normalised by the profile's own RMS:

    PITCH = |sum_r  e(r) * exp(-2*pi*i*r/slice_h)| / (N * rms(e))

  0.00   no component at the slice pitch: any horizontal structure is content
  1.00   the row profile is a pure sinusoid at the slice pitch

Reported per plane, because the two chroma planes carry this defect more
strongly than luma on this codec and a luma-only reading under-states it.  The
SOURCE's own pitch power is printed as the null: content sometimes does have
periodic horizontal structure, and subtracting the source's value is the only
honest way to attribute the rest to the coding grid.
"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yuvio

a = sys.argv
src, dec, W, H, N = a[1], a[2], int(a[3]), int(a[4]), int(a[5])
fmt   = a[a.index('--fmt')+1]        if '--fmt'   in a else '422'
depth = int(a[a.index('--depth')+1]) if '--depth' in a else 10
sh    = int(a[a.index('--sh')+1])    if '--sh'    in a else 16
lab   = a[a.index('--label')+1]      if '--label' in a else os.path.basename(dec)

def pitchpow(prof, sh):
    e = prof - prof.mean()
    r = np.arange(len(e))
    c = np.abs((e * np.exp(-2j * np.pi * r / sh)).sum()) / len(e)
    rms = np.sqrt((e * e).mean())
    return float(c / max(rms, 1e-12))

acc = np.zeros((3, H)); accs = np.zeros((3, H))
for f in range(N):
    S = yuvio.planes(src, W, H, f, fmt, depth)
    D = yuvio.planes(dec, W, H, f, fmt, depth)
    for i in range(3):
        sd = np.abs(np.diff(S[i], axis=0)); dd = np.abs(np.diff(D[i], axis=0))
        acc[i, 1:] += (dd - sd).mean(1)
        accs[i, 1:] += sd.mean(1)
acc /= N; accs /= N
out = []
for i in range(3):
    out.append((pitchpow(acc[i, 1:], sh), pitchpow(accs[i, 1:], sh)))
print("%-28s PITCH dec-vs-src Y/Cb/Cr %.4f/%.4f/%.4f   | SOURCE null %.4f/%.4f/%.4f"
      % (lab, out[0][0], out[1][0], out[2][0], out[0][1], out[1][1], out[2][1]))
