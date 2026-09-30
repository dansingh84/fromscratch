# Empirical high-rate coding gain (band variance x synthesis-norm weighted, geometric mean) of the
# OMC 2V x 5H structure on real frames, per plane Y/Cb/Cr.  Linear lifting, periodic ends.
import numpy as np, sys
def fwd1(x, ax, P, U):
    x = np.moveaxis(x, ax, 0); e = x[0::2].copy(); o = x[1::2].copy()
    h = o.copy()
    for off, w in P: h -= w * np.roll(e, -off, 0)
    l = e.copy()
    for off, w in U: l += w * np.roll(h, -off, 0)
    return np.moveaxis(np.concatenate([l, h], 0), 0, ax)
def inv1(y, ax, P, U):
    y = np.moveaxis(y, ax, 0); m = y.shape[0] // 2; l = y[:m].copy(); h = y[m:].copy()
    e = l.copy()
    for off, w in U: e -= w * np.roll(h, -off, 0)
    o = h.copy()
    for off, w in P: o += w * np.roll(e, -off, 0)
    x = np.empty_like(y); x[0::2] = e; x[1::2] = o
    return np.moveaxis(x, 0, ax)
def stages(R, C):
    return [('v', R, C, 'V1'), ('h', R, C, 'H1'), ('v', R//2, C//2, 'V2'), ('h', R//2, C//2, 'H2'),
            ('h', R//4, C//4, 'H3'), ('h', R//4, C//8, 'H4'), ('h', R//4, C//16, 'H5')]
def fwd2(img, cfg):
    x = img.astype(float).copy(); R, C = x.shape
    for ax, nr, nc, nm in stages(R, C):
        P, U = cfg[nm]; x[:nr, :nc] = fwd1(x[:nr, :nc], 0 if ax == 'v' else 1, P, U)
    return x
def inv2(x, cfg):
    x = x.copy(); R, C = x.shape
    for ax, nr, nc, nm in reversed(stages(R, C)):
        P, U = cfg[nm]; x[:nr, :nc] = inv1(x[:nr, :nc], 0 if ax == 'v' else 1, P, U)
    return x
def bands(R, C):
    b = []; r, c = R, C
    # V1: rows [R/2,R) all cols? follow Mallat: after V1+H1: LL1 [0,R/2)x[0,C/2), LH1 [R/2,R)x[0,C/2), HL1 [0,R/2)x[C/2,C), HH1 [R/2,R)x[C/2,C)
    b += [(R//2, R, 0, C//2), (0, R//2, C//2, C), (R//2, R, C//2, C)]
    b += [(R//4, R//2, 0, C//4), (0, R//4, C//4, C//2), (R//4, R//2, C//4, C//2)]
    b += [(0, R//4, C//8, C//4), (0, R//4, C//16, C//8), (0, R//4, C//32, C//16), (0, R//4, 0, C//32)]
    return b
def gain(img, cfg):
    R, C = img.shape; y = fwd2(img, cfg); lg = 0; N = R * C
    assert np.allclose(inv2(y, cfg), img, atol=1e-6)
    for r0, r1, c0, c1 in bands(R, C):
        z = np.zeros_like(y); z[(r0 + r1)//2, (c0 + c1)//2] = 1.0
        w = (inv2(z, cfg)**2).sum()
        v = y[r0:r1, c0:c1]; var = np.mean((v - (v.mean() if (r0, c0) == (0, 0) else 0))**2)
        n = (r1 - r0) * (c1 - c0); lg += n / N * np.log10(max(var * w, 1e-12))
    return 10 * (np.log10(np.var(img)) - lg)
P53 = [(0, .5), (1, .5)]; U53 = [(-1, .25), (0, .25)]
P97 = [(-1, -1/16), (0, 9/16), (1, 9/16), (2, -1/16)]
P60 = [(-2, 3/256), (-1, -25/256), (0, 150/256), (1, 150/256), (2, -25/256), (3, 3/256)]
def one(a, w1=.25, w2=.25): return [(-a, w1), (-a - 1, w2)]
CFG = {
 'today (sym 5/3 V; 9/7-M H1-2; 5/3 H3-5)': dict(V1=(P53, U53), V2=(P53, U53), H1=(P97, U53), H2=(P97, U53), H3=(P53, U53), H4=(P53, U53), H5=(P53, U53)),
 'predict-only 2-tap/4-tap (DESIGN3-like)': dict(V1=(P53, []), V2=(P53, []), H1=(P97, []), H2=(P97, []), H3=(P53, []), H4=(P53, []), H5=(P53, [])),
 'predict-only expert A ((6,0) H1,(4,0) H2, V (4,0))': dict(V1=(P97, []), V2=(P97, []), H1=(P60, []), H2=(P97, []), H3=(P53, []), H4=(P53, []), H5=(P53, [])),
 'one-sided acyclic, V lags(3,2) H lags(20,20,5,3,2) w=.25': dict(V1=(P53, one(3)), V2=(P53, one(2)), H1=(P97, one(20)), H2=(P97, one(20)), H3=(P53, one(5)), H4=(P53, one(3)), H5=(P53, one(2))),
 'one-sided CYCLIC lag 2 everywhere w=.25 (design text)': dict(V1=(P53, one(2)), V2=(P53, one(2)), H1=(P97, one(2)), H2=(P97, one(2)), H3=(P53, one(2)), H4=(P53, one(2)), H5=(P53, one(2))),
 'V one-sided (3,2) only, H symmetric (cyclic)': dict(V1=(P53, one(3)), V2=(P53, one(2)), H1=(P97, U53), H2=(P97, U53), H3=(P53, U53), H4=(P53, U53), H5=(P53, U53)),
}
def load(path, W, H, fr):
    fs = W * H * 2 * 2; d = np.fromfile(path, dtype='<u2', count=fs // 2, offset=fr * fs)
    Y = d[:W*H].reshape(H, W); Cb = d[W*H:W*H + W*H//2].reshape(H, W//2); Cr = d[W*H + W*H//2:].reshape(H, W//2)
    return Y, Cb, Cr
for path, W, H, fr in [('/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1920x1080_422_10.yuv', 1920, 1080, 5),
                       ('/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/cityalley_1920x1080_422_10.yuv', 1920, 1080, 5)]:
    Y, Cb, Cr = load(path, W, H, fr)
    print(path.split('/')[-1], 'frame', fr, ' (Y/Cb/Cr coding gain, dB)')
    for k, cfg in CFG.items():
        g = [gain(p.astype(float), cfg) for p in (Y, Cb, Cr)]
        print(f"  {k:58s} {g[0]:6.2f} {g[1]:6.2f} {g[2]:6.2f}"); sys.stdout.flush()
