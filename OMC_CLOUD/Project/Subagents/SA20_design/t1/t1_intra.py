#!/usr/bin/env python3
# t1_intra.py : T1 core (DESIGN §H) intra frame 0 at the owner rates vs today's frame 0 (and phase/streak statistics).
# Static tables: 16 classes x symbols |q| <= K (+ escape, Exp-Golomb tail), trained on the training clips' frame 0,
# pooled over the step grid and the three planes (S16-style). Ideal static code length; no headers.
# env RHO (leaf rounding offset, default 0.42), CLIPS, RATES.
import os, sys, ctypes, json, subprocess, numpy as np
D = os.path.dirname(os.path.abspath(__file__)); ROOT = '/home/user/fromscratch/OMC_CLOUD/'
lib = ctypes.CDLL(os.path.join(D, 't1core.so')); IP = np.ctypeslib.ndpointer(np.int32, flags='C')
lib.t1_code.argtypes = [IP, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_double, ctypes.c_double, ctypes.c_int, ctypes.c_int, IP, IP, IP, ctypes.c_int, ctypes.c_double]
W, H = 1280, 720; NC = 16; K = 20; RHO = float(os.environ.get('RHO', '0.42')); ALPHA = 1.0
GRID = [2 ** (e / 4) for e in range(-4, 28)]
MODEL = ROOT + 'vmaf_model/vmaf_v0.6.1neg.json'
def read(c, f=0):
    n = W * H * 2; a = np.fromfile(ROOT + 'Project/.work/arms/%s_1280x720_422_10.yuv' % c, '<u2', n, offset=f * n * 2).astype(np.int32)
    return [a[:W * H].reshape(H, W).copy(), a[W * H:W * H * 3 // 2].reshape(H, W // 2).copy(), a[W * H * 3 // 2:].reshape(H, W // 2).copy()]
def code(p, s, P=None):
    h, w = p.shape; out = np.zeros_like(p); q = np.zeros_like(p); cl = np.zeros_like(p)
    lib.t1_code(np.ascontiguousarray(p), None if P is None else np.ascontiguousarray(P).ctypes.data, h, w, s, RHO, 0, 1023, out, q, cl, NC, ALPHA)
    return out, q, cl
def sym(q): a = np.abs(q); return np.where(a > K, 2 * K + 1, np.where(q > 0, 2 * a - 1, 2 * a)), a
def eg_bits(a): return np.where(a > K, 2 * np.floor(np.log2(a - K + 1)) + 1, 0)
TR = [('cine_4k_A006', 0), ('cine_A005C021', 0), ('gfx444_F003C012', 0)]
tp = os.path.join(D, 'tables_rho%.2f.npy' % RHO)
if os.path.exists(tp): T = np.load(tp)
else:
    cnt = np.ones((NC, 2 * K + 2))
    for c, f in TR:
        for p in read(c, f):
            for s in GRID[4:]:
                _, q, cl = code(p, s); sm, _ = sym(q); np.add.at(cnt, (cl.ravel(), sm.ravel()), 1)
    T = -np.log2(cnt / cnt.sum(1, keepdims=True)); np.save(tp, T)
def bits(q, cl): sm, a = sym(q); return float(T[cl, sm].sum() + eg_bits(a).sum())
CM = float(os.environ.get("CM", "1.0"))   # chroma step multiplier
def frame(x, s): r = [code(p, s * (CM if k else 1.0)) for k, p in enumerate(x)]; return [o for o, _, _ in r], sum(bits(q, cl) for _, q, cl in r)
def vmaf1(dec, src):
    fs = []
    for nm, fr in (('d', dec), ('s', src)):
        fn = '/tmp/claude-0/-home-user-fromscratch/ca3365f6-68f7-5957-a3a2-a3df5f0ee7ba/scratchpad/t1_%s.yuv' % nm; fs.append(fn)
        with open(fn, 'wb') as fo:
            for p in fr: p.astype('<u2').tofile(fo)
    cmd = ['ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'yuv422p10le', '-s', '%dx%d' % (W, H), '-i', fs[0], '-f', 'rawvideo',
           '-pix_fmt', 'yuv422p10le', '-s', '%dx%d' % (W, H), '-i', fs[1], '-frames:v', '1', '-lavfi', 'libvmaf=model=path=%s:log_fmt=json:log_path=/dev/stdout' % MODEL, '-f', 'null', '-']
    return json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)['frames'][0]['metrics']['vmaf']
def psnr(a, b): return 10 * np.log10(1023 ** 2 / ((a.astype(float) - b) ** 2).mean())
def phase(e, px): pc = [e[:, k::px].mean() for k in range(px)]; pr = [e[k::4].mean() for k in range(4)]; return max(pc) / min(pc), max(pr) / min(pr)
def aniso(s):   # lag-1 autocorrelation of the signed error, horizontal / vertical (streak test: 1.00 = isotropic)
    s = s - s.mean(); v = (s * s).mean(); return (s[:, 1:] * s[:, :-1]).mean() / v, (s[1:] * s[:-1]).mean() / v
for c in os.environ.get('CLIPS', 'cine_A005C031,gfx444_B001C001,prores_sample').split(','):
    x = read(c)
    for R in [float(r) for r in os.environ.get('RATES', '0.5,1.0,1.5,2.0,2.5,3.0,4.0').split(',')]:
        lo, hi, best = 0, len(GRID) - 1, None
        while lo <= hi:
            m = (lo + hi) // 2; y, b = frame(x, GRID[m])
            if b <= R * W * H: best = (GRID[m], y, b); hi = m - 1
            else: lo = m + 1
        s, y, b = best
        t = [p.astype(np.int32) for p in read_t(c, R)] if False else None
        n = W * H * 2; ta = np.fromfile(ROOT + 'scratch/today/%s_1280x720_b%s.d.yuv' % (c, R), '<u2', n).astype(np.int32)
        t = [ta[:W * H].reshape(H, W), ta[W * H:W * H * 3 // 2].reshape(H, W // 2), ta[W * H * 3 // 2:].reshape(H, W // 2)]
        ng, ngt = vmaf1(y, x), vmaf1(t, x)
        ph = [phase(np.abs(o - p), 32 if k == 0 else 16) for k, (o, p) in enumerate(zip(y, x))]
        an = [aniso((o - p).astype(float)) for o, p in zip(y, x)]
        print('%s @%.1f step %.2f bpp %.3f | NEG %.2f vs today %.2f (%+.2f) | PSNR %s vs today %s | colphase %s rowphase %s | lag1 h/v %s' % (
            c, R, s, b / (W * H), ng, ngt, ng - ngt, '/'.join('%.2f' % psnr(o, p) for o, p in zip(y, x)), '/'.join('%.2f' % psnr(o, p) for o, p in zip(t, x)),
            '/'.join('%.2f' % v[0] for v in ph), '/'.join('%.2f' % v[1] for v in ph), ' '.join('%.2f/%.2f' % v for v in an)), flush=True)
