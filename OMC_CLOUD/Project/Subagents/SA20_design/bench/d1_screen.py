#!/usr/bin/env python3
# d1_screen.py — PROXY screen (entropy, not real code lengths; screening only).
# Intra, one frame, all three planes of a 4:2:2 10-bit clip.
#  ARM W53 : transform reference = integer 5/3, 2 levels 2-D + 3 levels horizontal, dead zone 0.35-rounding,
#            steps gain-normalised (coarse finer), zeroth-order entropy per band + 1-bit context (left/up nonzero).
#  ARM D1  : slack-read Laplacian (SA20Q): k = round(mean2x2 / Dc); k coded LOSSLESSLY by integer 5/3 (3 levels 2-D),
#            entropy per band; up() = bilinear of Dc*k (integer); residual q = deadzone(x - up, Dr) per sample,
#            out = clip(up + q*Dr); residual entropy zeroth-order with the same 1-bit context.
#            Read-slack steering ignored (it only moves indices by one step on a few blocks).
# Output: rate (bits per luma sample, all planes) and PSNR Y/Cb/Cr per point; then BD-PSNR D1 vs W53 per plane.
import sys, numpy as np

LO, HI = 0, 1023
def read(path, W, H, f):
    cw = W // 2; fs = W * H + 2 * cw * H
    a = np.fromfile(path, '<u2', count=fs, offset=2 * f * fs).astype(np.int64)
    return [a[:W*H].reshape(H, W), a[W*H:W*H+cw*H].reshape(H, cw), a[W*H+cw*H:].reshape(H, cw)]

def l53f(x, axis):  # integer 5/3 forward along axis, symmetric ext; returns (low, high)
    x = np.moveaxis(x, axis, 0); e = x[0::2].copy(); o = x[1::2].copy()
    en = np.concatenate([e[1:], e[-1:]], 0)[:o.shape[0]]
    o = o - ((e[:o.shape[0]] + en) >> 1)
    op = np.concatenate([o[:1], o], 0)[:e.shape[0]]; oc = np.concatenate([o, o[-1:]], 0)[:e.shape[0]]
    e = e + ((op + oc + 2) >> 2)
    return np.moveaxis(e, 0, axis), np.moveaxis(o, 0, axis)
def l53i(e, o, axis):
    e = np.moveaxis(e, axis, 0).copy(); o = np.moveaxis(o, axis, 0).copy()
    op = np.concatenate([o[:1], o], 0)[:e.shape[0]]; oc = np.concatenate([o, o[-1:]], 0)[:e.shape[0]]
    e = e - ((op + oc + 2) >> 2)
    en = np.concatenate([e[1:], e[-1:]], 0)[:o.shape[0]]
    o = o + ((e[:o.shape[0]] + en) >> 1)
    x = np.empty((e.shape[0] + o.shape[0],) + e.shape[1:], np.int64); x[0::2] = e; x[1::2] = o
    return np.moveaxis(x, 0, axis)

def fwd(x, lv2=2, lvh=3):
    bands = []; a = x
    for _ in range(lv2):
        L, Hh = l53f(a, 1); LL, LH = l53f(L, 0); HL, HH = l53f(Hh, 0)
        bands.append(('2d', [LH, HL, HH])); a = LL
    for _ in range(lvh):
        a, Hh = l53f(a, 1); bands.append(('h', [Hh]))
    return a, bands
def inv(a, bands):
    for kind, b in reversed(bands):
        if kind == 'h': a = l53i(a, b[0], 1)
        else:
            LH, HL, HH = b; L = l53i(a, LH, 0); Hh = l53i(HL, HH, 0); a = l53i(L, Hh, 1)
    return a

def ent(q):  # zeroth order + 1-bit context (left or up nonzero), bits
    q = q.astype(np.int64); nz = (q != 0)
    ctx = np.zeros_like(nz); ctx[:, 1:] |= nz[:, :-1]; ctx[1:, :] |= nz[:-1, :]
    bits = 0.0
    for c in (0, 1):
        v = q[ctx == c]
        if v.size == 0: continue
        _, n = np.unique(v, return_counts=True); p = n / v.size; bits += -(n * np.log2(p)).sum()
    return bits
def dz(v, s, rho=0.35): return np.sign(v) * np.floor(np.abs(v) / s + rho)

# band gains (synthesis energy of a unit impulse), for gain-normalised steps
def gains(shape):
    x = np.zeros(shape, np.int64); a, b = fwd(x); g = []
    def unit(setter):
        a0, b0 = fwd(np.zeros(shape, np.int64)); setter(a0, b0); y = inv(a0 * 1024, [(k, [m * 1024 for m in bb]) for k, bb in b0])
        return (y.astype(float) ** 2).sum() / 1024 ** 2
    ga = unit(lambda a0, b0: a0.__setitem__((a0.shape[0] // 2, a0.shape[1] // 2), 1))
    gb = []
    for i, (k, bb) in enumerate(b):
        gg = []
        for j in range(len(bb)):
            def s(a0, b0, i=i, j=j): m = b0[i][1][j]; m[m.shape[0] // 2, m.shape[1] // 2] = 1
            gg.append(unit(s))
        gb.append(gg)
    return ga, gb

def w53(planes, Q):
    bits = 0; outs = []
    for p in planes:
        a, b = fwd(p); ga, gb = GAINS[p.shape]
        sa = max(1.0, Q / np.sqrt(ga)); qa = np.round(a / sa); bits += ent(qa)   # LL: rounding, no dead zone
        nb = []
        for (k, bb), gg in zip(b, gb):
            m = []
            for c, g in zip(bb, gg):
                s = max(1.0, Q / np.sqrt(g)); qc = dz(c, s); bits += ent(qc); m.append(np.round(qc * s).astype(np.int64))
            nb.append((k, m))
        y = inv(np.round(qa * sa).astype(np.int64), nb); outs.append(np.clip(y, LO, HI))
    return bits, outs

def up2(c, shape):  # integer bilinear 2x upsample (block centres), edge replicate
    H, W = shape; ys = (np.arange(H) - 0.5) / 2; xs = (np.arange(W) - 0.5) / 2
    y0 = np.clip(np.floor(ys).astype(int), 0, c.shape[0] - 1); y1 = np.clip(y0 + 1, 0, c.shape[0] - 1)
    x0 = np.clip(np.floor(xs).astype(int), 0, c.shape[1] - 1); x1 = np.clip(x0 + 1, 0, c.shape[1] - 1)
    wy = ((ys - np.floor(ys)) * 4).round().astype(int)[:, None]; wx = ((xs - np.floor(xs)) * 4).round().astype(int)[None, :]
    v = (c[y0][:, x0] * (4 - wy) * (4 - wx) + c[y1][:, x0] * wy * (4 - wx) + c[y0][:, x1] * (4 - wy) * wx + c[y1][:, x1] * wy * wx)
    return (v + 8) >> 4

KSH = []
def d1(planes, Dr, ratio):
    bits = 0; outs = []; Dc = Dr * ratio
    for p in planes:
        m = (p[0::2, 0::2] + p[1::2, 0::2] + p[0::2, 1::2] + p[1::2, 1::2]) / 4.0
        k = np.round(m / Dc).astype(np.int64)
        a, b = fwd(k, 3, 0); bits += ent(a)   # lossless integer 5/3 of k
        for _, bb in b:
            for c in bb: bits += ent(c)
        kb = bits
        u = up2((k * Dc).round().astype(np.int64), p.shape)
        q = dz(p - u, Dr); bits += ent(q); KSH.append((kb, bits))
        outs.append(np.clip(u + np.round(q * Dr).astype(np.int64), LO, HI))
    return bits, outs

def psnr(a, b): return 10 * np.log10(1023.0 ** 2 / max(((a - b).astype(float) ** 2).mean(), 1e-9))
if __name__ == "__main__":
    path, W, H = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]); f = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    planes = read(path, W, H, f)
    GAINS = {p.shape: gains(p.shape) for p in planes}
    res = {}
    import os
    RAT = [float(r) for r in os.environ.get('RATIOS', '4,2,1.25').split(',')]
    arms = [('W53', w53, [2 ** (e / 2) for e in range(2, 14)])] + [('D1r%g' % r, (lambda r: lambda P, d: d1(P, d, r))(r), [2 ** (e / 2) for e in range(0, 12)]) for r in RAT]
    for name, fn, params in arms:
        pts = []
        for q in params:
            bits, outs = fn(planes, q); bpp = bits / (W * H)
            ps = [psnr(o, p) for o, p in zip(outs, planes)]; pts.append((bpp, ps))
            ksh = ''
            if KSH: kb = sum(a for a, b in KSH); ksh = ' k-share %.0f %%' % (100.0 * sum(a for a, b in KSH) / max(bits, 1)); KSH.clear()
            print('%s q=%.2f bpp %.3f PSNR %.2f/%.2f/%.2f%s' % (name, q, bpp, *ps, ksh), flush=True)
        res[name] = sorted(pts)
    def at(pts, r, pl):  # PSNR at rate r by linear interp in log2(bpp)
        x = np.log2([p[0] for p in pts]); y = [p[1][pl] for p in pts]; o = np.argsort(x)
        return float(np.interp(np.log2(r), x[o], np.array(y)[o]))
    for r in (0.25, 0.5, 1.0):
        ref = [at(res['W53'], r, pl) for pl in range(3)]
        print('@%.2f W53 %.2f/%.2f/%.2f' % (r, *ref) + ''.join(' | %s %+.2f/%+.2f/%+.2f' % (n, *[at(res[n], r, pl) - ref[pl] for pl in range(3)]) for n in res if n != 'W53'))
