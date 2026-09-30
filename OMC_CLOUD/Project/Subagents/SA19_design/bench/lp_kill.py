# partner's "decoupled output layer" kill test (1-level Laplacian pyramid, down = 2x2 mean, up = replicate,
# down(up(c)) = c). gen 1: c = down(x); c^ = Q(c); r = x - up(c^); r^ = Q(r); P1 = clip(up(c^) + r^).
# gen 2 re-reads the coarse layer: c2 = Q(down(P1)). Share of coarse values with c2 != c^.
import numpy as np, yuv
def Q(v, s, rho=0.5): return np.sign(v) * np.floor(np.abs(v) / s + rho) * s
for cell in ('dng720', 'hwy'):
    p, W, H = yuv.CELLS[cell]; x = yuv.read_frame(p, W, H, 3)[0].astype(float)
    down = lambda a: (a[0::2, 0::2] + a[1::2, 0::2] + a[0::2, 1::2] + a[1::2, 1::2]) / 4
    up = lambda c: np.repeat(np.repeat(c, 2, 0), 2, 1)
    for sc, sr in ((2, 8), (4, 16), (8, 32), (4, 32), (1, 16)):
        for rho in (0.5, 0.35):
            c = down(x); ch = np.round(c / sc) * sc
            r = x - up(ch); rh = Q(r, sr, rho); P1 = np.clip(np.round(up(ch) + rh), 0, 1023)
            c2 = np.round(down(P1) / sc) * sc
            print(cell, 'coarse step %d resid step %d rho %.2f: coarse re-read mismatch %.1f %%' % (sc, sr, rho, 100 * (c2 != ch).mean()))
