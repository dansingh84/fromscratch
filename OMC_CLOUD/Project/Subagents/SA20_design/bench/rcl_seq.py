#!/usr/bin/env python3
# rcl_seq.py CLIP ARM — form (i) end to end over 3 frames at STATIC-TABLE code lengths:
#   frame 0 intra = private-leaf pyramid (P = 0); frames 1-2 inter = private-leaf pyramid of x - P, P = block MC of the
#   engine's own previous reconstruction (16x16, +-8, chroma x halved), out = clip(P + pred + leaf) per sample.
#   Vector bits charged at 10 bits per 16x16 block (conservative stand-in for coded vector differences).
# Tables trained on the 3 disjoint training clips (all their frames, same arm/Q/config), keyed (plane class, intra/inter,
# band, 1-bit context). ARM = "cm<mult>[_cl]" as in rcl_fi.py. Rate = mean bits per frame / luma samples.
# Prints mean bpp, per-frame bpp, frame-2 NEG (3-frame run) and frame-2 PSNR Y/Cb/Cr. Summarise with seq_vs_today.py.
import sys, os, json, subprocess, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from d1_screen import read
from n4_core import po
from dp_screen_core import motion, apply
LO, HI = 0, 1023; W, H = 1280, 720
A = '/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/'
MODEL = '/home/user/fromscratch/OMC_CLOUD/vmaf_model/vmaf_v0.6.1neg.json'
TRAIN = [('cine_4k_A006', 2), ('cine_A005C021', 2), ('gfx444_F003C012', 3)]
TEST, ARM = sys.argv[1], sys.argv[2]
cm = float(ARM.split('_')[0][2:]); CL = ARM.endswith('_cl')
OUT = os.path.join(os.path.dirname(__file__), '..', 'out', 'rcl_seq'); os.makedirs(OUT, exist_ok=True)
def ctx(q):
    nz = q != 0; c = np.zeros_like(nz); c[:, 1:] |= nz[:, :-1]; c[1:, :] |= nz[:-1, :]; return c
def tally(SY, key0, tab):
    for key, q in SY:
        c = ctx(q); q = q.astype(np.int64)
        for cc in (0, 1):
            v = np.clip(q[c == cc], -64, 64); h = tab.setdefault(key0 + key + (cc,), np.zeros(129)); np.add.at(h, v + 64, 1)
def cost(SY, key0, tab):
    bits = 0.0
    for key, q in SY:
        c = ctx(q); q = q.astype(np.int64)
        for cc in (0, 1):
            v = q[c == cc]; h = tab.get(key0 + key + (cc,), np.zeros(129)) + 1; p = h / h.sum()
            bits += -np.log2(p[np.clip(v, -64, 64) + 64]).sum(); esc = np.abs(v) > 63; bits += (12 + 2 * np.log2(np.abs(v[esc]))).sum()
    return bits
def code_seq(frames, Q):
    """returns per frame: list of (key0, SY) and reconstruction"""
    rec = []; allsy = []
    for t, x in enumerate(frames):
        if t == 0: Ps = [np.zeros_like(p) for p in x]
        else:
            V = motion(x[0], rec[-1][0]); Ps = [apply(rec[-1][0], V, 16, 1), apply(rec[-1][1], V, 16, 2), apply(rec[-1][2], V, 16, 2)]
        out = []; sy = []; mode = 'intra' if t == 0 else 'inter'
        for pl, (p, P) in enumerate(zip(x, Ps)):
            SY = []
            if pl == 0:
                _, ye = po_res(p, P, Q, SY, None)
            else:
                Yd = None
                if CL:
                    Yf = out[0]; Yd = (Yf[:, 0::2] + Yf[:, 1::2] + 1) >> 1
                    Yd = Yd - ((Ps[0][:, 0::2] + Ps[0][:, 1::2] + 1) >> 1)   # luma detail in the same (residual) domain
                _, ye = po_res(p, P, Q * cm, SY, Yd)
            out.append(ye); sy.append(((min(pl, 1), mode), SY))
        rec.append(out); allsy.append(sy)
    return allsy, rec
def po_res(x, P, Q, SY, Yd):
    # the pyramid codes r = x - P; every sample's final value is clip(P + r^) (per-sample, private last write)
    return po(x, Q, 0.7, 0, SY, Yd=Yd, P=P)
def neg3(src3, dec):
    cmd = ['ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'yuv422p10le', '-s', '%dx%d' % (W, H), '-i', dec,
           '-f', 'rawvideo', '-pix_fmt', 'yuv422p10le', '-s', '%dx%d' % (W, H), '-i', src3, '-frames:v', '3',
           '-lavfi', '[0:v]trim=end_frame=3[d];[1:v]trim=end_frame=3[r];[d][r]libvmaf=model=path=%s:n_threads=4:log_fmt=json:log_path=/dev/stdout' % MODEL,
           '-f', 'null', '-']
    return [f['metrics']['vmaf'] for f in json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)['frames']]
def psnr(a, b): return 10 * np.log10(1023.0 ** 2 / max(((a - b).astype(float) ** 2).mean(), 1e-9))
src = A + TEST + '_1280x720_422_10.yuv'; X = [read(src, W, H, f) for f in range(3)]
for e in range(-6, 26):
    Q = 2 ** (e / 4); tab = {}
    for clip, nf in TRAIN:
        allsy, _ = code_seq([read(A + clip + '_1280x720_422_10.yuv', W, H, f) for f in range(nf)], Q)
        for sy in allsy:
            for key0, SY in sy: tally(SY, key0, tab)
    allsy, rec = code_seq(X, Q)
    nblk = ((H + 15) // 16) * ((W + 15) // 16)
    fb = [sum(cost(SY, key0, tab) for key0, SY in sy) + (10 * nblk if t else 0) for t, sy in enumerate(allsy)]
    bpp = np.mean(fb) / (W * H)
    if not 0.5 <= bpp < 4.6: continue
    fn = os.path.join(OUT, '%s_%s_%.3f.yuv' % (TEST, ARM, Q))
    with open(fn, 'wb') as fo:
        for fr in rec:
            for p in fr: p.astype('<u2').tofile(fo)
    ng = neg3(src, fn); oob = sum(int(((p < LO) | (p > HI)).sum()) for fr in rec for p in fr)
    print('%s %s Q=%.3f bpp %.4f f0/f1/f2 %s NEG f2 %.3f (f0 %.2f f1 %.2f) PSNR f2 %.2f/%.2f/%.2f oob %d' % (
        TEST, ARM, Q, bpp, '/'.join('%.3f' % (b / (W * H)) for b in fb), ng[2], ng[0], ng[1],
        *[psnr(o, p) for o, p in zip(rec[2], X[2])], oob), flush=True)
    os.unlink(fn)
