# E1b: BD-rate of vertical filters vs V53 (H53 fixed), intra, entropy proxy; per-plane PSNR at matched rate
import numpy as np, sys, xf, yuv
from exp1 import code_plane, rowret
cell = sys.argv[1]; vfs = sys.argv[2].split(','); frames = [int(a) for a in sys.argv[3].split(',')]
path, W, H = yuv.CELLS[cell]
D0s = (24, 36, 54, 80, 120)
res = {}
for vf in vfs:
    pts = []
    for D0 in D0s:
        tot = 0; se = np.zeros(3); sp = np.zeros(3)
        for f in frames:
            fr = yuv.read_frame(path, W, H, f)
            for i, x in enumerate(fr):
                vv, hh = vf.split(':') if ':' in vf else (vf, '53'); y, b = code_plane(x, D0, vv, hh, 0.4); y = np.clip(y, 0, 1023)
                tot += b; se[i] += np.mean((x - y.astype(float)) ** 2)
                sp[i] += rowret(x, y, 4)[0]
        bpp = tot / (W * H * len(frames)); ps = 10 * np.log10(1023 ** 2 / (se / len(frames)))
        pts.append((bpp, *ps, *(sp / len(frames))))
        print('%s %-6s D0=%3d bpp=%.3f PSNR %.2f/%.2f/%.2f  rowspread4 %.1f/%.1f/%.1f' % (cell, vf, D0, bpp, *ps, *(sp / len(frames))), flush=True)
    res[vf] = np.array(pts)
# BD-rate on weighted psnr (6:1:1) vs first vf
def bd(a, b):
    wa = (6 * a[:, 1] + a[:, 2] + a[:, 3]) / 8; wb = (6 * b[:, 1] + b[:, 2] + b[:, 3]) / 8
    pa = np.polyfit(wa, np.log(a[:, 0]), 3); pb = np.polyfit(wb, np.log(b[:, 0]), 3)
    lo, hi = max(wa.min(), wb.min()), min(wa.max(), wb.max())
    ia = np.polyval(np.polyint(pa), [lo, hi]); ib = np.polyval(np.polyint(pb), [lo, hi])
    return 100 * (np.exp(((ib[1] - ib[0]) - (ia[1] - ia[0])) / (hi - lo)) - 1)
for vf in vfs[1:]:
    print('BD-rate %s vs %s on %s: %+.2f %%' % (vf, vfs[0], cell, bd(res[vfs[0]], res[vf])))
