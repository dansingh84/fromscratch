#!/usr/bin/env python3
# rcl_fi.py CLIP ARM — form-(i) intra (private-leaf pyramid) at STATIC-TABLE code lengths (tables trained on the
# 3 disjoint training clips under the exact same arm/Q/config), frame 0, 720p, all planes -> VMAF-NEG + PSNR Y/Cb/Cr.
# ARM = "cm<mult>[_cl]": chroma quantiser step = mult x luma step (one normative per-plane constant, the SAME for
# every clip and rate); "_cl" = chroma predicted from FINAL luma (alpha per 16x16 block from final coarser-level
# data, eighths, shift-add). Ladder f = 0.7. Prints one line per Q; summarise with rcl_sum.py.
import sys, os, json, subprocess, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from d1_screen import read, dz
from n4_core import po
MODEL = '/home/user/fromscratch/OMC_CLOUD/vmaf_model/vmaf_v0.6.1neg.json'
W, H = 1280, 720
def ctx(q):
    nz = q != 0; c = np.zeros_like(nz); c[:, 1:] |= nz[:, :-1]; c[1:, :] |= nz[:-1, :]; return c
def tally(SY, pl, tab):
    for key, q in SY:
        c = ctx(q); q = q.astype(np.int64)
        for cc in (0, 1):
            v = np.clip(q[c == cc], -64, 64)
            h = tab.setdefault((pl,) + key + (cc,), np.zeros(129)); np.add.at(h, v + 64, 1)
def cost(SY, pl, tab):
    bits = 0.0
    for key, q in SY:
        c = ctx(q); q = q.astype(np.int64)
        for cc in (0, 1):
            v = q[c == cc]; h = tab.get((pl,) + key + (cc,), np.zeros(129)) + 1; p = h / h.sum()
            vi = np.clip(v, -64, 64); bits += -np.log2(p[vi + 64]).sum()
            esc = np.abs(v) > 63; bits += (12 + 2 * np.log2(np.abs(v[esc]))).sum()
    return bits
def neg1(src, dec):
    cmd = ['ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'yuv422p10le', '-s', '%dx%d' % (W, H), '-i', dec,
           '-f', 'rawvideo', '-pix_fmt', 'yuv422p10le', '-s', '%dx%d' % (W, H), '-i', src, '-frames:v', '1',
           '-lavfi', 'libvmaf=model=path=%s:n_threads=4:log_fmt=json:log_path=/dev/stdout' % MODEL, '-f', 'null', '-']
    return json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)['frames'][0]['metrics']['vmaf']
def psnr(a, b): return 10 * np.log10(1023.0 ** 2 / max(((a - b).astype(float) ** 2).mean(), 1e-9))
LO, HI = 0, 1023
A = '/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/'
TRAIN = [('cine_4k_A006', 2), ('cine_A005C021', 2), ('gfx444_F003C012', 3)]
TEST, ARM = sys.argv[1], sys.argv[2]; W, H = 1280, 720
cm = float(ARM.split('_')[0][2:]); CL = ARM.endswith('_cl')
LG = float([t[2:] for t in ARM.split('_') if t.startswith('lg')][0]) if '_lg' in ARM else 0  # luma-guided chroma interpolation
OUT = os.path.join(os.path.dirname(__file__), '..', 'out', 'rcl_fi'); os.makedirs(OUT, exist_ok=True)
def code_frame(planes, Q, SYS):
    Y = None; outs = []
    for pl, p in enumerate(planes):
        SY = []
        if pl == 0: y = po(p, Q, 0.7, 0, SY)[1]; Y = y
        else:
            Yd = (Y[:, 0::2] + Y[:, 1::2] + 1) >> 1 if (CL or LG) else None
            y = po(p, Q * cm, 0.7, 0, SY, Yd=Yd, LG=LG)[1]
        SYS.append((min(pl, 1), SY)); outs.append(y)
    return outs
src = A + TEST + '_1280x720_422_10.yuv'; x = read(src, W, H, 0)
f0 = os.path.join(OUT, TEST + '_src_f0.yuv')
if not os.path.exists(f0):
    with open(f0, 'wb') as fo:
        for p in x: p.astype('<u2').tofile(fo)
for e in range(-6, 26):
    Q = 2 ** (e / 4); tab = {}
    for clip, nf in TRAIN:
        for fr in range(nf):
            SYS = []; code_frame(read(A + clip + '_1280x720_422_10.yuv', W, H, fr), Q, SYS)
            for pl, SY in SYS: tally(SY, pl, tab)
    SYS = []; outs = code_frame(x, Q, SYS)
    bpp = sum(cost(SY, pl, tab) for pl, SY in SYS) / (W * H)
    if not 0.5 <= bpp < 4.6: continue
    fn = os.path.join(OUT, '%s_%s_%.3f.yuv' % (TEST, ARM, Q))
    with open(fn, 'wb') as fo:
        for p in outs: p.astype('<u2').tofile(fo)
    print('%s %s Q=%.3f bpp %.4f NEG %.3f PSNR %.2f/%.2f/%.2f oob %d' % (TEST, ARM, Q, bpp, neg1(f0, fn),
          *[psnr(o, p) for o, p in zip(outs, x)], sum(int(((o < LO) | (o > HI)).sum()) for o in outs)), flush=True)
    os.unlink(fn)
