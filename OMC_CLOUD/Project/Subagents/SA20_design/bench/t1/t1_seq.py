#!/usr/bin/env python3
# t1_seq.py : G-b test (DESIGN H10). The same per-sample process in every frame:
#   frame 0: T1 intra (causal MED, one quantiser everywhere);
#   frames 1..: final = clip(P + round(ALPHA x MED(residual of L, U, UL)) + leaf), P = the previous DECODED frame warped
#   by a per-sample vector field (vectors found per 16x16 area, placed at the area centres, bilinearly interpolated to
#   every sample; the reference is sampled bilinearly at the fractional position). No block edge touches a sample.
# Static tables: intra (T1) and inter, trained on the training clips (closed loop, several steps). Per-frame CBR:
# finest step on a 1/16-octave list whose bits fit R x W x H (+ 10 bits per vector node on inter frames).
# Reports per-frame NEG and PSNR vs today's decode of the same clip at the same rate, and error lag-1 correlations
# (h, v, and both diagonals) on the last frame. env ALPHA (0 or 1), RHO, CM, CLIPS, RATES.
import os, sys, ctypes, json, subprocess, numpy as np
Dd = os.path.dirname(os.path.abspath(__file__)); ROOT = '/home/user/fromscratch/OMC_CLOUD/'
sys.path.insert(0, os.path.join(Dd, '..')); from dp_screen_core import motion
lib = ctypes.CDLL(os.path.join(Dd, 't1core.so')); IP = np.ctypeslib.ndpointer(np.int32, flags='C')
lib.t1_code.argtypes = [IP, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_double, ctypes.c_double, ctypes.c_int, ctypes.c_int, IP, IP, IP, ctypes.c_int, ctypes.c_double]
W, H = 1280, 720; NC = 16; K = 20; NF = 3
ALPHA = float(os.environ.get('ALPHA', '1.0')); RHO = float(os.environ.get('RHO', '0.42')); CM = float(os.environ.get('CM', '1.0'))
GRID = [2 ** (e / 16) for e in range(-16, 112)]; MODEL = ROOT + 'vmaf_model/vmaf_v0.6.1neg.json'
SCR = '/tmp/claude-0/-home-user-fromscratch/ca3365f6-68f7-5957-a3a2-a3df5f0ee7ba/scratchpad/'
def read(c, f):
    n = W * H * 2; a = np.fromfile(ROOT + 'Project/.work/arms/%s_1280x720_422_10.yuv' % c, '<u2', n, offset=f * n * 2).astype(np.int32)
    return [a[:W * H].reshape(H, W).copy(), a[W * H:W * H * 3 // 2].reshape(H, W // 2).copy(), a[W * H * 3 // 2:].reshape(H, W // 2).copy()]
def nframes(c): return min(NF, os.path.getsize(ROOT + 'Project/.work/arms/%s_1280x720_422_10.yuv' % c) // (W * H * 4))
def code(p, s, P=None):
    p = np.ascontiguousarray(p, np.int32); h, w = p.shape; out = np.zeros_like(p); q = np.zeros_like(p); cl = np.zeros_like(p)
    Pc = None if P is None else np.ascontiguousarray(P, np.int32)
    lib.t1_code(p, None if Pc is None else Pc.ctypes.data, h, w, s, RHO, 0, 1023, out, q, cl, NC, ALPHA if P is not None else 1.0)
    return out, q, cl
def field(v, shp, bw):   # node values at area centres -> bilinear per-sample field (clamped beyond the outer centres)
    def ax(n, B, nb):
        c = np.clip((np.arange(n) + 0.5) / B - 0.5, 0, nb - 1); i0 = np.minimum(np.floor(c).astype(int), nb - 2) if nb > 1 else np.zeros(n, int)
        return i0, np.minimum(i0 + 1, nb - 1), c - i0
    r0, r1, fr = ax(shp[0], 16, v.shape[0]); c0, c1, fc = ax(shp[1], bw, v.shape[1])
    t = v[r0][:, c0] * (1 - fc) + v[r0][:, c1] * fc; b = v[r1][:, c0] * (1 - fc) + v[r1][:, c1] * fc
    return t * (1 - fr[:, None]) + b * fr[:, None]
def warp(ref, vy, vx):   # bilinear sample of ref at (y + vy, x + vx), edge-clamped
    h, w = ref.shape; yy = np.clip(np.arange(h)[:, None] + vy, 0, h - 1); xx = np.clip(np.arange(w)[None, :] + vx, 0, w - 1)
    y0 = np.minimum(np.floor(yy).astype(int), h - 2); x0 = np.minimum(np.floor(xx).astype(int), w - 2); fy = yy - y0; fx = xx - x0
    r = ref.astype(float)
    v = r[y0, x0] * (1 - fy) * (1 - fx) + r[y0, x0 + 1] * (1 - fy) * fx + r[y0 + 1, x0] * fy * (1 - fx) + r[y0 + 1, x0 + 1] * fy * fx
    return np.round(v).astype(np.int32)
def predict(x, ref):
    V = motion(x[0].astype(np.int64), ref[0].astype(np.int64))[:H // 16, :W // 16].astype(float)
    vy = field(V[:, :, 0], (H, W), 16); vx = field(V[:, :, 1], (H, W), 16)
    vyc = field(V[:, :, 0], (H, W // 2), 8); vxc = field(V[:, :, 1] / 2, (H, W // 2), 8)
    return [warp(ref[0], vy, vx), warp(ref[1], vyc, vxc), warp(ref[2], vyc, vxc)], V.shape[0] * V.shape[1]
def sym(q): a = np.abs(q); return np.where(a > K, 2 * K + 1, np.where(q > 0, 2 * a - 1, 2 * a)), a
def eg_bits(a): return np.where(a > K, 2 * np.floor(np.log2(np.maximum(a - K + 1, 1))) + 1, 0)
def frame(x, s, Ps):
    ys, parts = [], []
    for k, p in enumerate(x):
        y, q, cl = code(p, s * (CM if k else 1.0), None if Ps is None else Ps[k]); ys.append(y); parts.append((q, cl))
    return ys, parts
TR = ['cine_4k_A006', 'cine_A005C021', 'gfx444_F003C012']
tp = os.path.join(Dd, 'seq_tables_A%.1f_rho%.2f_cm%.1f.npy' % (ALPHA, RHO, CM))
if os.path.exists(tp): T = np.load(tp)
else:
    cnt = np.ones((2, NC, 2 * K + 2))
    for c in TR:
        X = [read(c, f) for f in range(nframes(c))]
        for s in GRID[16::8]:
            ref = None
            for t, x in enumerate(X):
                Ps = None if ref is None else predict(x, ref)[0]; ys, parts = frame(x, s, Ps)
                for q, cl in parts: sm, _ = sym(q); np.add.at(cnt[1 if t else 0], (cl.ravel(), sm.ravel()), 1)
                ref = ys
    T = -np.log2(cnt / cnt.sum(2, keepdims=True)); np.save(tp, T)
def bits(parts, role): return sum(float(T[role][cl, sym(q)[0]].sum() + eg_bits(np.abs(q)).sum()) for q, cl in parts)
def vmaf(dec, src, n):
    fs = []
    for nm, frs in (('d', dec), ('s', src)):
        fn = SCR + 'seq_%s_%d.yuv' % (nm, os.getpid()); fs.append(fn)
        with open(fn, 'wb') as fo:
            for fr in frs:
                for p in fr: p.astype('<u2').tofile(fo)
    cmd = ['ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'yuv422p10le', '-s', '%dx%d' % (W, H), '-i', fs[0], '-f', 'rawvideo',
           '-pix_fmt', 'yuv422p10le', '-s', '%dx%d' % (W, H), '-i', fs[1], '-frames:v', str(n), '-lavfi', 'libvmaf=model=path=%s:log_fmt=json:log_path=/dev/stdout' % MODEL, '-f', 'null', '-']
    return [f['metrics']['vmaf'] for f in json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)['frames']]
def psnr(a, b): return 10 * np.log10(1023 ** 2 / ((a.astype(float) - b) ** 2).mean())
def lag(s):
    s = s - s.mean(); v = (s * s).mean()
    return [(s[:, 1:] * s[:, :-1]).mean() / v, (s[1:] * s[:-1]).mean() / v, (s[1:, 1:] * s[:-1, :-1]).mean() / v, (s[1:, :-1] * s[:-1, 1:]).mean() / v]
for c in os.environ.get('CLIPS', 'cine_A005C031,gfx444_B001C001,prores_sample').split(','):
    n = nframes(c); X = [read(c, f) for f in range(n)]
    for R in [float(r) for r in os.environ.get('RATES', '0.5,1.0,2.0').split(',')]:
        ref = None; rec = []; info = []
        for t, x in enumerate(X):
            Ps, nn = (None, 0) if ref is None else predict(x, ref); lo, hi, best = 0, len(GRID) - 1, None
            while lo <= hi:
                m = (lo + hi) // 2; ys, parts = frame(x, GRID[m], Ps); b = bits(parts, 1 if t else 0) + 10 * nn
                if b <= R * W * H: best = (GRID[m], ys, b); hi = m - 1
                else: lo = m + 1
            s, ys, b = best; rec.append(ys); info.append((s, b / (W * H))); ref = ys
        nb = W * H * 2; ta = np.fromfile(ROOT + 'scratch/today/%s_1280x720_b%s.d.yuv' % (c, R), '<u2').astype(np.int32)
        tod = [[ta[f * nb:f * nb + W * H].reshape(H, W), ta[f * nb + W * H:f * nb + W * H * 3 // 2].reshape(H, W // 2), ta[f * nb + W * H * 3 // 2:(f + 1) * nb].reshape(H, W // 2)] for f in range(n)]
        ng, ngt = vmaf(rec, X, n), vmaf(tod, X, n); L_ = n - 1
        lg = lag((rec[L_][0] - X[L_][0]).astype(float))
        print('%s @%.1f steps %s bpp %s | NEG %s vs today %s | last %+.2f | PSNR last %s vs today %s | Y err lag1 h %.2f v %.2f d %.2f a %.2f' % (
            c, R, '/'.join('%.2f' % s for s, _ in info), '/'.join('%.3f' % b for _, b in info), '/'.join('%.2f' % v for v in ng), '/'.join('%.2f' % v for v in ngt),
            ng[L_] - ngt[L_], '/'.join('%.2f' % psnr(o, p) for o, p in zip(rec[L_], X[L_])), '/'.join('%.2f' % psnr(o, p) for o, p in zip(tod[L_], X[L_])), *lg), flush=True)
