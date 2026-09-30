#!/usr/bin/env python3
"""[SA11 H0] stage comparison for the dumped slice. usage: h0_stage.py dir dec.yuv W H slice"""
import sys, os, numpy as np
d, dec, W, H, s = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
names = ['ref', 'pcoef', 'coef_pre_inv', 'pre_clip', 'post_clip', 'committed_after_edit']
st = {}
for f in range(8):
    fn = os.path.join(d, 'h0_f%d_s%d.bin' % (f, s))
    if not os.path.exists(fn): continue
    a = np.fromfile(fn, dtype='<i4'); hdr = a[-4:]; a = a[:-4].reshape(6, -1)
    st[f] = (a, hdr)
n0 = st[0][0].shape[1]; sh = n0 // W
fs = W * H * 2
disp = {f: np.fromfile(dec, dtype='<u2', count=W * H, offset=f * fs * 2).astype(np.int32).reshape(H, W)[s * sh:(s + 1) * sh].ravel() for f in range(8)}
print('stage dump slice %d plane Y (%d x %d): changed samples frame f-1 -> f per stage; inter = slice coded inter on frame f' % (s, W, sh))
for f in range(1, 8):
    if f not in st or f - 1 not in st: continue
    a, h = st[f]; b, hb = st[f - 1]
    row = ['f%d->f%d inter=%d' % (f - 1, f, h[2])]
    for i, nm in enumerate(names):
        c = int((a[i] != b[i]).sum()); row.append('%s %d' % (nm, c))
    c = int((disp[f] != disp[f - 1]).sum()); row.append('displayed %d' % c)
    # consistency: reference of frame f == displayed frame f-1 ?
    off = int(np.median(a[0] - disp[f - 1]))
    row.append('| bias %d ref(f)!=disp(f-1): %d' % (off, int((a[0] - off != disp[f - 1]).sum())))
    row.append('committed(f)!=disp(f): %d' % int((a[5] - off != disp[f]).sum()))
    dd = (disp[f] != disp[f - 1]).reshape(sh, W).sum(axis=1)
    row.append('disp_changed_by_row %s' % ','.join(str(int(x)) for x in dd))
    row.append('post_clip(f)!=ref(f): %d' % int((a[4] != a[0]).sum()))
    row.append('pre_clip(f)!=ref(f): %d' % int((a[3] != a[0]).sum()))
    print('  ' + ' '.join(row))
