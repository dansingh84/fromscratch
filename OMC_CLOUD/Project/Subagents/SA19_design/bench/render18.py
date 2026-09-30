# SA18 renders (owner rules): per plane Y | Cb | Cr side by side, full frame, full resolution:
#  row 1: level map (decoded plane, grey, legend 0..max code); row 2: |decode - source| (heat, legend 0..R codes);
#  row 3: the same diff with the slice grid (red lines every S rows); plus a x4 magnified strip across two slice edges.
# usage: render18.py SRC DEC W H FRAME S OUTPREFIX [R=16]
import sys, numpy as np
from PIL import Image, ImageDraw
src, dec, W, H, f, S, out = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), int(sys.argv[6]), sys.argv[7]
R = int(sys.argv[8]) if len(sys.argv) > 8 else 16
Wc = W // 2; fw = W * H + 2 * Wc * H
def planes(p):
    d = np.fromfile(p, dtype='<u2', count=fw, offset=2 * fw * f).astype(np.int64)
    return [d[:W * H].reshape(H, W), d[W * H:W * H + Wc * H].reshape(H, Wc), d[W * H + Wc * H:].reshape(H, Wc)]
S_, D_ = planes(src), planes(dec)
def heat(v):     # 0 -> black, R -> white through blue/red/yellow
    t = np.clip(v / R, 0, 1)
    return np.stack([np.clip(3 * t, 0, 1), np.clip(3 * t - 1, 0, 1), np.clip(3 * t - 2, 0, 1) + np.clip(1 - 3 * np.abs(t - 1 / 6) * 2, 0, 1) * 0.6], -1)
def legend(h, kind):
    v = np.linspace(1, 0, h)[:, None] * np.ones((1, 24))
    img = heat(v * R) if kind == 'heat' else np.repeat((v)[..., None], 3, -1)
    return (img * 255).astype(np.uint8)
panels = []
for i, name in enumerate(('Y', 'Cb', 'Cr')):
    s, d = S_[i], D_[i]
    if s.shape[1] != W: s = np.repeat(s, 2, 1); d = np.repeat(d, 2, 1)
    lvl = np.repeat((d / 1023.0)[..., None], 3, -1)
    df = heat(np.abs(d - s))
    grid = df.copy(); grid[::S] = [1, 0, 0]
    col = np.concatenate([lvl, df, grid], 0)
    col = (col * 255).astype(np.uint8)
    lg = np.concatenate([legend(H, 'grey'), legend(H, 'heat'), legend(H, 'heat')], 0)
    panels.append(np.concatenate([col, lg, np.zeros((3 * H, 8, 3), np.uint8)], 1))
img = Image.fromarray(np.concatenate(panels, 1)); dr = ImageDraw.Draw(img)
for i, name in enumerate(('Y', 'Cb', 'Cr')):
    x0 = i * (W + 32)
    dr.text((x0 + 4, 4), '%s level (legend 0..1023)' % name, fill=(255, 255, 0))
    dr.text((x0 + 4, H + 4), '%s |dec-src| (legend 0..%d codes)' % (name, R), fill=(255, 255, 0))
    dr.text((x0 + 4, 2 * H + 4), '%s |dec-src| + slice grid (S=%d, red)' % (name, S), fill=(255, 255, 0))
img.save(out + '_maps.png')
# x4 magnified strip across two slice edges (rows y0..y0+3S, first 320 columns), per plane diff, nearest-neighbour
y0 = (H // 2 // S) * S - S; strips = []
for i in range(3):
    s, d = S_[i], D_[i]
    if s.shape[1] != W: s = np.repeat(s, 2, 1); d = np.repeat(d, 2, 1)
    st = heat(np.abs(d - s)[y0:y0 + 3 * S, :320]); st[[S, 2 * S]] = [1, 0, 0] if False else st[[S, 2 * S]]
    st = np.repeat(np.repeat(st, 4, 0), 4, 1)
    for k in (S, 2 * S): st[4 * k - 1] = [1, 0, 0]
    strips.append((st * 255).astype(np.uint8)); strips.append(np.zeros((st.shape[0], 8, 3), np.uint8))
Image.fromarray(np.concatenate(strips, 1)).save(out + '_x4strip.png')
print('wrote', out + '_maps.png', out + '_x4strip.png')
