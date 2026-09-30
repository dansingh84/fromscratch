#!/usr/bin/env python3
# [A3] per-frame per-plane PSNR (the ledger's PLANEPSNR snippet from h_dc_flat.sh,
# generalised to 4:2:2 / 4:4:4 and any depth).  usage: planepsnr.py SRC DEC W H FMT DEPTH TAG
import sys, numpy as np
src, dec, W, H, fmt, dep, tag = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), sys.argv[5], int(sys.argv[6]), sys.argv[7]
cw = W if fmt == '444' else W // 2
fw = W * H + 2 * cw * H
dt = np.uint16 if dep > 8 else np.uint8
s = np.fromfile(src, dtype=dt); d = np.fromfile(dec, dtype=dt)
n = min(len(s), len(d)) // fw
mx = (1 << dep) - 1
segs = [(0, W * H), (W * H, cw * H), (W * H + cw * H, cw * H)]
r = []
for f in range(n):
    p = []
    for off, sz in segs:
        e = d[f*fw+off:f*fw+off+sz].astype(float) - s[f*fw+off:f*fw+off+sz].astype(float)
        p.append(10 * np.log10(mx**2 / (e**2).mean()))
    r.append('f%d %.2f/%.2f/%.2f' % (f, p[0], p[1], p[2]))
print('PLANEPSNR', tag, ' '.join(r))
