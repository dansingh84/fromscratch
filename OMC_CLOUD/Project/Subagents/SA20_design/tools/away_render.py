#!/usr/bin/env python3
# away_render.py CELLS RATES : H21 first measurement. Runs the pack's averaging pair pyramid with leaf-interval
# legality (SA19 bench, unchanged, as a measuring instrument) on frame 0 and compares the legal decode with the SAME
# coded leaves synthesised rail-free and then plainly clipped. Per plane: samples moved farther than the plain clip,
# worst excess (codes) and where, p99 of the excess; PNG crops (x4, brightened) of the 10 worst luma moves:
# source | legal decode | plain-clip decode | excess map. Output: renders/away/<cell>_<rate>_k.png
import sys, os, numpy as np
from PIL import Image
B = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA19_design/bench'; sys.path.insert(0, B); os.chdir(B)
import yuv, ent, seq, pyr
SA7 = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/'; ARMS = '/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/'
C = {'cut24': (SA7 + 'cut24.yuv', 256, 64, 0, 1023), 'ext10': (SA7 + 'ext_10_422_l0.yuv', 512, 128, 0, 1023),
     'gfx': (ARMS + 'cf_gfx_448x256_422_10.yuv', 448, 256, 4, 1019), 'dng720': (yuv.CELLS['dng720'][0], 1280, 720, 4, 1019),
     'title_full': (ARMS + 'title_full_1280x720_422_10.yuv', 1280, 720, 4, 1019),
     'title_narrow': (ARMS + 'title_narrow_1280x720_422_10.yuv', 1280, 720, 4, 1019)}
OUT = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design/renders/away'; os.makedirs(OUT, exist_ok=True)
tabs = ent.Tables('../out/tab_h_r1.pkl')
def show(a, lo_v, hi_v):   # brighten: map [lo_v, hi_v] to 0..255
    return np.clip((a.astype(float) - lo_v) * 255.0 / max(hi_v - lo_v, 1), 0, 255).astype(np.uint8)
for cell in sys.argv[1].split(','):
    path, W, H, lo, hi = C[cell]
    for bpp in [float(r) for r in sys.argv[2].split(',')]:
        g = seq.Seq(W, H, bpp, tabs, lo=lo, hi=hi, tilt=0.25, rho=0.35, S=4 if H <= 720 else 8, still_hold=1, refresh=False, bx=64, lam=4)
        g.c.emit_reading = False
        x = yuv.read_frame(path, W, H, 0); o, b, info = g.encode(x)
        for p in range(3):
            s = x[p].astype(float); yu, _, _ = pyr.synthesis(info['V0'][p], lo, hi, legal=False); yc = np.clip(yu, lo, hi)
            el = np.abs(o[p] - s); ec = np.abs(yc - s); ex = el - ec; aw = ex > 0
            if aw.any():
                i = np.unravel_index(np.argmax(ex), ex.shape); p99 = np.percentile(ex[aw], 99)
            else: i, p99 = (-1, -1), 0
            print('%-12s @%.1f plane %d: bits/px %.3f | away %d (%.4f %%) | worst excess %d codes at row %d col %d (source %d, legal %d, clip %d) | p99 %.0f' % (
                cell, bpp, p, float(np.sum(b)) / (W * H), int(aw.sum()), 100 * aw.mean(), int(ex.max()) if aw.any() else 0, i[0], i[1],
                int(s[i]) if aw.any() else -1, int(o[p][i]) if aw.any() else -1, int(yc[i]) if aw.any() else -1, p99), flush=True)
            if p == 0 and aw.any():
                idx = np.argsort(ex.ravel())[::-1][:10]; done = []
                for k, j in enumerate(idx):
                    r, c = divmod(int(j), W)
                    if any(abs(r - a) < 16 and abs(c - bb) < 16 for a, bb in done): continue
                    done.append((r, c)); r0 = int(np.clip(r - 16, 0, H - 32)); c0 = int(np.clip(c - 16, 0, W - 32))
                    win = lambda a: a[r0:r0 + 32, c0:c0 + 32]
                    v = [win(s), win(o[p]), win(yc)]; vlo, vhi = min(a.min() for a in v), max(a.max() for a in v)
                    tiles = [show(a, vlo, vhi) for a in v] + [show(win(np.maximum(ex, 0)), 0, max(1, ex.max()))]
                    im = np.concatenate([np.pad(np.kron(t, np.ones((4, 4), np.uint8)), ((0, 0), (0, 4)), constant_values=128) for t in tiles], 1)
                    Image.fromarray(im).save(os.path.join(OUT, '%s_%.1f_%02d_r%d_c%d.png' % (cell, bpp, len(done), r, c)))
