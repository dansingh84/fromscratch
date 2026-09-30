# E1: transform choice. intra, gain-normalised dead-zone quantiser, zeroth-order entropy proxy (A/B only).
import numpy as np, sys, xf, yuv

def ent_bits(q):
    q = q.ravel(); a = np.abs(q)
    c = np.minimum(a, 64)
    v, n = np.unique(c, return_counts=True); p = n / n.sum()
    bits = -(n * np.log2(p)).sum() + (a > 0).sum()          # magnitude class + sign
    big = a[a >= 64]
    bits += (2 * np.log2(big / 32.0)).sum() if big.size else 0
    return bits

def code_plane(x, D0, vf, hf, rho, Lv=2, Lh=5):
    T = xf.analysis(x - 512, Lv, Lh, vf, hf)
    G = xf.gains(x.shape, Lv, Lh, vf, hf)
    R = {}; bits = 0
    for b, c in T.items():
        D = max(1.0, D0 / np.sqrt(G[b]))
        q = np.sign(c) * np.floor(np.abs(c) / D + rho)
        bits += ent_bits(q.astype(np.int64))
        R[b] = np.round(q * D).astype(np.int64)
    y = xf.synthesis(R, Lv, Lh, vf, hf) + 512
    return y, bits

def rowret(s, d, sh):
    gs = np.abs(np.diff(s.astype(float), axis=1)).mean(1); gd = np.abs(np.diff(d.astype(float), axis=1)).mean(1)
    H = s.shape[0]; ph = np.arange(H) % sh
    r = np.array([gd[ph == k].sum() / gs[ph == k].sum() for k in range(sh)])
    return 100 * (r.max() - r.min()) / r.mean(), r

if __name__ == '__main__':
    cells = sys.argv[1].split(',')
    rho = float(sys.argv[2]) if len(sys.argv) > 2 else 0.4
    for cell in cells:
        path, W, H = yuv.CELLS[cell]
        fr = yuv.read_frame(path, W, H, 3)
        for vf, hf in (('53', '53'), ('26', '53'), ('26', '26')):
            for D0 in (12, 20, 32, 48):
                tot = 0; ps = []; sp4 = []; sp16 = []
                for i, x in enumerate(fr):
                    y, b = code_plane(x, D0 * (1.0 if i == 0 else 1.0), vf, hf, rho)
                    y = np.clip(y, 0, 1023)
                    tot += b; ps.append(yuv.psnr(x, y))
                    sp4.append(rowret(x, y, 4)[0]); sp16.append(rowret(x, y, 16)[0])
                print('%-7s V%s H%s D0=%3d bpp=%.3f PSNR %.2f/%.2f/%.2f  rowspread4 %.1f/%.1f/%.1f %%  sp16 %.1f/%.1f/%.1f' % (
                    cell, vf, hf, D0, tot / (W * H), ps[0], ps[1], ps[2], *sp4, *sp16), flush=True)
