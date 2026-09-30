#!/usr/bin/env python3
# rcl_intra.py — intra frame 0 at STATIC-TABLE code lengths (tables trained on the disjoint training clips under the
# exact configuration: same arm, same Q, same ladder, same context rule), then VMAF-NEG + PSNR Y/Cb/Cr.
# Code length per symbol = -log2 p_train(symbol | band key, 1-bit context), add-1 smoothing over |q| <= 63,
# escapes |q| > 63 cost 12 + 2*log2|q| bits. (Ideal static code; tANS at L = 1024 is within ~0.5 % of it.)
# Arms: W53 (integer 5/3, averaging reference) and N4 T in {0 (=PO), 1}; ladder f fixed per arm (best from the screen).
import sys, os, json, subprocess, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import d1_screen
from d1_screen import fwd, inv, dz, read, gains
from n4_core import po
d1_screen.GAINS = {}
LO, HI = 0, 1023
A = '/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/'
TRAIN = [('cine_4k_A006', 2), ('cine_A005C021', 2), ('gfx444_F003C012', 3)]
TEST = sys.argv[1]; W, H = 1280, 720; OUT = os.path.join(os.path.dirname(__file__), '..', 'out', 'rcl'); os.makedirs(OUT, exist_ok=True)
MODEL = '/home/user/fromscratch/OMC_CLOUD/vmaf_model/vmaf_v0.6.1neg.json'
def ctx(q):
    nz = q != 0; c = np.zeros_like(nz); c[:, 1:] |= nz[:, :-1]; c[1:, :] |= nz[:-1, :]; return c
def w53_syms(x, Q, SY):
    if x.shape not in d1_screen.GAINS: d1_screen.GAINS[x.shape] = gains(x.shape)
    ga, gb = d1_screen.GAINS[x.shape]; a, b = fwd(x); sa = max(1.0, Q / np.sqrt(ga)); qa = np.round(a / sa)
    dq = qa.copy(); dq[:, 1:] = qa[:, 1:] - qa[:, :-1]; dq[1:, 0] = qa[1:, 0] - qa[:-1, 0]; SY.append((('LL',), dq)); nb = []
    for i, ((k, bb), gg) in enumerate(zip(b, gb)):
        m = []
        for j, (c, g) in enumerate(zip(bb, gg)):
            s = max(1.0, Q / np.sqrt(g)); qc = dz(c, s); SY.append(((i, j), qc)); m.append(np.round(qc * s).astype(np.int64))
        nb.append((k, m))
    return np.clip(inv(np.round(qa * sa).astype(np.int64), nb), LO, HI)
def code(arm, x, Q, SY):
    if arm == 'W53': return w53_syms(x, Q, SY)
    T = {'PO': 0, 'N4t1': 1}[arm]; f = {'PO': 0.7, 'N4t1': 0.7}[arm]; return po(x, Q, f, T, SY)[1]
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
src = A + TEST + '_1280x720_422_10.yuv'; x = read(src, W, H, 0)
f0 = os.path.join(OUT, TEST + '_src_f0.yuv')
with open(f0, 'wb') as fo:
    for p in x: p.astype('<u2').tofile(fo)
for arm, Qs in (('W53', [2 ** (e / 4) for e in range(0, 30)]), ('PO', [2 ** (e / 4) for e in range(-4, 26)])):
    for Q in Qs:
        tab = {}
        for clip, nf in TRAIN:
            for fr in range(nf):
                for pl, p in enumerate(read(A + clip + '_1280x720_422_10.yuv', W, H, fr)):
                    SY = []; code(arm, p, Q, SY); tally(SY, min(pl, 1), tab)
        bits = 0.0; outs = []
        for pl, p in enumerate(x):
            SY = []; y = code(arm, p, Q, SY); bits += cost(SY, min(pl, 1), tab); outs.append(y)
        bpp = bits / (W * H)
        if not 0.4 < bpp < 4.6: continue
        fn = os.path.join(OUT, '%s_%s_%.3f.yuv' % (TEST, arm, Q))
        with open(fn, 'wb') as fo:
            for p in outs: p.astype('<u2').tofile(fo)
        print('%s %s Q=%.3f bpp %.4f NEG %.3f PSNR %.2f/%.2f/%.2f' % (TEST, arm, Q, bpp, neg1(f0, fn), *[psnr(o, p) for o, p in zip(outs, x)]), flush=True)
        os.unlink(fn)
