#!/usr/bin/env python3
# make_titles.py : synthetic legality stress clips (DESIGN H24), 1280x720 4:2:2 10-bit, 2 identical frames each
#   title_full : white text 1019 on black 4 (full-range rails), several sizes, plus a near-black ramp 4..40 and a
#                hard-clipped highlight disc (1019 plateau with a soft shoulder); chroma neutral 512
#   title_narrow: the same layout at video levels (text 940 on 64, ramp 64..100, plateau 940)
import numpy as np
from PIL import Image, ImageDraw, ImageFont
A = '/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/'; W, H = 1280, 720
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
def luma(bg, fg):
    im = Image.new('L', (W, H), 0); d = ImageDraw.Draw(im); y = 20
    for sz in (72, 40, 24, 14):
        d.text((30, y), 'EXACT LEGAL 0123 Wxyz', font=ImageFont.truetype(FONT, sz), fill=255); y += sz + 20
    m = np.asarray(im, float) / 255.0
    x = bg + (fg - bg) * m
    x[560:640, :] = bg + (np.arange(W) / (W - 1))[None, :] * 36          # near-black ramp, 36 codes over the width
    yy, xx = np.mgrid[:H, :W]; r = np.hypot(yy - 380, xx - 1050)
    x = np.where(r < 150, np.minimum(fg, bg + (fg - bg) * np.clip((170 - r) / 40, 0, 1) * 1.3), x)   # clipped highlight
    return np.clip(np.round(x), 0, 1023).astype('<u2')
for name, bg, fg in (('title_full', 4, 1019), ('title_narrow', 64, 940)):
    y = luma(bg, fg); c = np.full((H, W // 2), 512, '<u2')
    with open(A + '%s_1280x720_422_10.yuv' % name, 'wb') as f:
        for _ in range(2):
            y.tofile(f); c.tofile(f); c.tofile(f)
    print(name, 'written')
