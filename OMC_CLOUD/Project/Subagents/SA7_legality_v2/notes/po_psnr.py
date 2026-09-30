#!/usr/bin/env python3
# [SA7-PO] per-plane PSNR, mean over frames and WORST FRAME, for gate (3).
# Every master in this project is a uint16 container whatever the coded depth,
# so the dtype is fixed at uint16 -- shared_tools/planepsnr.py picks uint8 at
# depth 8 and would read those files wrongly.
# usage: po_psnr.py SRC DEC W H FMT DEPTH NF TAG
import sys, numpy as np
src, dec, W, H, fmt, dep, nf, tag = (sys.argv[1], sys.argv[2], int(sys.argv[3]),
    int(sys.argv[4]), sys.argv[5], int(sys.argv[6]), int(sys.argv[7]), sys.argv[8])
cw = W if fmt == '444' else W // 2
fw = W * H + 2 * cw * H
mx = float((1 << dep) - 1)
s = np.fromfile(src, dtype='<u2', count=fw * nf)
d = np.fromfile(dec, dtype='<u2', count=fw * nf)
n = min(len(s), len(d)) // fw
if n == 0:
    print('PSNR', tag, 'NODATA'); sys.exit(0)
segs = [(0, W * H), (W * H, cw * H), (W * H + cw * H, cw * H)]
per = np.zeros((n, 3))
for f in range(n):
    for k, (off, sz) in enumerate(segs):
        e = (d[f*fw+off:f*fw+off+sz].astype(np.float64)
           - s[f*fw+off:f*fw+off+sz].astype(np.float64))
        m = (e * e).mean()
        per[f, k] = 99.0 if m == 0 else 10 * np.log10(mx * mx / m)
print('PSNR %s n=%d meanY=%.4f meanCb=%.4f meanCr=%.4f '
      'worstY=%.4f worstCb=%.4f worstCr=%.4f worstfY=%d'
      % (tag, n, per[:,0].mean(), per[:,1].mean(), per[:,2].mean(),
         per[:,0].min(), per[:,1].min(), per[:,2].min(), int(per[:,0].argmin())))
