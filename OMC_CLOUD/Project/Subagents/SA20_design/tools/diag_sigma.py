# median per-block luma sigma-hat, frames 0 -> 1: temporal (frame difference, 20th pct per luma band, as bench/rcl_cbr.py
# noise_gate) vs spatial (Immerkaer Laplacian, 20th pct per luma band, as bench/rcl_cbr.py spatial_sigma)
import sys, numpy as np
W, H = 1280, 720; A = '/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/'
def rd(c, f):
    n = W * H * 2; a = np.fromfile(A + c + '_1280x720_422_10.yuv', '<u2', n, offset=f * n * 2).astype(float); return a[:W * H].reshape(H, W)
def blocks(a): return a.reshape(H // 16, 16, W // 16, 16).mean(axis=(1, 3))
def band_pct(m, lb):
    n = np.array([np.percentile(m[lb == b], 20) if (lb == b).sum() >= 8 else np.percentile(m, 20) for b in range(8)]); return n[lb]
for c in sys.argv[1:]:
    x0, x1 = rd(c, 0), rd(c, 1); lb = np.minimum((blocks(x1) / 128).astype(int), 7)
    tem = np.maximum(band_pct(blocks(np.abs(x1 - x0)), lb), 0.5) / 1.13
    q = np.pad(x1, 1, mode='edge')
    L = q[:-2, :-2] - 2 * q[:-2, 1:-1] + q[:-2, 2:] - 2 * (q[1:-1, :-2] - 2 * q[1:-1, 1:-1] + q[1:-1, 2:]) + q[2:, :-2] - 2 * q[2:, 1:-1] + q[2:, 2:]
    spa = np.maximum(band_pct(blocks(np.abs(L)) * np.sqrt(np.pi / 2) / 6, lb), 0.5 / 1.13)
    print('%-16s temporal %.2f spatial %.2f' % (c, np.median(tem), np.median(spa)))
