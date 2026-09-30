#!/usr/bin/env python3
"""armscore.py SRC DEC W H NFRAMES [--ref REF.yuv] [--fmt][--depth][--sh][--blk]
              [--label X] [--frame 3]

ONE LINE PER ARM, AND IT IS NEVER LUMA-ONLY.

Every column exists in three copies -- Y, Cb, Cr -- because the recurring
failure in this project is to measure luma, declare a win, and ship a chroma
regression.  On the arm that opened this investigation the v4.14 -> v5.1 change
cost 19% of the luma detail and 35% of the chroma detail; a luma-only
scorecard would have called that a 19% problem.

Columns:
  ret       detail retention: mean |horizontal gradient| of the decode over the
            source, per plane.  1.0 = every edge survived.
  dev       the SPREAD of that retention across row phase inside the slice, as
            a percentage of its own mean.  0% = the coding grid is invisible.
            Non-zero means the picture is sharper at some row phases than
            others AT A FIXED PITCH, which is read as flatness in the starved
            phases and as banding at the sharp ones.
  flat      blocks that >=10 of the fifteen h/flatlib.py measures call flatter
            than REF (default: flatter than the source's own detail level).
  sat/hue   the two chroma-only flatness measures, reported separately so a
            chroma collapse cannot hide inside a 15-measure consensus.
  PSNR      per plane.  NEG: VMAF-NEG (luma-only BY CONSTRUCTION -- which is
            exactly why it is the LAST column here and never the deciding one).
"""
import sys, os, subprocess
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yuvio, flatlib

a = sys.argv
src, dec, W, H, N = a[1], a[2], int(a[3]), int(a[4]), int(a[5])
fmt   = a[a.index('--fmt')+1]        if '--fmt'   in a else '422'
depth = int(a[a.index('--depth')+1]) if '--depth' in a else 10
sh    = int(a[a.index('--sh')+1])    if '--sh'    in a else 16
blk   = int(a[a.index('--blk')+1])   if '--blk'   in a else 8
lab   = a[a.index('--label')+1]      if '--label' in a else os.path.basename(dec)
FR    = int(a[a.index('--frame')+1]) if '--frame' in a else 3
ref   = a[a.index('--ref')+1]        if '--ref'   in a else None
noneg = '--noneg' in a

def gx(p): return np.abs(np.diff(p, axis=1)).mean(axis=1)

accS = np.zeros((3, sh)); accD = np.zeros((3, sh))
for f in range(N):
    S = yuvio.planes(src, W, H, f, fmt, depth)
    D = yuvio.planes(dec, W, H, f, fmt, depth)
    for i in range(3):
        s_, d_ = gx(S[i]), gx(D[i])
        for r in range(S[i].shape[0]):
            accS[i, r % sh] += s_[r]; accD[i, r % sh] += d_[r]
ret = accD / np.maximum(accS, 1e-9)
retm = ret.mean(1)
dev  = 100.0 * (ret.max(1) - ret.min(1)) / np.maximum(retm, 1e-9)

def load(path, f):
    y, cb, cr = yuvio.planes(path, W, H, f, fmt, depth)
    r, g, b = yuvio.rgbish(y, cb, cr, W, fmt, depth)
    return dict(y=y, cb=cb, cr=cr, r=r, g=g, b=b, mid=1 << (depth-1),
                cbf=yuvio.upchroma(cb, W, fmt), crf=yuvio.upchroma(cr, W, fmt))

s, d = load(src, FR), load(dec, FR)
sp = load(src, FR-1) if FR > 0 else None
dp = load(dec, FR-1) if FR > 0 else None
rf = load(ref, FR) if ref else None
rfp = load(ref, FR-1) if (ref and FR > 0) else None
detail = flatlib.detail_of(s, blk)
cons = None; chroma = {}
for name, fn, _ in flatlib.MEASURES:
    r_ = fn(s, d, sp, dp, blk) if name == 'M15_temporal' else fn(s, d, blk)
    if rf is not None:
        r2 = fn(s, rf, sp, rfp, blk) if name == 'M15_temporal' else fn(s, rf, blk)
        r_ = flatlib._ratio(r_, r2, 1e-3)
    else:
        r_ = flatlib.normalise(r_, detail)
    if name in ('M09_chroma_sd', 'M10_sat', 'M11_hue', 'M12_rgb_grad'):
        chroma[name] = float(np.median(r_))
    fl = (r_ < 0.70).astype(np.int32)
    cons = fl if cons is None else cons + fl
f10 = int((cons >= 10).sum()); f6 = int((cons >= 6).sum())

ps = []
for i in range(3):
    e2 = 0.0; n = 0
    for f in range(N):
        S = yuvio.planes(src, W, H, f, fmt, depth)[i]
        D = yuvio.planes(dec, W, H, f, fmt, depth)[i]
        e2 += float(((S - D) ** 2).sum()); n += S.size
    mse = e2 / n
    ps.append(10 * np.log10(((1 << depth) - 1) ** 2 / max(mse, 1e-9)))

neg = "n/a"
if not noneg:
    try:
        neg = subprocess.run(["bash", os.path.join(os.path.dirname(os.path.abspath(__file__)), "vmafneg.sh"),
                              src, dec, str(W), str(H), str(N)],
                             capture_output=True, text=True, timeout=1800).stdout.strip() or "err"
    except Exception:
        neg = "err"

print("%-26s ret Y/Cb/Cr %.3f/%.3f/%.3f  dev %4.1f/%4.1f/%4.1f%%  flat>=10 %5d  >=6 %5d"
      "  | chroma med sd/sat/hue/rgbg %.2f/%.2f/%.2f/%.2f  | PSNR %.2f/%.2f/%.2f  NEG %s"
      % (lab, retm[0], retm[1], retm[2], dev[0], dev[1], dev[2], f10, f6,
         chroma['M09_chroma_sd'], chroma['M10_sat'], chroma['M11_hue'], chroma['M12_rgb_grad'],
         ps[0], ps[1], ps[2], neg))
