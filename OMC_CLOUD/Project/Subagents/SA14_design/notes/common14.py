import numpy as np, os
import nest

ARMS = '/home/user/fromscratch/OMC_CLOUD/Project/.work/arms'
CELLS = {
    'dng1080': (ARMS + '/dng_1920x1080_422_10.yuv', 1920, 1080, '422', 10),
    'spot': (ARMS + '/long/spotrobotL_1920x1080_422_10.yuv', 1920, 1080, '422', 10),
    'floor': (ARMS + '/long/floorballgameL_1920x1080_422_10.yuv', 1920, 1080, '422', 10),
    'gfx': (ARMS + '/cf_gfx_448x256_422_10.yuv', 448, 256, '422', 10),
    'dng720': (ARMS + '/dng_1280x720_422_10.yuv', 1280, 720, '422', 10),
    'dng444_12': (ARMS + '/dng_1920x1080_444_12.yuv', 1920, 1080, '444', 12),
}

def read_frame(cell, f):
    path, W, H, fmt, dep = CELLS[cell]
    cw = W if fmt == '444' else W // 2
    n = W * H + 2 * cw * H
    a = np.fromfile(path, dtype='<u2', count=n, offset=2 * n * f).astype(np.int64)
    Y = a[:W * H].reshape(H, W)
    Cb = a[W * H:W * H + cw * H].reshape(H, cw)
    Cr = a[W * H + cw * H:].reshape(H, cw)
    return [Y, Cb, Cr], dep

def synth_rails(W=512, H=256, dep=10, seed=1):
    """synthetic full-range rail picture: black/white plates, 1-px strokes, stripes, a ramp."""
    rng = np.random.default_rng(seed)
    M = (1 << dep) - 1
    X = np.zeros((H, W), np.int64)
    X[:, W // 2:] = M
    for _ in range(40):
        y0, x0 = rng.integers(0, H - 20), rng.integers(0, W - 40)
        h, w = rng.integers(2, 20), rng.integers(2, 40)
        X[y0:y0 + h, x0:x0 + w] = rng.choice([0, M, M // 2, 64, 940])
    X[10:40, 10:200:2] = M          # 1-px vertical stripes
    X[50:52, :] = M; X[53, :] = 0     # thin lines
    X[200:230, :] = (np.arange(W) * M // (W - 1))[None, :]   # full ramp
    X[100:180:3, 300:500] = 0
    return X

def shifts_for(n2d, n1d, shape, D0, mode='nest'):
    """power-of-two step per band from synthesis basis energy (linear synthesis, no windows)."""
    H, W = shape
    sh = {}
    lo = np.full(shape, -nest.INF); hi = np.full(shape, nest.INF)
    # build zero leaves
    levels, (L, tlo, thi) = nest.analysis(np.zeros(shape, np.int64), lo, hi, n2d, n1d)
    def energy(lev, name):
        ql = []
        for lv, lvl in enumerate(levels):
            d = {}
            for n, dd in lvl.items():
                if n == 'win':
                    continue
                v = np.zeros_like(dd['val'])
                if lv == lev and n == name:
                    v[v.shape[0] // 2, v.shape[1] // 2] = 1 << 12
                d[n] = {'val': v, 'esc': np.zeros(v.shape, np.int8)}
            ql.append(d)
        tv = np.zeros_like(L)
        if name == 'top':
            tv[tv.shape[0] // 2, tv.shape[1] // 2] = 1 << 12
        rec, _, _ = nest.synthesis({'val': tv, 'esc': np.zeros(tv.shape, np.int8)}, ql, lo, hi, n2d, n1d)
        return (rec.astype(np.float64) / (1 << 12)) ** 2
    for lev, lvl in enumerate(levels):
        for n in lvl:
            if n == 'win':
                continue
            e = energy(lev, n).sum()
            sh[(lev, n)] = max(0, int(round(np.log2(D0 / np.sqrt(e)))))
    e = energy(None, 'top').sum()
    sh['top'] = max(0, int(round(np.log2(D0 / np.sqrt(e)))))
    return sh

def psnr(a, b, dep):
    m = np.mean((a.astype(np.float64) - b) ** 2)
    return 99.0 if m == 0 else 10 * np.log10(((1 << dep) - 1) ** 2 / m)
