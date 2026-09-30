#!/usr/bin/env python3
# rcl_ctx.py CLIP ARM — intra frame 0, form-(i) PO, real static-table code lengths under two entropy models:
#   base: 1-bit context (causal neighbour nonzero), as rcl_fi.py
#   ctx : neighbour bit x 5 activity classes; activity = |difference of the inner prediction taps| / level step, read
#         from this frame's FINAL coarser (or already final same-level) samples only -> decoder-computable, parse
#         depends on the current frame's stream only.
# Reconstruction is identical in both models (only bits change). Prints two lines per Q (ARM and ARM_ctx) in the
# rcl_fi format, so intra_vs_today.py scores both.
import sys, os, json, subprocess, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from d1_screen import read
from n4_core import po
MODEL = '/home/user/fromscratch/OMC_CLOUD/vmaf_model/vmaf_v0.6.1neg.json'
W, H = 1280, 720; LO, HI = 0, 1023
A = '/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/'
TRAIN = [('cine_4k_A006', 2), ('cine_A005C021', 2), ('gfx444_F003C012', 3)]
TEST, ARM = sys.argv[1], sys.argv[2]; cm = float(ARM[2:])
TH = np.array([0.5, 1.5, 4.0, 10.0])
OUT = os.path.join(os.path.dirname(__file__), '..', 'out', 'rcl_ctx'); os.makedirs(OUT, exist_ok=True)
def nzc(q):
    nz = q != 0; c = np.zeros_like(nz); c[:, 1:] |= nz[:, :-1]; c[1:, :] |= nz[:-1, :]; return c.astype(int)
def ctxs(q, a, rich): return nzc(q) * 5 + np.searchsorted(TH, a[:q.shape[0], :q.shape[1]]) if rich else nzc(q)
def tally(SY, AC, pl, tab, rich):
    for (key, q), a in zip(SY, AC):
        c = ctxs(q, a, rich); v = np.clip(q.astype(np.int64), -64, 64)
        for cc in np.unique(c):
            h = tab.setdefault((pl,) + key + (cc,), np.zeros(129)); np.add.at(h, v[c == cc] + 64, 1)
def cost(SY, AC, pl, tab, rich):
    bits = 0.0
    for (key, q), a in zip(SY, AC):
        c = ctxs(q, a, rich); q = q.astype(np.int64)
        for cc in np.unique(c):
            v = q[c == cc]; h = tab.get((pl,) + key + (cc,), np.zeros(129)) + 1; p = h / h.sum()
            bits += -np.log2(p[np.clip(v, -64, 64) + 64]).sum(); esc = np.abs(v) > 63; bits += (12 + 2 * np.log2(np.abs(v[esc]))).sum()
    return bits
def code_frame(planes, Q):
    outs = []; syms = []
    for pl, p in enumerate(planes):
        SY = []; AC = []; y = po(p, Q * (cm if pl else 1), 0.7, 0, SY, ACT=AC)[1]
        syms.append((min(pl, 1), SY, AC)); outs.append(y)
    return outs, syms
def neg1(src, dec):
    cmd = ['ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'yuv422p10le', '-s', '%dx%d' % (W, H), '-i', dec,
           '-f', 'rawvideo', '-pix_fmt', 'yuv422p10le', '-s', '%dx%d' % (W, H), '-i', src, '-frames:v', '1',
           '-lavfi', 'libvmaf=model=path=%s:n_threads=4:log_fmt=json:log_path=/dev/stdout' % MODEL, '-f', 'null', '-']
    return json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)['frames'][0]['metrics']['vmaf']
def psnr(a, b): return 10 * np.log10(1023.0 ** 2 / max(((a - b).astype(float) ** 2).mean(), 1e-9))
src = A + TEST + '_1280x720_422_10.yuv'; x = read(src, W, H, 0)
f0 = os.path.join(OUT, TEST + '_src_f0.yuv')
if not os.path.exists(f0):
    with open(f0, 'wb') as fo:
        for p in x: p.astype('<u2').tofile(fo)
TR = [read(A + c + '_1280x720_422_10.yuv', W, H, f) for c, nf in TRAIN for f in range(nf)]
for e in range(-6, 26):
    Q = 2 ** (e / 4); tabs = ({}, {})
    for fr in TR:
        for pl, SY, AC in code_frame(fr, Q)[1]:
            for r in (0, 1): tally(SY, AC, pl, tabs[r], r)
    outs, syms = code_frame(x, Q)
    bpp = [sum(cost(SY, AC, pl, tabs[r], r) for pl, SY, AC in syms) / (W * H) for r in (0, 1)]
    if not (0.5 <= bpp[1] < 4.6 or 0.5 <= bpp[0] < 4.6): continue
    fn = os.path.join(OUT, '%s_%s_%.3f.yuv' % (TEST, ARM, Q))
    with open(fn, 'wb') as fo:
        for p in outs: p.astype('<u2').tofile(fo)
    n = neg1(f0, fn); ps = [psnr(o, p) for o, p in zip(outs, x)]; oob = sum(int(((o < LO) | (o > HI)).sum()) for o in outs)
    for r, nm in ((0, ARM), (1, ARM + '_ctx')):
        print('%s %s Q=%.3f bpp %.4f NEG %.3f PSNR %.2f/%.2f/%.2f oob %d' % (TEST, nm, Q, bpp[r], n, *ps, oob), flush=True)
    os.unlink(fn)
