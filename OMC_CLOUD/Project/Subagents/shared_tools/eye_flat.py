#!/usr/bin/env python3
"""Eye-check render for the flatness bar, IN COLOUR (owner rule: never luma only).

usage: eye_flat.py src.yuv W H frame out.png dec1.yuv [dec2.yuv ...]  [--fmt 422] [--depth 10]
Panels: source, then each decode, stacked (or side by side when narrow).  Flat textured blocks
(flatplane's criterion: source block high-pass energy > 0.5 x frame median, decoded < 0.35 x median)
are outlined per plane: luma RED, Cb GREEN, Cr BLUE.  Output is BT.709 RGB from 4:2:2/4:4:4 YCbCr.
"""
import sys, numpy as np
from PIL import Image
a = sys.argv[1:]; fmt, depth = '422', 10
if '--fmt' in a: i = a.index('--fmt'); fmt = a[i+1]; del a[i:i+2]
if '--depth' in a: i = a.index('--depth'); depth = int(a[i+1]); del a[i:i+2]
src, W, H, f, out = a[0], int(a[1]), int(a[2]), int(a[3]), a[4]; decs = a[5:]
Wc = W // 2 if fmt == '422' else W
fw = W*H + 2*Wc*H; mx = (1 << depth) - 1

def planes(path):
    d = np.fromfile(path, dtype=np.uint16)[f*fw:(f+1)*fw].astype(np.float32)
    y = d[:W*H].reshape(H, W); cb = d[W*H:W*H+Wc*H].reshape(H, Wc); cr = d[W*H+Wc*H:].reshape(H, Wc)
    return y, cb, cr
def hp(p):
    return p - (np.roll(p,1,0)+np.roll(p,-1,0)+np.roll(p,1,1)+np.roll(p,-1,1))/4
def blocks(e, bw, bh=16):
    Hh, Ww = e.shape; return (e[:Hh//bh*bh, :Ww//bw*bw]**2).reshape(Hh//bh, bh, Ww//bw, bw).mean(axis=(1,3))
def to_rgb(y, cb, cr):
    if Wc != W: cb = np.repeat(cb, 2, axis=1)[:, :W]; cr = np.repeat(cr, 2, axis=1)[:, :W]
    yy = (y / mx * 255.0 - 16*255/256) * (255/219); c1 = (cb / mx - 0.5) * 255 * (255/224); c2 = (cr / mx - 0.5) * 255 * (255/224)
    r = yy + 1.5748*c2; g = yy - 0.1873*c1 - 0.4681*c2; b = yy + 1.8556*c1
    return np.clip(np.stack([r, g, b], -1), 0, 255).astype(np.uint8)
def outline(rgb, flat, bw, colour, off):
    ys, xs = np.nonzero(flat)
    for yb, xb in zip(ys, xs):
        y0, y1, x0, x1 = yb*16+off, min((yb+1)*16-1-off, H-1), xb*bw+off, min((xb+1)*bw-1-off, W-1)
        rgb[y0:y1+1, x0, :] = colour; rgb[y0:y1+1, x1, :] = colour; rgb[y0, x0:x1+1, :] = colour; rgb[y1, x0:x1+1, :] = colour

sy, scb, scr = planes(src)
refs = []
for p, bw in ((sy, 16), (scb, 16 if Wc == W else 8), (scr, 16 if Wc == W else 8)):
    es = blocks(hp(p), bw); med = np.median(es); refs.append((es > 0.5*med, med, bw))
panels = [to_rgb(sy, scb, scr)]
for dpath in decs:
    dy, dcb, dcr = planes(dpath); rgb = to_rgb(dy, dcb, dcr); line = []
    for k, (p, name, colour, off) in enumerate(((dy, 'Y', [255,0,0], 0), (dcb, 'Cb', [0,255,0], 1), (dcr, 'Cr', [0,80,255], 2))):
        tex, med, bw = refs[k]; ed = blocks(hp(p), bw); flat = (ed < 0.35*med) & tex
        scale = W // p.shape[1]
        line.append('%s %d/%d' % (name, int(flat.sum()), int(tex.sum())))
        # map chroma block columns to luma columns for drawing
        flat_l = np.repeat(flat, scale, axis=1)[:, :W//16] if scale > 1 and bw == 8 else flat
        outline(rgb, flat_l, 16, colour, off)
    print(dpath, 'flat textured blocks:', ', '.join(line))
    panels.append(rgb)
axis = 1 if W <= 512 else 0
Image.fromarray(np.concatenate(panels, axis=axis)).save(out)
print('wrote', out)
