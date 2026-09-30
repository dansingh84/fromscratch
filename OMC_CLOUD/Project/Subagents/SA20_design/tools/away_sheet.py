#!/usr/bin/env python3
# away_sheet.py PREFIX N OUT : stack the N worst crops of renders/away/PREFIX_* into one labelled sheet
import sys, glob, os
from PIL import Image, ImageDraw, ImageFont
D = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design/renders/away/'
fs = sorted(glob.glob(D + sys.argv[1] + '_*.png'))[:int(sys.argv[2])]
ims = [Image.open(f).convert('L') for f in fs]; w = max(i.width for i in ims); hh = 22
font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 14)
sheet = Image.new('L', (w, hh + sum(i.height + hh for i in ims)), 40); d = ImageDraw.Draw(sheet)
d.text((4, 3), 'source | legal decode (averaging + clamp) | same bits, plain clip | extra error from legality', fill=255, font=font)
y = hh
for f, i in zip(fs, ims):
    d.text((4, y + 3), os.path.basename(f)[:-4], fill=200, font=font); y += hh; sheet.paste(i, (0, y)); y += i.height
sheet.save(sys.argv[3]); print(sys.argv[3], sheet.size)
