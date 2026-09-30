#!/usr/bin/env python3
"""[SA7] level map and |decode-source| map with the REGION GRID marked (owner ruling
2026-09-13: no harness verdict on steps is trusted; the grid must be visible so a human
can look for a step at boundary phase).
usage: gridmap.py SRC DEC W H FMT DEPTH FRAME OUTPREFIX --sh N --grid COLS
Draws: level map (block mean of decode-source, blocks sh/4 x 32, +-20 codes full scale,
red = decode above source) and |decode-source| (0..40 codes, white = large), each with
1-pixel green vertical lines at every COLS luma columns and green horizontal lines at
every slice boundary."""
import sys, numpy as np
from PIL import Image
a = sys.argv[1:]
sh = 16; grid = 64
for key in ('--sh','--grid'):
    if key in a:
        i = a.index(key); v = int(a[i+1]); del a[i:i+2]
        if key=='--sh': sh = v
        else: grid = v
src, dec, W, H, fmt, dep, f, outp = a[0], a[1], int(a[2]), int(a[3]), a[4], int(a[5]), int(a[6]), a[7]
Wc = W if fmt=='444' else W//2
fw = W*H + 2*Wc*H
def planes(p):
    d = np.fromfile(p, dtype=np.uint16)[f*fw:(f+1)*fw].astype(np.float64)
    if d.size < fw: sys.exit("frame %d not present in %s" % (f,p))
    return d[:W*H].reshape(H,W), d[W*H:W*H+Wc*H].reshape(H,Wc), d[W*H+Wc*H:].reshape(H,Wc)
S = planes(src); D = planes(dec)
bh, bw = max(sh//4,1), 32
for pi,name in enumerate(('Y','Cb','Cr')):
    s, d = S[pi], D[pi]
    h, w = s.shape
    e = d - s
    # ---- level map
    nb_y, nb_x = (h+bh-1)//bh, (w+bw-1)//bw
    bm = np.zeros((nb_y, nb_x))
    for by in range(nb_y):
        for bx in range(nb_x):
            bm[by,bx] = e[by*bh:(by+1)*bh, bx*bw:(bx+1)*bw].mean()
    up = np.kron(bm, np.ones((bh,bw)))[:h,:w]
    img = np.zeros((h,w,3), np.uint8)
    v = np.clip(up/20.0, -1, 1)
    img[...,0] = (np.clip(v,0,1)*255).astype(np.uint8)
    img[...,2] = (np.clip(-v,0,1)*255).astype(np.uint8)
    gstep = grid if pi==0 else max(grid//(W//Wc),1)
    Image.fromarray(img).save("%s_lvl_%s.png"%(outp,name))       # UNMARKED: what the owner looks at
    g1 = img.copy()
    g1[:, ::gstep, 1] = np.maximum(g1[:, ::gstep, 1], 90)        # control-point columns
    g1[::sh, :, 1] = np.maximum(g1[::sh, :, 1], 90)              # slice boundaries
    Image.fromarray(g1).save("%s_lvl_%s_grid.png"%(outp,name))   # MARKED: for locating only
    # ---- |decode - source|
    m = np.clip(np.abs(e)/40.0,0,1)
    g = (m*255).astype(np.uint8)
    img2 = np.dstack([g,g,g])
    Image.fromarray(img2).save("%s_absdiff_%s.png"%(outp,name))  # UNMARKED
    g2 = img2.copy()
    g2[:, ::gstep, 1] = 120
    g2[::sh, :, 1] = 120
    Image.fromarray(g2).save("%s_absdiff_%s_grid.png"%(outp,name))
    print("GRIDMAP %s %s f%d blockmean %.1f..%.1f  |e| mean %.2f p99 %.0f max %.0f  grid every %d cols, slice %d rows"
          % (outp,name,f,bm.min(),bm.max(),np.abs(e).mean(),np.percentile(np.abs(e),99),np.abs(e).max(),gstep,sh))
