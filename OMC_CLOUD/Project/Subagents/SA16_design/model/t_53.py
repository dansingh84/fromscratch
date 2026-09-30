# intra transform comparison at matched entropy: CQP pyramid vs LeGall 5/3 (2V x 5H), equal-MSE weights from measured synthesis gains
import sys, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import pyr2, yuv
def ent(q):
    q = np.clip(np.asarray(q).astype(np.int64), -40, 40).ravel() + 40; c = np.bincount(q, minlength=81).astype(float); p = c[c > 0] / c.sum()
    return -(c[c > 0] * np.log2(p)).sum()
# ---- 5/3 lifting (reversible), 1-D along an axis with symmetric extension
def a53(x, ax):
    x = np.moveaxis(x, ax, 0).astype(np.int64); n = x.shape[0]; e = x[0::2]; o = x[1::2]
    er = np.concatenate([e, e[-1:]], 0) if n % 2 == 0 else e
    d = o - ((er[:-1] + er[1:]) >> 1) if n % 2 == 0 else o - ((e[:-1] + e[1:]) >> 1)
    dl = np.concatenate([d[:1], d], 0)
    s = e + ((dl[:-1] + dl[1:] + 2) >> 2) if n % 2 == 0 else e + ((np.concatenate([d[:1], d], 0)[:-1] + np.concatenate([d, d[-1:]], 0)[:-1]) * 0 + (np.concatenate([d[:1], d])[:len(e)] + np.concatenate([d, d[-1:]])[:len(e)] + 2) >> 2)
    return np.moveaxis(s, 0, ax), np.moveaxis(d, 0, ax)
def s53(s, d, ax):
    s = np.moveaxis(s, ax, 0); d = np.moveaxis(d, ax, 0); dl = np.concatenate([d[:1], d], 0)
    e = s - ((dl[:-1] + dl[1:] + 2) >> 2); er = np.concatenate([e, e[-1:]], 0); o = d + ((er[:-1] + er[1:]) >> 1)
    x = np.empty((e.shape[0] + o.shape[0],) + e.shape[1:], np.int64); x[0::2] = e; x[1::2] = o
    return np.moveaxis(x, 0, ax)
def ana53(x, Lh):
    T = {}; ll = x
    for k in range(1, Lh + 1):
        L, Hh = a53(ll, 1)
        if k <= 2:
            LL, LH = a53(L, 0); HL, HH = a53(Hh, 0); T['LH%d' % k] = LH; T['HL%d' % k] = HL; T['HH%d' % k] = HH; ll = LL
        else: T['H%d' % k] = Hh; ll = L
    T['LL'] = ll; return T
def syn53(T, Lh):
    ll = T['LL']
    for k in range(Lh, 0, -1):
        if k <= 2:
            L = s53(ll, T['LH%d' % k], 0); Hh = s53(T['HL%d' % k], T['HH%d' % k], 0); ll = s53(L, Hh, 1)
        else: ll = s53(ll, T['H%d' % k], 1)
    return ll
def gains(ana, syn, shape, Lh, bands):
    """synthesis energy gain per band (impulse at a central coefficient)."""
    T = ana(np.zeros(shape, np.int64), Lh); g = {}
    for b in bands:
        C = {bb: np.zeros_like(T[bb]) for bb in bands}; a = C[b]; a[a.shape[0] // 2, a.shape[1] // 2] = 64
        x = syn(C, Lh).astype(float); g[b] = ((x / 64.0) ** 2).sum()
    return g
def run(name, ana, syn, x, Lh, steps):
    T = ana(x, Lh); bands = list(T.keys()); g = gains(ana, syn, x.shape, Lh, bands); pts = []
    for s in steps:
        bits = 0; C = {}
        for b in bands:
            D = max(1, int(round(s / np.sqrt(g[b])))); q = np.round(T[b] / D).astype(np.int64); bits += ent(q); C[b] = q * D
        xr = syn(C, Lh)

        mse = np.mean((xr - x) ** 2.0); pts.append((bits / x.size, 10 * np.log10(1023 ** 2 / mse)))
    return pts
def bd(ref, tst):
    ref = sorted(ref); tst = sorted(tst); lo = max(ref[0][0], tst[0][0]); hi = min(ref[-1][0], tst[-1][0])
    bs = np.exp(np.linspace(np.log(lo), np.log(hi), 20)); f = lambda pts, b: float(np.interp(b, [p[0] for p in pts], [p[1] for p in pts]))
    return np.mean([f(tst, b) - f(ref, b) for b in bs])
cqp_syn = lambda C, Lh: pyr2.synthesis(C, Lh, -10**6, 10**6)[0]
for clip, W, H, f in ((yuv.TRAIN[0], 1920, 1080, 2), (yuv.CELLS['dng720'][0], 1280, 720, 2)):
    fr = yuv.read_frame(clip, W, H, f)
    for pn, x, Lh in (('Y', fr[0], 5), ('Cb', fr[1], 4), ('Cr', fr[2], 4)):
        steps = (1.0, 1.5, 2.2, 3.3, 5, 7, 10, 14)
        a = run('53', ana53, syn53, x, Lh, [s * 4 for s in steps]); b = run('cqp', pyr2.analysis, cqp_syn, x, Lh, [s * 4 for s in steps])
        print('%-12s %-2s CQP vs 5/3 at matched entropy: %+.2f dB | at ~0.5 bpp: 5/3 %s cqp %s' % (clip.split('/')[-1][:12], pn, bd(a, b),
              [(round(p[0], 3), round(p[1], 2)) for p in a if 0.3 < p[0] < 0.8][:2], [(round(p[0], 3), round(p[1], 2)) for p in b if 0.3 < p[0] < 0.8][:2]), flush=True)
