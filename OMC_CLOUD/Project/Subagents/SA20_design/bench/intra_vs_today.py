#!/usr/bin/env python3
# intra_vs_today.py LOG... : compares real-code intra frame-0 curves (rcl_intra / rcl_fi logs) with TODAY's frame 0
# (v537 real decode; frame 0 is pure intra at exactly the stream rate) at the owner's rates 0.5..4.0.
# Our curve is interpolated in log2(bpp) between measured points (all >= 0.5 bpp; at 0.5 the lowest two points
# are extrapolated linearly if no point lies below). Prints NEG then PSNR Y/Cb/Cr, ours - today.
import sys, re, json, subprocess, numpy as np
RATES = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0]; W, H = 1280, 720
ROOT = '/home/user/fromscratch/OMC_CLOUD/'
MODEL = ROOT + 'vmaf_model/vmaf_v0.6.1neg.json'
def today_f0(clip, r):
    src = ROOT + 'Project/.work/arms/%s_1280x720_422_10.yuv' % clip; dec = ROOT + 'scratch/today/%s_1280x720_b%s.d.yuv' % (clip, r)
    fs = W * H * 2; s = np.fromfile(src, '<u2', count=fs).astype(float); d = np.fromfile(dec, '<u2', count=fs).astype(float)
    seg = [(0, W * H), (W * H, W * H // 2), (W * H * 3 // 2, W * H // 2)]
    ps = [10 * np.log10(1023 ** 2 / ((d[o:o+n] - s[o:o+n]) ** 2).mean()) for o, n in seg]
    cmd = ['ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'yuv422p10le', '-s', '%dx%d' % (W, H), '-i', dec,
           '-f', 'rawvideo', '-pix_fmt', 'yuv422p10le', '-s', '%dx%d' % (W, H), '-i', src, '-frames:v', '1',
           '-lavfi', 'libvmaf=model=path=%s:n_threads=4:log_fmt=json:log_path=/dev/stdout' % MODEL, '-f', 'null', '-']
    n = json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)['frames'][0]['metrics']['vmaf']
    return [n] + ps
def interp(pts, r, k):
    p = sorted(p for p in pts if p[0] >= 0.5); x = np.log2([a[0] for a in p]); y = np.maximum.accumulate([a[1][k] for a in p])
    if np.log2(r) < x[0]:
        return float(y[0] + (y[1] - y[0]) * (np.log2(r) - x[0]) / (x[1] - x[0]))
    return float(np.interp(np.log2(r), x, y))
TC = {}
for log in sys.argv[1:]:
    pts = {}
    for l in open(log):
        m = re.match(r'(\S+) (\S+) Q=\S+ bpp (\S+) NEG (\S+) PSNR (\S+)/(\S+)/(\S+)', l)
        if m: pts.setdefault((m.group(1), m.group(2)), []).append((float(m.group(3)), [float(v) for v in m.groups()[3:7]]))
    for (clip, arm), p in pts.items():
        if len(p) < 2: continue
        rows = []
        for r in RATES:
            if r > max(a[0] for a in p) * 1.02: continue
            if (clip, r) not in TC: TC[(clip, r)] = today_f0(clip, r)
            t = TC[(clip, r)]; o = [interp(p, r, k) for k in range(4)]
            rows.append('@%.1f NEG %.2f (today %.2f, %+.2f) PSNR %+.2f/%+.2f/%+.2f' % (r, o[0], t[0], o[0] - t[0], *[o[k] - t[k] for k in (1, 2, 3)]))
        print('%s %s\n  ' % (clip, arm) + '\n  '.join(rows), flush=True)
