#!/usr/bin/env python3
# l2_intra.py : L2 (DESIGN H16) intra frame 0. Pass 1: cell index m = floor(x / S) on a fixed value lattice, coded
# losslessly by the T1 scan (step 1: symbol = m - MED(m), causal contexts; bits only). Pass 2 (no bits): the final
# value y = constrained smooth reconstruction from the whole m-image: start at cell centres, then NIT times
# {separable binomial low-pass (1,4,6,4,1)/16; clamp every sample to its own cell [mS, mS + S - 1]}; round.
# Rate knob: the integer lattice width S (per frame, one value). env NIT (8), CLIPS, RATES.
import os, sys, ctypes, json, subprocess, numpy as np
Dd = os.path.dirname(os.path.abspath(__file__)); ROOT = '/home/user/fromscratch/OMC_CLOUD/'
lib = ctypes.CDLL(os.path.join(Dd, 't1core.so')); IP = np.ctypeslib.ndpointer(np.int32, flags='C')
lib.t1_code.argtypes = [IP, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_double, ctypes.c_double, ctypes.c_int, ctypes.c_int, IP, IP, IP, ctypes.c_int, ctypes.c_double]
W, H = 1280, 720; NC = 16; K = 20; NIT = int(os.environ.get('NIT', '8'))
MODEL = ROOT + 'vmaf_model/vmaf_v0.6.1neg.json'; SCR = '/tmp/claude-0/-home-user-fromscratch/ca3365f6-68f7-5957-a3a2-a3df5f0ee7ba/scratchpad/'
def read(c, f=0):
    n = W * H * 2; a = np.fromfile(ROOT + 'Project/.work/arms/%s_1280x720_422_10.yuv' % c, '<u2', n, offset=f * n * 2).astype(np.int32)
    return [a[:W * H].reshape(H, W).copy(), a[W * H:W * H * 3 // 2].reshape(H, W // 2).copy(), a[W * H * 3 // 2:].reshape(H, W // 2).copy()]
def lossless(m):   # T1 scan at step 1 with rho 0.5 = exact integer coding of m
    m = np.ascontiguousarray(m, np.int32); h, w = m.shape; out = np.zeros_like(m); q = np.zeros_like(m); cl = np.zeros_like(m)
    lib.t1_code(m, None, h, w, 1.0, 0.5, -10 ** 6, 10 ** 6, out, q, cl, NC, 1.0); assert (out == m).all(); return q, cl
def lp(a):
    k = np.array([1, 4, 6, 4, 1]) / 16.0
    p = np.pad(a, ((0, 0), (2, 2)), mode='edge'); a = sum(k[i] * p[:, i:i + a.shape[1]] for i in range(5))
    p = np.pad(a, ((2, 2), (0, 0)), mode='edge'); return sum(k[i] * p[i:i + a.shape[0]] for i in range(5))
def recon(m, S):
    lo = m * S; hi = np.minimum(lo + S - 1, 1023); y = (lo + hi) / 2.0
    for _ in range(NIT): y = np.clip(lp(y), lo, hi)
    return np.round(y).astype(np.int32)
def sym(q): a = np.abs(q); return np.where(a > K, 2 * K + 1, np.where(q > 0, 2 * a - 1, 2 * a)), a
def eg_bits(a): return np.where(a > K, 2 * np.floor(np.log2(np.maximum(a - K + 1, 1))) + 1, 0)
SS = list(range(2, 129))
tp = os.path.join(Dd, 'l2_tables.npy')
if os.path.exists(tp): T = np.load(tp)
else:
    cnt = np.ones((NC, 2 * K + 2))
    for c in ('cine_4k_A006', 'cine_A005C021', 'gfx444_F003C012'):
        for p in read(c):
            for S in (4, 6, 8, 12, 16, 24, 32, 48, 64, 96):
                q, cl = lossless(p // S); sm, _ = sym(q); np.add.at(cnt, (cl.ravel(), sm.ravel()), 1)
    T = -np.log2(cnt / cnt.sum(1, keepdims=True)); np.save(tp, T)
def frame(x, S):
    ys, b = [], 0.0
    for p in x:
        m = p // S; q, cl = lossless(m); b += float(T[cl, sym(q)[0]].sum() + eg_bits(np.abs(q)).sum()); ys.append(recon(m, S))
    return ys, b
def vmaf1(dec, src):
    fs = []
    for nm, fr in (('d', dec), ('s', src)):
        fn = SCR + 'l2_%s_%d.yuv' % (nm, os.getpid()); fs.append(fn)
        with open(fn, 'wb') as fo:
            for p in fr: p.astype('<u2').tofile(fo)
    cmd = ['ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'yuv422p10le', '-s', '%dx%d' % (W, H), '-i', fs[0], '-f', 'rawvideo',
           '-pix_fmt', 'yuv422p10le', '-s', '%dx%d' % (W, H), '-i', fs[1], '-frames:v', '1', '-lavfi', 'libvmaf=model=path=%s:log_fmt=json:log_path=/dev/stdout' % MODEL, '-f', 'null', '-']
    return json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)['frames'][0]['metrics']['vmaf']
def psnr(a, b): return 10 * np.log10(1023 ** 2 / ((a.astype(float) - b) ** 2).mean())
for c in os.environ.get('CLIPS', 'cine_A005C031,gfx444_B001C001,prores_sample').split(','):
    x = read(c)
    for R in [float(r) for r in os.environ.get('RATES', '0.5,1.0,2.0').split(',')]:
        lo, hi, best = 0, len(SS) - 1, None
        while lo <= hi:   # smallest S (finest lattice) whose bits fit
            mid = (lo + hi) // 2; ys, b = frame(x, SS[mid])
            if b <= R * W * H: best = (SS[mid], ys, b); hi = mid - 1
            else: lo = mid + 1
        S, ys, b = best
        n = W * H * 2; ta = np.fromfile(ROOT + 'scratch/today/%s_1280x720_b%s.d.yuv' % (c, R), '<u2', n).astype(np.int32)
        t = [ta[:W * H].reshape(H, W), ta[W * H:W * H * 3 // 2].reshape(H, W // 2), ta[W * H * 3 // 2:].reshape(H, W // 2)]
        print('%s @%.1f S %d bpp %.3f | NEG %.2f vs today %.2f (%+.2f) | PSNR %s vs today %s | max|err| %d' % (c, R, S, b / (W * H), vmaf1(ys, x), vmaf1(t, x),
              vmaf1(ys, x) - vmaf1(t, x), '/'.join('%.2f' % psnr(o, p) for o, p in zip(ys, x)), '/'.join('%.2f' % psnr(o, p) for o, p in zip(t, x)),
              max(int(np.abs(o - p).max()) for o, p in zip(ys, x))), flush=True)
