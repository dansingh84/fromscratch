# renders: colour decode (with and without the slice grid), per-plane signed error level maps and |dec-src| maps,
# with colour legends, whole frame, vertically magnified x4 so a one-row feature is >= 4 output pixels.
import sys, os, numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import yuv
def rgb(y, cb, cr, W):
    if cb.shape[1] != W: cb = np.repeat(cb, 2, 1)[:, :W]; cr = np.repeat(cr, 2, 1)[:, :W]
    mx = 1023.0; yy = (y / mx * 255 - 16 * 255 / 256) * (255 / 219); c1 = (cb / mx - 0.5) * 255 * (255 / 224); c2 = (cr / mx - 0.5) * 255 * (255 / 224)
    return np.clip(np.stack([yy + 1.5748 * c2, yy - 0.1873 * c1 - 0.4681 * c2, yy + 1.8556 * c1], -1), 0, 255).astype(np.uint8)
def signed_map(e, sat):
    """red = decode brighter, blue = darker, saturating at +-sat codes."""
    v = np.clip(e / sat, -1, 1); img = np.zeros(e.shape + (3,), np.uint8)
    img[..., 0] = np.clip(255 * np.maximum(v, 0), 0, 255); img[..., 2] = np.clip(255 * np.maximum(-v, 0), 0, 255)
    img[..., 1] = np.clip(255 * (1 - np.abs(v)) * 0.15, 0, 255); return img
def abs_map(e, sat):
    v = np.clip(np.abs(e) / sat, 0, 1); img = np.zeros(e.shape + (3,), np.uint8)
    img[..., 0] = (255 * v).astype(np.uint8); img[..., 1] = (255 * v ** 2).astype(np.uint8); img[..., 2] = (255 * (v > 0.999)).astype(np.uint8); return img
def legend(img, text, sat, kind):
    W = img.shape[1]; bar = np.zeros((24, W, 3), np.uint8); xs = np.linspace(-1 if kind == 'signed' else 0, 1, W)
    if kind == 'signed': bar[:] = signed_map(xs[None, :] * sat, sat).repeat(24, 0)
    else: bar[:] = abs_map(xs[None, :] * sat, sat).repeat(24, 0)
    out = Image.fromarray(np.concatenate([bar, img], 0)); d = ImageDraw.Draw(out)
    d.text((4, 4), '%s   legend: %s%d .. %+d codes (10-bit)' % (text, '-' if kind == 'signed' else '', sat, sat), fill=(255, 255, 255)); return out
def grid(img, S, mag, color=(0, 255, 0)):
    a = np.array(img); a[S * mag::S * mag, :, :] = color; return Image.fromarray(a)
def run(src, dec, W, H, f, S, outp, tag, sat=8, mag=4):
    s = yuv.read_frame(src, W, H, f); d = yuv.read_frame(dec, W, H, f)
    col = Image.fromarray(rgb(d[0], d[1], d[2], W)); col.save(outp + '_%s_decode.png' % tag)
    grid(col, S, 1).save(outp + '_%s_decode_grid.png' % tag)
    for p, name in enumerate(('Y', 'Cb', 'Cr')):
        e = (d[p] - s[p]).astype(np.float64); e4 = np.repeat(e, mag, 0)
        legend(signed_map(e4, sat), '%s %s f%d signed error (x%d vertical)' % (tag, name, f, mag), sat, 'signed').save(outp + '_%s_%s_signed_x%d.png' % (tag, name, mag))
        grid(legend(signed_map(e4, sat), '%s %s f%d signed error + slice grid' % (tag, name, f), sat, 'signed'), S, mag).save(outp + '_%s_%s_signed_x%d_grid.png' % (tag, name, mag))
        legend(abs_map(e4, sat * 2), '%s %s f%d |decode-source| (x%d vertical)' % (tag, name, f, mag), sat * 2, 'abs').save(outp + '_%s_%s_abs_x%d.png' % (tag, name, mag))
        # 8x8-mean level map (owner's level-map view) at x4
        bh, bw = e.shape[0] // 8, e.shape[1] // 8; lv = e[:bh * 8, :bw * 8].reshape(bh, 8, bw, 8).mean(axis=(1, 3))
        lv8 = np.repeat(np.repeat(lv, 8 * mag, 0), 8, 1)
        legend(signed_map(lv8, sat / 2), '%s %s f%d 8x8 level map' % (tag, name, f), sat / 2, 'signed').save(outp + '_%s_%s_level_x%d.png' % (tag, name, mag))
if __name__ == '__main__':
    src, dec, W, H, f, S, outp, tag = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]), sys.argv[7], sys.argv[8]
    os.makedirs(os.path.dirname(outp), exist_ok=True); run(src, dec, W, H, f, S, outp, tag)
