#!/usr/bin/env python3
"""artifactmap.py -- the OWNER-VERIFIED way to find OMC's visible artifacts.

sect.50.7.  Dan verified on 2026-08-25 that (a) the signed error map shows
the artifacts he sees exactly where he sees them, and (b) the region set this
script produces is CORRECT -- it covers the long thin bright streaks on the
computer screen, the dark streaks on the light speaker, AND the dark spots on
the screen.  Four earlier detectors were rejected by him; see sect.50.7 for
why each failed.  Do not "improve" this by adding a shape, length or size
prior: that is exactly what made the earlier ones wrong.

Usage:
  artifactmap.py SRC.yuv DEC.yuv W H FRAME OUTDIR [--depth 10] [--fmt 422|444|400]
                 [--slice-h 16] [--plane Y|Cb|Cr]

v5.3.5 (sect.B3): `--plane` runs the identical map-and-region method on a chroma
plane, at that plane's own raster (half width at 4:2:2).  The v5.3 tool read
the Y plane only (LEDGER_v5_3 sect.78.2), and C5 forbids luma-only measurement.
The rule -- map first, regions read off the map, no shape prior -- is unchanged;
only the plane it is applied to is selectable.  Default Y, so every existing
call and every owner-verified luma result is unchanged.  The output tag carries
the plane name for Cb/Cr, and the "src" column is then the mean source CHROMA.

Writes, into OUTDIR:
  <tag>_ERRORMAP.png        signed error, RED = decoded brighter than source,
                            BLUE = darker, saturating at +-SAT codes
  <tag>_ERRORMAP_BOXED.png  the same map with every detected region boxed
  <tag>_DECODE_BOXED.png    the same boxes drawn on the decoded picture
  <tag>_regions.txt         one line per region: kind, rows, cols, area,
                            mean signed error, mean source luma, slice index
"""
import sys, os
import numpy as np
from PIL import Image, ImageDraw
from collections import deque

SAT = 40.0        # codes at which the map saturates (10-bit scale)
CHAN = 110        # a map pixel counts as "strong" above this channel value
DENS = 0.35       # required density of strong pixels in the neighbourhood
NH, NW = 5, 25    # neighbourhood: 5 rows x 25 cols (wide, because streaks are)
MINAREA = 150     # smallest region reported; NOT a shape filter

def plane(path, W, H, frame, fmt='422', which='Y'):
    """One plane of one frame, at the plane's own raster."""
    CW = 0 if fmt == '400' else (W // 2 if fmt == '422' else W)
    per = W*H + 2*CW*H
    a = np.fromfile(path, dtype='<u2', count=per, offset=frame*per*2)
    if a.size < per:
        raise SystemExit("artifactmap.py: short read at frame %d" % frame)
    if which == 'Y':  return a[:W*H].reshape(H, W).astype(float)
    if CW == 0:       raise SystemExit("artifactmap.py: no chroma plane in 4:0:0")
    if which == 'Cb': return a[W*H:W*H+CW*H].reshape(H, CW).astype(float)
    if which == 'Cr': return a[W*H+CW*H:W*H+2*CW*H].reshape(H, CW).astype(float)
    raise SystemExit("artifactmap.py: --plane must be Y, Cb or Cr")

def luma(path, W, H, frame, fmt='422'):
    return plane(path, W, H, frame, fmt, 'Y')

def boxfilt(a, kh, kw):
    c = np.cumsum(np.cumsum(np.pad(a.astype(float), ((kh,0),(kw,0))), 0), 1)
    return (c[kh:,kw:] - c[:-kh,kw:] - c[kh:,:-kw] + c[:-kh,:-kw]) / (kh*kw)

def components(mask, minarea=MINAREA):
    seen = np.zeros(mask.shape, bool); out = []
    ys, xs = np.nonzero(mask)
    for y, x in zip(ys, xs):
        if seen[y, x]: continue
        q = deque([(y, x)]); seen[y, x] = True; cells = []
        while q:
            cy, cx = q.popleft(); cells.append((cy, cx))
            for ny, nx in ((cy+1,cx),(cy-1,cx),(cy,cx+1),(cy,cx-1),
                           (cy+2,cx),(cy-2,cx),(cy,cx+3),(cy,cx-3)):
                if 0 <= ny < mask.shape[0] and 0 <= nx < mask.shape[1] \
                   and mask[ny,nx] and not seen[ny,nx]:
                    seen[ny,nx] = True; q.append((ny,nx))
        if len(cells) >= minarea: out.append(cells)
    return sorted(out, key=len, reverse=True)

def main(argv):
    src_p, dec_p, W, H, frame, outdir = argv[1], argv[2], int(argv[3]), int(argv[4]), int(argv[5]), argv[6]
    fmt = argv[argv.index('--fmt')+1] if '--fmt' in argv else '422'
    sh  = int(argv[argv.index('--slice-h')+1]) if '--slice-h' in argv else 16
    which = argv[argv.index('--plane')+1] if '--plane' in argv else 'Y'
    depth = int(argv[argv.index('--depth')+1]) if '--depth' in argv else 10
    os.makedirs(outdir, exist_ok=True)
    tag = os.path.splitext(os.path.basename(dec_p))[0] + f'_f{frame}' + ('' if which == 'Y' else f'_{which}')
    src = plane(src_p, W, H, frame, fmt, which); dec = plane(dec_p, W, H, frame, fmt, which)
    H, W = src.shape                      # the plane's own raster
    d = (dec - src) * (1024.0 / (1 << depth))   # common 10-bit code scale (v5.3 assumed 10-bit)

    # 1. the map.  This is the instrument the owner verified; everything else
    #    is derived FROM it, never from a fresh threshold on d.
    img = np.zeros((H, W, 3), np.uint8)
    img[...,0] = (np.clip( d/SAT, 0, 1)*255).astype(np.uint8)
    img[...,2] = (np.clip(-d/SAT, 0, 1)*255).astype(np.uint8)
    img[...,1] = ((1-np.clip(np.abs(d)/SAT, 0, 1))*40).astype(np.uint8)
    Image.fromarray(img).save(f'{outdir}/{tag}_ERRORMAP.png')

    # 2. regions, read back off the map itself
    strong_r = img[...,0] > CHAN
    strong_b = img[...,2] > CHAN
    mr = boxfilt(strong_r, NH, NW) > DENS
    mb = boxfilt(strong_b, NH, NW) > DENS

    em = Image.fromarray(img).convert('RGB')
    dc = np.clip(dec / float(1 << (depth - 8)), 0, 255).astype(np.uint8)
    dcim = Image.fromarray(np.dstack([dc]*3)).convert('RGB')
    d1, d2 = ImageDraw.Draw(em), ImageDraw.Draw(dcim)
    rows = []
    for mask, colour, kind in ((mr, (255,255,0), 'BRIGHT'), (mb, (0,255,0), 'DARK')):
        for cells in components(mask):
            ys = [c[0] for c in cells]; xs = [c[1] for c in cells]
            y0,y1,x0,x1 = min(ys), max(ys), min(xs), max(xs)
            for dd in (d1, d2): dd.rectangle([x0-2,y0-2,x1+2,y1+2], outline=colour)
            rows.append(f'{kind:6s} rows {y0:4d}-{y1:4d} cols {x0:4d}-{x1:4d} '
                        f'area {len(cells):6d} err {d[y0:y1+1,x0:x1+1].mean():+7.1f} '
                        f'src {src[y0:y1+1,x0:x1+1].mean():6.1f} slice {y0//sh}')
    em.save(f'{outdir}/{tag}_ERRORMAP_BOXED.png')
    dcim.save(f'{outdir}/{tag}_DECODE_BOXED.png')
    open(f'{outdir}/{tag}_regions.txt','w').write('\n'.join(rows)+'\n')
    nb = sum(1 for r in rows if r.startswith('BRIGHT')); nd = len(rows)-nb
    print(f'{tag}: {nb} bright regions, {nd} dark regions -> {outdir}/{tag}_*')

if __name__ == '__main__':
    main(sys.argv)
