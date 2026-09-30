#!/usr/bin/env python3
"""Row-resolution seam renders (coordinator round 6, item 3).
For each (decode, frame, boundary row): signed error decode - source averaged over 8-column x 1-row cells, rows
[b-12, b+12), Y | Cb | Cr side by side, each cell drawn 4 px wide x 4 px tall (a one-row step = 4 output pixels),
colour: red = decode too high, blue = too low, full colour at +-6 codes, white = 0; a legend strip underneath.
_grid variant: a black line at the boundary row (between row b-1 and b) and thin grey lines every 8 rows.
Prints per-row mean signed error (all columns) for rows b-6 .. b+5 per plane, and the whole-frame row-phase profile
(mean signed error by row index mod sh) per plane.
usage: rowmaps.py src.yuv W H sh outdir tag:dec.yuv:frame:boundary [...]"""
import sys, os, numpy as np
from PIL import Image, ImageDraw
src, W, H, sh, od = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]), sys.argv[5]; os.makedirs(od, exist_ok=True)
Wc = W // 2; fw = W * H + 2 * Wc * H
def planes(p, f):
    d = np.fromfile(p, dtype='<u2', count=fw, offset=f * fw * 2).astype(np.float64)
    return d[:W * H].reshape(H, W), d[W * H:W * H + Wc * H].reshape(H, Wc), d[W * H + Wc * H:].reshape(H, Wc)
def colour(v, sc=6.0):
    t = np.clip(v / sc, -1, 1); r = np.where(t > 0, 255, 255 * (1 + t)); b = np.where(t < 0, 255, 255 * (1 - t)); g = 255 * (1 - np.abs(t))
    return np.stack([r, g, b], -1).astype(np.uint8)
def panel(e, b):
    rows = e[b - 12:b + 12]; w = (rows.shape[1] // 8) * 8
    m = rows[:, :w].reshape(24, w // 8, 8).mean(2)
    img = colour(m); return np.kron(img, np.ones((4, 4, 1), np.uint8)), m
for spec in sys.argv[6:]:
    tag, dec, f, b = spec.split(':'); f, b = int(f), int(b)
    S = planes(src, f); D = planes(dec, f); pans = []; prof = []
    for nm, s, d in zip(('Y', 'Cb', 'Cr'), S, D):
        e = d - s; p, m = panel(e, b); pans.append(p)
        prof.append((nm, [float(e[r].mean()) for r in range(b - 6, b + 6)], [float(e[j::sh].mean()) for j in range(sh)]))
    gap = np.full((pans[0].shape[0], 12, 3), 40, np.uint8)
    body = np.concatenate([pans[0], gap, pans[1], gap, pans[2]], 1)
    leg = np.concatenate([colour(np.linspace(-6, 6, body.shape[1]))[None].repeat(16, 0)], 0)
    img = Image.fromarray(np.concatenate([body, np.full((6, body.shape[1], 3), 255, np.uint8), leg], 0))
    dr = ImageDraw.Draw(img); dr.text((4, body.shape[0] + 7), '-6 codes (blue: decode too low)', fill=(0, 0, 0))
    dr.text((body.shape[1] // 2 - 10, body.shape[0] + 7), '0', fill=(0, 0, 0)); dr.text((body.shape[1] - 200, body.shape[0] + 7), '+6 codes (red: too high)', fill=(0, 0, 0))
    base = os.path.join(od, '%s_f%d_row%d_signed8x1_YCbCr.png' % (tag, f, b)); img.save(base)
    g = img.copy(); dg = ImageDraw.Draw(g)
    for r in range(0, 24, 8 if sh >= 8 else sh):
        y = r * 4 + ((b - 12 + r) % sh) * 0; dg.line([(0, y), (body.shape[1], y)], fill=(170, 170, 170))
    dg.line([(0, 48), (body.shape[1], 48)], fill=(0, 0, 0), width=1)
    g.save(base.replace('.png', '_grid.png'))
    print('%s f%d boundary row %d (between rows %d and %d); panels Y | Cb | Cr' % (tag, f, b, b - 1, b))
    for nm, rp, ph in prof:
        print('  %-2s rows %d..%d mean signed err: %s' % (nm, b - 6, b + 5, ' '.join('%+.2f' % x for x in rp)))
        print('     row-phase profile (row mod %d, whole frame): %s' % (sh, ' '.join('%+.2f' % x for x in ph)))
