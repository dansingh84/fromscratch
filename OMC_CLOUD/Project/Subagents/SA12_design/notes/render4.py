"""Eye renders (owner): full-frame, full-resolution, for each decode and frame:
  <tag>_f<N>_decode.png            colour decode (BT.709, limited-range display mapping as smudgegroups.py)
  <tag>_f<N>_level_{Y,Cb,Cr}.png    8x8 block mean of (decode - source): red = too bright/too much, blue = too little, +-10 codes = full
  <tag>_f<N>_absdiff_{Y,Cb,Cr}.png  |decode - source| x 8
  each also as _grid.png (8-row slice lines + 32-column lines, red, 1 px) -- same raster.
Also prints the dark-area discolouration statistic (G6): over pixels whose SOURCE luma < 25 % of range,
mean signed error Cb/Cr, mean |err| Cb/Cr, and chroma-magnitude ratio |(Cb,Cr)-mid| decode/source (1.00 = no desaturation).
usage: render4.py src.yuv W H outdir tag:dec.yuv [tag:dec.yuv ...]"""
import sys, os, numpy as np
from PIL import Image
src, W, H, od = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]; os.makedirs(od, exist_ok=True)
Wc = W // 2; fw = W * H + 2 * Wc * H
def planes(p, f):
    d = np.fromfile(p, dtype='<u2', count=fw, offset=f * fw * 2).astype(np.float64)
    return d[:W * H].reshape(H, W), d[W * H:W * H + Wc * H].reshape(H, Wc), d[W * H + Wc * H:].reshape(H, Wc)
def rgb(y, cb, cr):
    cb = np.repeat(cb, 2, 1); cr = np.repeat(cr, 2, 1)
    yy = (y / 1023 * 255 - 16 * 255 / 256) * (255 / 219); c1 = (cb / 1023 - .5) * 255 * (255 / 224); c2 = (cr / 1023 - .5) * 255 * (255 / 224)
    return np.clip(np.stack([yy + 1.5748 * c2, yy - .1873 * c1 - .4681 * c2, yy + 1.8556 * c1], -1), 0, 255).astype(np.uint8)
def save(a, p, cw):
    Image.fromarray(a).save(p); g = a.copy()
    if g.ndim == 2: g = np.stack([g] * 3, -1)
    g[::8, :] = (255, 0, 0); g[:, ::cw] = (255, 0, 0); Image.fromarray(g).save(p.replace('.png', '_grid.png'))
def level(e):
    h, w = (e.shape[0] // 8) * 8, (e.shape[1] // 8) * 8
    B = e[:h, :w].reshape(h // 8, 8, w // 8, 8).mean((1, 3)); B = np.kron(B, np.ones((8, 8)))
    out = np.full(e.shape + (3,), 128, np.uint8); v = np.clip(B / 10.0, -1, 1)
    out[:h, :w, 0] = np.clip(128 + 127 * v, 0, 255); out[:h, :w, 2] = np.clip(128 - 127 * v, 0, 255); out[:h, :w, 1] = np.clip(128 - 127 * np.abs(v), 0, 255)
    return out
for f in (8, 11):
    S = planes(src, f); save(rgb(*S), os.path.join(od, 'source_f%d_decode.png' % f), 32)
    for spec in sys.argv[5:]:
        tag, dec = spec.split(':', 1); D = planes(dec, f)
        save(rgb(*D), os.path.join(od, '%s_f%d_decode.png' % (tag, f)), 32)
        for nm, s, d, cw in (('Y', S[0], D[0], 32), ('Cb', S[1], D[1], 16), ('Cr', S[2], D[2], 16)):
            save(level(d - s), os.path.join(od, '%s_f%d_level_%s.png' % (tag, f, nm)), cw)
            save(np.clip(np.abs(d - s) * 8, 0, 255).astype(np.uint8), os.path.join(od, '%s_f%d_absdiff_%s.png' % (tag, f, nm)), cw)
        dark = S[0][:, 0::2] < 0.25 * 1023           # chroma-grid positions of dark luma
        mag_s = np.hypot(S[1] - 512, S[2] - 512)[dark]; mag_d = np.hypot(D[1] - 512, D[2] - 512)[dark]
        print('f%d %-14s dark px %6d | mean err Cb %+.2f Cr %+.2f | mean|err| Cb %.2f Cr %.2f | chroma magnitude ratio %.3f' % (
            f, tag, dark.sum(), (D[1] - S[1])[dark].mean(), (D[2] - S[2])[dark].mean(), np.abs(D[1] - S[1])[dark].mean(), np.abs(D[2] - S[2])[dark].mean(), mag_d.sum() / max(mag_s.sum(), 1)))
