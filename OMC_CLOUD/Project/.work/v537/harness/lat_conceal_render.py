#!/usr/bin/env python3
"""[A5-CONCEAL] eye check for the concealment branches.

Owner's rule (ledger H.0): never luma-only.  Every panel is a BT.709 COLOUR
render, and every comparison carries a per-plane |decode - reference| map.
Reference is the CLEAN decode -- concealment approximates what the viewer would
otherwise have seen, so that is what the error is measured against.

argv: clean.yuv shipped.yuv up.yuv W H fmt depth frame slice0 slice1 outprefix title
"""
import sys, numpy as np
from PIL import Image, ImageDraw

cl, sh_, up = sys.argv[1], sys.argv[2], sys.argv[3]
W, H = int(sys.argv[4]), int(sys.argv[5])
fmt, depth = sys.argv[6], int(sys.argv[7])
frame, s0, s1 = int(sys.argv[8]), int(sys.argv[9]), int(sys.argv[10])
outp, title = sys.argv[11], sys.argv[12]

SH = 16 if H > 720 else 8
CW = W if fmt == "444" else W // 2
fw = W*H + 2*CW*H
mx = float((1 << depth) - 1)

def load(p):
    d = np.fromfile(p, dtype=np.uint16, count=(frame+1)*fw)[frame*fw:(frame+1)*fw].astype(np.float64)
    Y = d[:W*H].reshape(H, W)
    Cb = d[W*H:W*H+CW*H].reshape(H, CW)
    Cr = d[W*H+CW*H:].reshape(H, CW)
    return Y, Cb, Cr

def rgb(Y, Cb, Cr):
    if CW != W:                       # 4:2:2 -> replicate chroma columns
        Cb = np.repeat(Cb, 2, axis=1); Cr = np.repeat(Cr, 2, axis=1)
    s = mx / 1023.0                   # the BT.709 constants are 10-bit
    y = (Y/s - 64)/876; cb = (Cb/s - 512)/896; cr = (Cr/s - 512)/896
    r = y + 1.5748*cr; g = y - 0.1873*cb - 0.4681*cr; b = y + 1.8556*cb
    return (np.clip(np.stack([r, g, b], -1), 0, 1)*255 + 0.5).astype(np.uint8)

C, A, B = load(cl), load(sh_), load(up)
r0, r1 = s0*SH, min((s1+1)*SH, H)
# a band of context around the concealed rows, so the eye sees the seam
pad = 3*SH
v0, v1 = max(0, r0-pad), min(H, r1+pad)

def band(pl):
    return rgb(*pl)[v0:v1]

panels = [("clean decode (reference)", band(C)),
          ("shipped concealment", band(A)),
          ("upward-only", band(B))]
ims = []
for name, im in panels:
    if im.shape[1] > 960:
        im = im[:, ::2]
    im = np.kron(im, np.ones((2, 2, 1), dtype=np.uint8))
    p = Image.fromarray(im); d = ImageDraw.Draw(p)
    d.rectangle([0, 0, 320, 18], fill=(0, 0, 0)); d.text((4, 3), name, fill=(255, 255, 255))
    # mark the concealed rows
    d.line([(0, (r0-v0)*2), (p.width, (r0-v0)*2)], fill=(255, 0, 0), width=1)
    d.line([(0, (r1-v0)*2), (p.width, (r1-v0)*2)], fill=(255, 0, 0), width=1)
    ims.append(p)
w = max(i.width for i in ims); h = sum(i.height for i in ims) + 8*2
out = Image.new('RGB', (w, h), (40, 40, 40)); y = 0
for i in ims: out.paste(i, (0, y)); y += i.height + 8
out.save(outp + "_colour.png")

# per-plane |decode - clean| maps over the concealed band, amplified, side by side
rows = []
for pi, pname in enumerate(("Y", "Cb", "Cr")):
    pw = W if pi == 0 else CW
    q0, q1 = (r0, r1)
    # A concealed band is 16 rows tall and up to 1920 wide; drawn at full width
    # it is an unreadable letterbox.  Crop to the 640-column window where the
    # two variants differ most, so the panel shows something an eye can judge.
    d_all = np.abs(A[pi][q0:q1] - B[pi][q0:q1])
    win = 320 if pw > 320 else pw
    if pw > win:
        colsum = d_all.sum(axis=0)
        cs = np.concatenate([[0], np.cumsum(colsum)])
        x0 = int(np.argmax(cs[win:] - cs[:-win]))
    else:
        x0 = 0
    cols = []
    for name, S in (("shipped", A), ("upward-only", B)):
        e = np.abs(S[pi][q0:q1, x0:x0+win] - C[pi][q0:q1, x0:x0+win])
        img = np.clip(e * 8, 0, 255).astype(np.uint8)
        img = np.kron(img, np.ones((4, 4), dtype=np.uint8))   # x4, no decimation
        p = Image.fromarray(img).convert("RGB"); d = ImageDraw.Draw(p)
        d.rectangle([0, 0, 300, 16], fill=(0, 0, 0))
        d.text((3, 2), "|%s - clean|  %s  x8  (cols %d-%d)" % (pname, name, x0, x0+win),
               fill=(255, 255, 255))
        cols.append(p)
    rows.append(cols)
# MEMO 009 clause 2: stack everything vertically and keep the long side under
# ~2000 px, or the viewer downscales and the x4 is fiction.
w = max(max(c[0].width, c[1].width) for c in rows)
h = sum(c[0].height + c[1].height + 16 for c in rows)
out = Image.new('RGB', (w, h), (40, 40, 40)); y = 0
for cols in rows:
    for c in cols: out.paste(c, (0, y)); y += c.height + 4
    y += 8
out = out.crop((0, 0, w, y))
assert max(out.size) <= 2000, "planediff %dx%d would be downscaled" % out.size
out.save(outp + "_planediff.png")
# ---- MEMO 008 rule 2: a magnified crop chosen so a ONE-SLICE displacement
# (8 or 16 lines) is plainly visible.  x4 minimum for band-structured artifacts.
# A one-slice offset is 1.5 % of frame height at 1080p and is easy to miss at
# full width -- that is exactly how the fbgame stagger got past me.
# Agent 4, Message 14: a x4 file tiled 3-wide comes out ~5800 px and any viewer
# downscales it -- the file is x4 and the EYE gets x1.4, with nothing warning
# you.  So: narrow source region, magnified hard, arms stacked VERTICALLY, and
# the output kept under ~2000 px on its long side.
ZW = 240
d_all = np.abs(A[0][r0:r1] - B[0][r0:r1])
if W > ZW:
    cs = np.concatenate([[0], np.cumsum(d_all.sum(axis=0))])
    zx = int(np.argmax(cs[ZW:] - cs[:-ZW]))
else:
    zx, ZW = 0, W
zy0, zy1 = max(0, r0 - 2*SH), min(H, r1 + 2*SH)
ims = []
for name, P in (("clean decode (reference)", C), ("shipped", A), ("upward-only", B)):
    im = rgb(*P)[zy0:zy1, zx:zx+ZW]
    im = np.kron(im, np.ones((4, 4, 1), dtype=np.uint8))     # x4
    q = Image.fromarray(im); d = ImageDraw.Draw(q)
    d.rectangle([0, 0, 300, 18], fill=(0, 0, 0))
    d.text((4, 3), name + "  x4", fill=(255, 255, 255))
    d.line([(0, (r0-zy0)*4), (q.width, (r0-zy0)*4)], fill=(255, 0, 0))
    d.line([(0, (r1-zy0)*4), (q.width, (r1-zy0)*4)], fill=(255, 0, 0))
    ims.append(q)
w = max(i.width for i in ims); h = sum(i.height for i in ims) + 8*2
out = Image.new('RGB', (w, h), (40, 40, 40)); y = 0
for i in ims: out.paste(i, (0, y)); y += i.height + 8
assert max(out.size) <= 2000, "zoom render %dx%d would be downscaled" % out.size
out.save(outp + "_zoom4.png")
print("wrote %s_colour.png, %s_planediff.png, %s_zoom4.png (x4, rows %d-%d cols %d-%d)  (%s)"
      % (outp, outp, outp, zy0, zy1, zx, zx+ZW, title))
