#!/usr/bin/env python3
# rcl_s16.py CLIP CM [CTX] — intra frame 0 under the S16 step-invariant entropy model (16 tables shared by every step,
# level and plane), with real static-table code lengths, NEG and PSNR per plane (rcl_fi output format, so
# intra_vs_today.py scores it). CTX: 'S16' = |q| neighbours (left, up, half diagonals) + step-normalised activity;
# 'S16i' = indices only; 'S16u' = indices from the row ABOVE only (no left: no per-symbol loop in a lane).
# Tables: trained on the TRAIN clips minus CLIP (leave-one-out when CLIP is a training clip), all steps pooled.
# Also prints the escape share (|q| > 63) per step.
import sys, os, json, subprocess, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from d1_screen import read
from n4_core import po
W, H = 1280, 720; LO, HI = 0, 1023
A = '/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/'
MODEL = '/home/user/fromscratch/OMC_CLOUD/vmaf_model/vmaf_v0.6.1neg.json'
TRAIN = [('cine_4k_A006', 2), ('cine_A005C021', 2), ('gfx444_F003C012', 3)]
TEST, CM = sys.argv[1], float(sys.argv[2]); CTX = sys.argv[3] if len(sys.argv) > 3 else 'S16'
TR = [c for c in TRAIN if c[0] != TEST]; K = 16
OUT = os.path.join(os.path.dirname(__file__), '..', 'out', 'rcl_s16'); os.makedirs(OUT, exist_ok=True)
def mag(q, a):
    q = np.abs(q.astype(float)); m = np.zeros_like(q)
    if CTX == 'S16l2': m[:, 2:] += q[:, :-2]; m[:, 1:2] += 0   # left at distance 2: a 2-cycle loop in a lane
    elif CTX != 'S16u': m[:, 1:] += q[:, :-1]
    m[1:, :] += q[:-1, :]; m[1:, 1:] += 0.5 * q[:-1, :-1]; m[1:, :-1] += 0.5 * q[:-1, 1:]
    if CTX == 'S16u': m[1:, 1:] += 0.5 * q[:-1, :-1]; m[1:, :-1] += 0.5 * q[:-1, 1:]   # rebalance weight lost from left
    return m + a[:q.shape[0], :q.shape[1]] if CTX in ('S16', 'S16l2') else m
def cls(q, a): return np.minimum((np.log2(1 + mag(q, a)) * K / 7).astype(int), K - 1)
def syms(planes, Q):
    out = []; ys = []
    for pl, p in enumerate(planes):
        SY = []; AC = []; y = po(p, Q * (CM if pl else 1), 0.7, 0, SY, ACT=AC)[1]; out.append((SY, AC)); ys.append(y)
    return out, ys
def acc(S, tab):
    for SY, AC in S:
        for (key, q), a in zip(SY, AC):
            k = cls(q, a); v = np.clip(q.astype(np.int64), -64, 64) + 64
            for kk in np.unique(k): np.add.at(tab.setdefault(kk, np.zeros(129)), v[k == kk], 1)
def cost(S, tab):
    b = 0.0
    for SY, AC in S:
        for (key, q), a in zip(SY, AC):
            k = cls(q, a); q = q.astype(np.int64)
            for kk in np.unique(k):
                x = q[k == kk]; h = tab.get(kk, np.zeros(129)) + 1; p = h / h.sum()
                b += -np.log2(p[np.clip(x, -64, 64) + 64]).sum() + (12 + 2 * np.log2(np.abs(x[np.abs(x) > 63]))).sum()
    return b
def cost_ub(S, tab, r=1):   # upper bound: each symbol at its max code length over classes c-r..c+r
    b = 0.0; L = {}
    for kk in range(K):
        h = tab.get(kk, np.zeros(129)) + 1; L[kk] = -np.log2(h / h.sum())
    LM = np.array([L[k] for k in range(K)])
    for SY, AC in S:
        for (key, q), a in zip(SY, AC):
            k = cls(q, a); qi = np.clip(q.astype(np.int64), -64, 64) + 64
            m = np.max([LM[np.clip(k + d, 0, K - 1), qi] for d in range(-r, r + 1)], axis=0)
            b += m.sum() + (12 + 2 * np.log2(np.abs(q[np.abs(q) > 63]))).sum()
    return b
def neg1(src, dec):
    cmd = ['ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'yuv422p10le', '-s', '%dx%d' % (W, H), '-i', dec,
           '-f', 'rawvideo', '-pix_fmt', 'yuv422p10le', '-s', '%dx%d' % (W, H), '-i', src, '-frames:v', '1',
           '-lavfi', 'libvmaf=model=path=%s:n_threads=4:log_fmt=json:log_path=/dev/stdout' % MODEL, '-f', 'null', '-']
    return json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)['frames'][0]['metrics']['vmaf']
def psnr(a, b): return 10 * np.log10(1023.0 ** 2 / max(((a - b).astype(float) ** 2).mean(), 1e-9))
TRF = [read(A + c + '_1280x720_422_10.yuv', W, H, f) for c, nf in TR for f in range(nf)]
x = read(A + TEST + '_1280x720_422_10.yuv', W, H, 0)
f0 = os.path.join(OUT, TEST + '_src_f0.yuv')
if not os.path.exists(f0):
    with open(f0, 'wb') as fo:
        for p in x: p.astype('<u2').tofile(fo)
tab = {}
for e in range(-2, 25):
    for fr in TRF: acc(syms(fr, 2 ** (e / 4))[0], tab)
ARM = 'cm%g_%s' % (CM, CTX)
EST = os.environ.get('EST') == '1'
def src_act(planes, Q):   # encoder-side estimate: the same activity computed on the SOURCE (lossless pyramid finals)
    out = []
    for pl, p in enumerate(planes):
        SY = []; AC = []; po(p, 1e-6, 0.7, 0, SY, ACT=AC); s_ = Q * (CM if pl else 1)
        out.append([ai * 1e-6 / s_ for ai in AC])   # same ladder -> ratio 1e-6 / step at every level
    return out
for e in range(-2, 25):
    Q = 2 ** (e / 4); S, ys = syms(x, Q); bpp = cost(S, tab) / (W * H)
    if EST:
        SA = src_act(x, Q); Se = [(SY, sa) for (SY, _), sa in zip(S, SA)]
        est = cost(Se, tab) / (W * H); ub = cost_ub(Se, tab) / (W * H)
        print('   est %.4f emitted %.4f (emitted - est %+.2f %%) | upper bound +-1 class %.4f (padding %.2f %%, over %s)' % (
            est, bpp, 100 * (bpp / est - 1), ub, 100 * (ub / bpp - 1), 'YES' if bpp > ub else 'no'), flush=True)
    if not 0.4 <= bpp < 4.6: continue
    esc = sum(int((np.abs(q) > 63).sum()) for SY, _ in S for _, q in SY); n = sum(q.size for SY, _ in S for _, q in SY)
    fn = os.path.join(OUT, '%s_%s_%.3f.yuv' % (TEST, ARM, Q))
    with open(fn, 'wb') as fo:
        for p in ys: p.astype('<u2').tofile(fo)
    print('%s %s Q=%.3f bpp %.4f NEG %.3f PSNR %.2f/%.2f/%.2f oob %d esc %.4f%%' % (TEST, ARM, Q, bpp, neg1(f0, fn),
          *[psnr(o, p) for o, p in zip(ys, x)], sum(int(((o < LO) | (o > HI)).sum()) for o in ys), 100 * esc / n), flush=True)
    os.unlink(fn)
