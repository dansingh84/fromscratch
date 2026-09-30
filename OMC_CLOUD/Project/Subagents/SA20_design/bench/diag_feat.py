#!/usr/bin/env python3
# diag_feat.py CLIP R LOG: VMAF-NEG feature breakdown (ADM, VIF per scale, motion) ours (PO intra at the step whose
# logged bpp ~ R) vs today's frame 0 at R.
import sys, os, re, json, subprocess, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from d1_screen import read
from n4_core import po
W, H = 1280, 720; ROOT = '/home/user/fromscratch/OMC_CLOUD/'; MODEL = ROOT + 'vmaf_model/vmaf_v0.6.1neg.json'
CLIP, R, LOG = sys.argv[1], float(sys.argv[2]), sys.argv[3]
pts = [(float(m.group(2)), float(m.group(1))) for m in (re.match(r'\S+ \S+ Q=(\S+) bpp (\S+)', l) for l in open(LOG)) if m]
Q = min(pts, key=lambda p: abs(np.log2(p[0] / R)))[1]
src = ROOT + 'Project/.work/arms/%s_1280x720_422_10.yuv' % CLIP; x = read(src, W, H, 0)
tmp = '/tmp/claude-0/-home-user-fromscratch/ca3365f6-68f7-5957-a3a2-a3df5f0ee7ba/scratchpad/'
with open(tmp + 'o.yuv', 'wb') as f:
    for p in [po(p, Q, 0.7, 0, [])[1] for p in x]: p.astype('<u2').tofile(f)
with open(tmp + 's.yuv', 'wb') as f:
    for p in x: p.astype('<u2').tofile(f)
t = read(ROOT + 'scratch/today/%s_1280x720_b%s.d.yuv' % (CLIP, sys.argv[2]), W, H, 0)
with open(tmp + 't.yuv', 'wb') as f:
    for p in t: p.astype('<u2').tofile(f)
def feats(dec):
    cmd = ['ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'yuv422p10le', '-s', '%dx%d' % (W, H), '-i', dec,
           '-f', 'rawvideo', '-pix_fmt', 'yuv422p10le', '-s', '%dx%d' % (W, H), '-i', tmp + 's.yuv',
           '-lavfi', 'libvmaf=model=path=%s:log_fmt=json:log_path=/dev/stdout' % MODEL, '-f', 'null', '-']
    return json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)['frames'][0]['metrics']
o, tt = feats(tmp + 'o.yuv'), feats(tmp + 't.yuv')
print('%s @%.1f ours Q=%.2f' % (CLIP, R, Q))
for k in sorted(o): print('  %-32s ours %.4f today %.4f diff %+.4f' % (k, o[k], tt[k], o[k] - tt[k]))
