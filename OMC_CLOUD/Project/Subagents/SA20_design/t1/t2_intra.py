#!/usr/bin/env python3
# t2_intra.py : T2 core (DESIGN §H6) intra frame 0. Auxiliary coarse signal A = D x D block means of each plane (not
# output samples), coded by the T1 scan at step KA x s; decoder upsamples the decoded A with a separable Keys cubic
# (nodes at block centres) to U. Every output sample: final = clip(U + round(ALPHA x MED(detail of L, U, UL)) + leaf),
# the same process at every position. Static tables per role (aux / main), trained on the training clips' frame 0.
# env D (4), KA (0.5), ALPHA (0.5), RHO (0.42), CM (1.0), CLIPS, RATES.
import os, sys, ctypes, json, subprocess, numpy as np
Dd = os.path.dirname(os.path.abspath(__file__)); ROOT = '/home/user/fromscratch/OMC_CLOUD/'
lib = ctypes.CDLL(os.path.join(Dd, 't1core.so')); IP = np.ctypeslib.ndpointer(np.int32, flags='C')
lib.t1_code.argtypes = [IP, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_double, ctypes.c_double, ctypes.c_int, ctypes.c_int, IP, IP, IP, ctypes.c_int, ctypes.c_double]
W, H = 1280, 720; NC = 16; K = 20
D = int(os.environ.get('D', '4')); KA = float(os.environ.get('KA', '0.5')); ALPHA = float(os.environ.get('ALPHA', '0.5'))
RHO = float(os.environ.get('RHO', '0.42')); CM = float(os.environ.get('CM', '1.0'))
GRID = [2 ** (e / 16) for e in range(-16, 112)]; MODEL = ROOT + 'vmaf_model/vmaf_v0.6.1neg.json'
def read(c, f=0):
    n = W * H * 2; a = np.fromfile(ROOT + 'Project/.work/arms/%s_1280x720_422_10.yuv' % c, '<u2', n, offset=f * n * 2).astype(np.int32)
    return [a[:W * H].reshape(H, W).copy(), a[W * H:W * H * 3 // 2].reshape(H, W // 2).copy(), a[W * H * 3 // 2:].reshape(H, W // 2).copy()]
def code(p, s, P=None, alpha=1.0):
    p = np.ascontiguousarray(p, np.int32); h, w = p.shape; out = np.zeros_like(p); q = np.zeros_like(p); cl = np.zeros_like(p)
    Pc = None if P is None else np.ascontiguousarray(P, np.int32)
    lib.t1_code(p, None if Pc is None else Pc.ctypes.data, h, w, s, RHO, 0, 1023, out, q, cl, NC, alpha)
    return out, q, cl
def keys_w(n_out, n_in, D):   # cubic (Keys a = -0.5) weights: output sample i sits at node coordinate (i + 0.5) / D - 0.5
    c = (np.arange(n_out) + 0.5) / D - 0.5; i0 = np.floor(c).astype(int); t = c - i0
    def k(x):
        x = np.abs(x); return np.where(x <= 1, 1.5 * x ** 3 - 2.5 * x ** 2 + 1, np.where(x < 2, -0.5 * x ** 3 + 2.5 * x ** 2 - 4 * x + 2, 0))
    idx = np.stack([np.clip(i0 + o, 0, n_in - 1) for o in (-1, 0, 1, 2)], 1); wt = np.stack([k(t - o) for o in (-1, 0, 1, 2)], 1)
    return idx, wt
def upsample(a, shp):
    iy, wy = keys_w(shp[0], a.shape[0], D); ix, wx = keys_w(shp[1], a.shape[1], D)
    r = (a[iy] * wy[:, :, None]).sum(1); r = (r[:, ix] * wx[None]).sum(2); return np.clip(np.round(r), 0, 1023).astype(np.int32)
def aux(p): h, w = p.shape; return np.round(p.reshape(h // D, D, w // D, D).mean(axis=(1, 3))).astype(np.int32)
def sym(q): a = np.abs(q); return np.where(a > K, 2 * K + 1, np.where(q > 0, 2 * a - 1, 2 * a)), a
def eg_bits(a): return np.where(a > K, 2 * np.floor(np.log2(np.maximum(a - K + 1, 1))) + 1, 0)
def plane(p, s):   # -> final, [(role, q, cls)]
    ya, qa, ca = code(aux(p), s * KA); U = upsample(ya, p.shape); y, q, c = code(p, s, U, ALPHA); return y, [(0, qa, ca), (1, q, c)]
TR = ['cine_4k_A006', 'cine_A005C021', 'gfx444_F003C012']
tp = os.path.join(Dd, 't2_tables_D%d_KA%.2f_A%.2f_rho%.2f.npy' % (D, KA, ALPHA, RHO))
if os.path.exists(tp): T = np.load(tp)
else:
    cnt = np.ones((2, NC, 2 * K + 2))
    for c in TR:
        for p in read(c):
            for s in GRID[16::4]:
                for role, q, cl in plane(p, s)[1]: sm, _ = sym(q); np.add.at(cnt[role], (cl.ravel(), sm.ravel()), 1)
    T = -np.log2(cnt / cnt.sum(2, keepdims=True)); np.save(tp, T)
def bits(parts): return sum(float(T[r][cl, sym(q)[0]].sum() + eg_bits(np.abs(q)).sum()) for r, q, cl in parts)
def frame(x, s):
    ys, b = [], 0.0
    for k, p in enumerate(x): y, parts = plane(p, s * (CM if k else 1.0)); ys.append(y); b += bits(parts)
    return ys, b
def vmaf1(dec, src):
    fs = []
    for nm, fr in (('d', dec), ('s', src)):
        fn = '/tmp/claude-0/-home-user-fromscratch/ca3365f6-68f7-5957-a3a2-a3df5f0ee7ba/scratchpad/t2_%s_%d.yuv' % (nm, os.getpid()); fs.append(fn)
        with open(fn, 'wb') as fo:
            for p in fr: p.astype('<u2').tofile(fo)
    cmd = ['ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'yuv422p10le', '-s', '%dx%d' % (W, H), '-i', fs[0], '-f', 'rawvideo',
           '-pix_fmt', 'yuv422p10le', '-s', '%dx%d' % (W, H), '-i', fs[1], '-frames:v', '1', '-lavfi', 'libvmaf=model=path=%s:log_fmt=json:log_path=/dev/stdout' % MODEL, '-f', 'null', '-']
    return json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)['frames'][0]['metrics']['vmaf']
def psnr(a, b): return 10 * np.log10(1023 ** 2 / ((a.astype(float) - b) ** 2).mean())
def phase(e, px, py): pc = [e[:, k::px].mean() for k in range(px)]; pr = [e[k::py].mean() for k in range(py)]; return max(pc) / min(pc), max(pr) / min(pr)
def aniso(s): s = s - s.mean(); v = (s * s).mean(); return (s[:, 1:] * s[:, :-1]).mean() / v, (s[1:] * s[:-1]).mean() / v
for c in os.environ.get('CLIPS', 'cine_A005C031,gfx444_B001C001,prores_sample').split(','):
    x = read(c)
    for R in [float(r) for r in os.environ.get('RATES', '0.5,1.0').split(',')]:
        lo, hi, best = 0, len(GRID) - 1, None
        while lo <= hi:
            m = (lo + hi) // 2; y, b = frame(x, GRID[m])
            if b <= R * W * H: best = (GRID[m], y, b); hi = m - 1
            else: lo = m + 1
        s, y, b = best
        n = W * H * 2; ta = np.fromfile(ROOT + 'scratch/today/%s_1280x720_b%s.d.yuv' % (c, R), '<u2', n).astype(np.int32)
        t = [ta[:W * H].reshape(H, W), ta[W * H:W * H * 3 // 2].reshape(H, W // 2), ta[W * H * 3 // 2:].reshape(H, W // 2)]
        ng, ngt = vmaf1(y, x), vmaf1(t, x)
        ph = [phase(np.abs(o - p), D, D) for o, p in zip(y, x)]; an = [aniso((o - p).astype(float)) for o, p in zip(y, x)]
        print('%s @%.1f step %.2f bpp %.3f | NEG %.2f vs today %.2f (%+.2f) | PSNR %s | phase%d col %s row %s | lag1 h/v %s' % (
            c, R, s, b / (W * H), ng, ngt, ng - ngt, '/'.join('%.2f' % psnr(o, p) for o, p in zip(y, x)), D,
            '/'.join('%.2f' % v[0] for v in ph), '/'.join('%.2f' % v[1] for v in ph), ' '.join('%.2f/%.2f' % v for v in an)), flush=True)
