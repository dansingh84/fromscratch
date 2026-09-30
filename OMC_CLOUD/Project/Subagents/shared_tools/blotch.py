#!/usr/bin/env python3
"""blotch.py SRC.yuv DEC.yuv W H NFRAMES [--sh 16] [--fmt 422|444|400] [--depth 10]

sect.51's LEVEL instrument.  artifactmap.py (sect.50.7) is owner-verified for
FINDING the artifact; this quantifies its one defining property so two arms can
be RANKED.  The defect is a LEVEL error over a coherent block, and the block is
the LL band's support: (slice_h/4) picture rows by 32 plane columns.  So:

    BLOTCH = max over all frames and all blocks of |mean signed error|

reported alongside the 99.9th percentile and the counts of blocks past 20 and
past 40 codes, because one number can be beaten by luck and three cannot.
Unlike VMAF-NEG this rises when the damage is CONCENTRATED, which is exactly
the failure mode a mean-square metric rewards.

v5.3.5 EXTENSIONS (sect.B3 of LEDGER_v5_3_5; both were recorded as instrument gaps
in LEDGER_v5_3 sect.78.2 and sect.80.4b and are closed here, in the SHIPPED
tool rather than in a fourth instrument):

  1. ALL THREE PLANES.  The v5.3 tool read `[:W*H]` -- the Y plane only -- so
     chroma level error had never been measured anywhere in the project, even
     though the owner's item 4 (city "colour-block updating") is a chroma
     observation and C5 forbids luma-only measurement.  Each plane is now
     scored on its OWN LL support (the band layout is per plane width, so a
     chroma block is (slice_h/4) rows x 32 CHROMA columns).

  2. CONTIGUITY.  A max, a percentile and two counts cannot tell five scattered
     blocks from one long bar, and the eye reads the bar (sect.80.4b: the ship
     set "improved" the aggregate while relocating the wash into a bar the
     aggregate could not see).  `cont>20` is the largest 4-connected component
     of blocks past 20 codes, in blocks, over any single frame, with its frame
     and top-left corner, so a relocation shows up as a number.

  Output: one line per plane, then the LEGACY luma line LAST -- byte-for-byte
  the v5.3 format up to `n>40 N`, so every battery that does
  `tail -1 | grep -oE "n>20 [0-9]+\\s+n>40 [0-9]+"` keeps working unchanged.
  Do NOT rank on the luma line alone: read all three.
"""
import sys, numpy as np

def largest_component(mask):
    """Largest 4-connected component of a boolean block grid.
    Returns (size, (row, col)) of its top-left-most cell; (0, None) if empty."""
    H, W = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    best, bloc = 0, None
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys, xs):
        if seen[y0, x0]:
            continue
        stack = [(y0, x0)]; seen[y0, x0] = True; n = 0
        top = (y0, x0)
        while stack:
            y, x = stack.pop(); n += 1
            if (y, x) < top: top = (y, x)
            for ny, nx in ((y-1, x), (y+1, x), (y, x-1), (y, x+1)):
                if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True; stack.append((ny, nx))
        if n > best:
            best, bloc = n, top
    return best, bloc

def main(a):
    src, dec, W, H, N = a[1], a[2], int(a[3]), int(a[4]), int(a[5])
    fmt = a[a.index('--fmt')+1] if '--fmt' in a else '422'
    depth = int(a[a.index('--depth')+1]) if '--depth' in a else 10
    sc = 1024.0 / (1 << depth)      # report on a common 10-bit code scale
    sh = int(a[a.index('--sh')+1]) if '--sh' in a else 16
    bh, bw = sh // 4, 32
    if fmt == '400':
        CW = 0; names = ('Y',)
    else:
        CW = W // 2 if fmt == '422' else W; names = ('Y', 'Cb', 'Cr')
    per = W*H + 2*CW*H
    dims = {'Y': (H, W), 'Cb': (H, CW), 'Cr': (H, CW)}
    offs = {'Y': 0, 'Cb': W*H, 'Cr': W*H + CW*H}

    st = {n: dict(worst=0.0, loc=None, vals=[], cont=0, cloc=None) for n in names}
    for f in range(N):
        S = np.fromfile(src, dtype='<u2', count=per, offset=f*per*2).astype(np.float64)
        D = np.fromfile(dec, dtype='<u2', count=per, offset=f*per*2).astype(np.float64)
        if S.size < per or D.size < per:
            raise SystemExit("blotch.py: short read at frame %d (src %d, dec %d of %d)"
                             % (f, S.size, D.size, per))
        for n in names:
            hh, ww = dims[n]
            if hh < bh or ww < bw:
                continue
            s = S[offs[n]:offs[n]+hh*ww].reshape(hh, ww)
            d = D[offs[n]:offs[n]+hh*ww].reshape(hh, ww)
            e = (d - s) * sc
            nh, nw = hh // bh, ww // bw
            blk = e[:nh*bh, :nw*bw].reshape(nh, bh, nw, bw).mean(axis=(1, 3))
            r = st[n]
            r['vals'].append(blk.ravel())
            i = int(np.argmax(np.abs(blk)))
            v = blk.ravel()[i]
            if abs(v) > abs(r['worst']):
                r['worst'] = v; r['loc'] = (f, (i // nw) * bh, (i % nw) * bw)
            csz, cl = largest_component(np.abs(blk) > 20)
            if csz > r['cont']:
                r['cont'] = csz; r['cloc'] = (f, cl[0] * bh, cl[1] * bw)

    lines = []
    legacy = None
    for n in names:
        r = st[n]
        if not r['vals']:
            lines.append("BLOTCH %-2s n/a (plane narrower than one LL block)" % n)
            continue
        v = np.abs(np.concatenate(r['vals']))
        loc = r['loc'] or (0, 0, 0)
        cl = r['cloc'] or (0, 0, 0)
        n20, n40 = int((v > 20).sum()), int((v > 40).sum())
        lines.append("BLOTCH %-2s worst %+7.1f at f%d r%d c%d  p99.9 %5.1f  n>20 %d  n>40 %d  cont>20 %d (f%d r%d c%d)"
                     % (n, r['worst'], loc[0], loc[1], loc[2], np.percentile(v, 99.9),
                        n20, n40, r['cont'], cl[0], cl[1], cl[2]))
        if n == 'Y':
            legacy = ("BLOTCH(10b-scale) %+.1f at f%d r%d c%d  p99.9 %.1f  n>20 %d  n>40 %d  cont>20 %d"
                      % (r['worst'], loc[0], loc[1], loc[2], np.percentile(v, 99.9),
                         n20, n40, r['cont']))
    for l in lines: print(l)
    if legacy: print(legacy)   # LAST: legacy luma line, battery-compatible

if __name__ == '__main__': main(sys.argv)
