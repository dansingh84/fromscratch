#!/usr/bin/env python3
# dp_score.py LOG SRC W H : frame-2 VMAF-NEG (all-frame run, frame 2 value) + PSNR Y/Cb/Cr of every decode in a
# dp_screen log; per arm the upper hull over f; values at 0.25/0.5/1.0 mean bpp by interpolation in log2(bpp).
import os, sys, re, json, subprocess, numpy as np
log, src, W, H = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
MODEL = '/home/user/fromscratch/OMC_CLOUD/vmaf_model/vmaf_v0.6.1neg.json'
def neg(dec):
    cmd = ['ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'yuv422p10le', '-s', '%dx%d' % (W, H), '-i', dec,
           '-f', 'rawvideo', '-pix_fmt', 'yuv422p10le', '-s', '%dx%d' % (W, H), '-i', src, '-frames:v', '3',
           '-lavfi', '[0:v]trim=end_frame=3[d];[1:v]trim=end_frame=3[r];[d][r]libvmaf=model=path=%s:n_threads=4:log_fmt=json:log_path=/dev/stdout' % MODEL,
           '-f', 'null', '-']
    j = json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)
    return j['frames'][2]['metrics']['vmaf']
pts = {}
for l in open(log):
    m = re.match(r'(\S+)_(AVG|DPI|DP)(f[\d.]+)?_([\d.]+) bpp f0/f1/f2 \S+ mean ([\d.]+) \| f2 PSNR ([\d.]+)/([\d.]+)/([\d.]+) \| (\S+)', l)
    if not m: continue
    arm = m.group(2); r = float(m.group(5)); ps = [float(m.group(i)) for i in (6, 7, 8)]
    pts.setdefault(arm, []).append((r, [neg(m.group(9))] + ps))
def at(p, r, k):  # hull: for each rate take the best value among points with rate <= r (monotone), interpolate
    p = sorted(p); x = np.log2([a for a, _ in p]); y = np.maximum.accumulate([b[k] for _, b in p])
    return float(np.interp(np.log2(r), x, y))
for r in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0):
    a = [at(pts['AVG'], r, k) for k in range(4)]; d = [at(pts[os.environ.get('ARM','DP')], r, k) for k in range(4)]
    print('@%.2f AVG NEG %.2f PSNR %.2f/%.2f/%.2f | DP NEG %.2f PSNR %.2f/%.2f/%.2f | DP-AVG NEG %+.2f PSNR %+.2f/%+.2f/%+.2f' % (
        r, *a, *d, *[d[k] - a[k] for k in range(4)]))
