#!/usr/bin/env python3
"""crawlfill.py SRC NOFILL FILLED W H NFRAMES [--fmt][--depth][--label X][--thr 0]

CRAWL WHERE THE FILL ACTUALLY IS.

`tests/ants.py` reports the crawl over every block the SOURCE holds flat and
still.  That is the right population for judging a codec, and the WRONG one for
comparing two fill settings against each other, because a setting that fills
FEWER positions leaves more of that population perfectly still and so scores a
lower average -- without its filled positions being any calmer.

The owner asked precisely this (2026-08-26): "is it possible the crawl is less
on E because the flat blocks don't have any crawl?"

So this conditions on the fill.  The FILL REGION is the set of samples where the
filled decode differs from the same cell decoded with fill OFF -- that is
exactly where the fill put something and nowhere else.  Then:

  coverage    what fraction of the frame the fill region covers
  crawl@fill  the crawl tail INSIDE the fill region, for the filled arm
  base@fill   the crawl tail inside the SAME region for the NO-FILL arm

`base@fill` is the control that makes `crawl@fill` mean anything: it is what
those very samples were already doing before any fill was added.  The quantity
that decides whether a setting is calmer is `crawl@fill - base@fill`, the crawl
the fill ITSELF contributes, measured only where it exists.

Reported per plane.  Tail is P(|frame-to-frame difference| > 6 codes at 10-bit),
the same statistic and threshold ants.py uses, so the two are comparable.
"""
import sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yuvio

a = sys.argv
src, nofill, filled, W, H, N = a[1], a[2], a[3], int(a[4]), int(a[5]), int(a[6])
fmt   = a[a.index('--fmt')+1]        if '--fmt'   in a else '422'
depth = int(a[a.index('--depth')+1]) if '--depth' in a else 10
lab   = a[a.index('--label')+1]      if '--label' in a else os.path.basename(filled)
sc = 2.0 ** (depth - 10)
TAIL = 6.0 * sc

out = []
for pi, nm in enumerate(("Y", "Cb", "Cr")):
    F = [yuvio.planes(filled, W, H, f, fmt, depth)[pi] for f in range(N)]
    Nf = [yuvio.planes(nofill, W, H, f, fmt, depth)[pi] for f in range(N)]
    # the fill region: where the two arms differ at any frame
    reg = np.zeros_like(F[0], dtype=bool)
    for f in range(N):
        reg |= (F[f] != Nf[f])
    cov = float(reg.mean())
    if reg.sum() == 0:
        out.append((nm, cov, 0.0, 0.0)); continue
    cf = cb = 0.0; n = 0
    for f in range(1, N):
        df = np.abs(F[f][reg] - F[f-1][reg])
        db = np.abs(Nf[f][reg] - Nf[f-1][reg])
        cf += float((df > TAIL).sum()); cb += float((db > TAIL).sum()); n += df.size
    out.append((nm, cov, 100.0*cf/max(n,1), 100.0*cb/max(n,1)))

print("%-26s " % lab + "  ".join(
    "%s cov %5.1f%% crawl@fill %6.2f base@fill %6.2f  added %+6.2f"
    % (nm, 100*cov, cf, cb, cf-cb) for nm, cov, cf, cb in out))
