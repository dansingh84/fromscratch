#!/usr/bin/env python3
# today_perframe.py CLIP... : today's (v537) per-frame NEG and PSNR Y/Cb/Cr at 720p for every owner rate, from the
# decodes in scratch/today. Output lines match out/today_eval.txt ("per-frame NEG a b c", PSNR of the LAST frame).
import sys, json, subprocess, numpy as np
ROOT = '/home/user/fromscratch/OMC_CLOUD/'; W, H = 1280, 720; MODEL = ROOT + 'vmaf_model/vmaf_v0.6.1neg.json'
for c in sys.argv[1:]:
    src = ROOT + 'Project/.work/arms/%s_1280x720_422_10.yuv' % c
    for r in ('0.5', '1.0', '1.5', '2.0', '2.5', '3.0', '4.0'):
        dec = ROOT + 'scratch/today/%s_1280x720_b%s.d.yuv' % (c, r)
        cmd = ['ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'yuv422p10le', '-s', '%dx%d' % (W, H), '-i', dec,
               '-f', 'rawvideo', '-pix_fmt', 'yuv422p10le', '-s', '%dx%d' % (W, H), '-i', src,
               '-lavfi', 'libvmaf=model=path=%s:n_threads=4:log_fmt=json:log_path=/dev/stdout' % MODEL, '-f', 'null', '-']
        ng = [f['metrics']['vmaf'] for f in json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)['frames']]
        fs = W * H * 2; n = len(ng); s = np.fromfile(src, '<u2', count=fs * n).astype(float); d = np.fromfile(dec, '<u2', count=fs * n).astype(float)
        o = fs * (n - 1); seg = [(o, W * H), (o + W * H, W * H // 2), (o + W * H * 3 // 2, W * H // 2)]
        ps = [10 * np.log10(1023 ** 2 / ((d[a:a+b] - s[a:a+b]) ** 2).mean()) for a, b in seg]
        print('%s_1280x720_b%s NEG %.3f (worst %.3f) PSNR %.2f/%.2f/%.2f (last frame) | per-frame NEG %s' % (
            c, r, ng[-1], min(ng[1:]) if n > 1 else ng[0], *ps, ' '.join('%.2f' % v for v in ng)), flush=True)
