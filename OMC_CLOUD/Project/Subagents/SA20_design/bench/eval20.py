#!/usr/bin/env python3
# eval20.py SRC DEC W H [FMT=422] [DEPTH=10] [TAG]
# VMAF-NEG per frame over ALL frames (so frame 2 carries its real motion feature; the owner's model, same
# ffmpeg call as shared_tools/vmafneg.sh), then PSNR Y/Cb/Cr per frame. Prints mean over steady frames
# (2..N-1) first, then per frame. With 3-frame clips steady = frame 2 only (= worst frame).
import sys, json, subprocess, numpy as np
src, dec, W, H = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
fmt = sys.argv[5] if len(sys.argv) > 5 else '422'; dep = int(sys.argv[6]) if len(sys.argv) > 6 else 10
tag = sys.argv[7] if len(sys.argv) > 7 else dec
MODEL = '/home/user/fromscratch/OMC_CLOUD/vmaf_model/vmaf_v0.6.1neg.json'
cw = W if fmt == '444' else W // 2; fs = W * H + 2 * cw * H
s = np.fromfile(src, '<u2'); d = np.fromfile(dec, '<u2'); N = min(s.size, d.size) // fs
pf = ('yuv444p' if fmt == '444' else 'yuv422p') + '%dle' % dep
cmd = ['ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', pf, '-s', '%dx%d' % (W, H), '-i', dec,
       '-f', 'rawvideo', '-pix_fmt', pf, '-s', '%dx%d' % (W, H), '-i', src, '-frames:v', str(N),
       '-lavfi', '[0:v]trim=end_frame=%d[d];[1:v]trim=end_frame=%d[r];[d][r]libvmaf=model=path=%s:n_threads=4:log_fmt=json:log_path=/dev/stdout' % (N, N, MODEL),
       '-f', 'null', '-']
j = json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)
neg = [f['metrics']['vmaf'] for f in j['frames']]
mx = (1 << dep) - 1; segs = [(0, W * H), (W * H, cw * H), (W * H + cw * H, cw * H)]
ps = []
for f in range(N):
    row = []
    for o, n in segs:
        e = d[f*fs+o:f*fs+o+n].astype(float) - s[f*fs+o:f*fs+o+n]
        row.append(10 * np.log10(mx * mx / max((e * e).mean(), 1e-12)))
    ps.append(row)
st = list(range(2, N)) or [N - 1]
m = np.mean([neg[i] for i in st]); w = min(neg[i] for i in st); P = np.mean([ps[i] for i in st], 0); Pw = np.min([ps[i] for i in st], 0)
print('%s NEG %.3f (worst %.3f) PSNR %.2f/%.2f/%.2f (worst %.2f/%.2f/%.2f) | all-frame NEG %.3f | per-frame NEG %s' % (
    tag, m, w, P[0], P[1], P[2], Pw[0], Pw[1], Pw[2], np.mean(neg), ' '.join('%.2f' % v for v in neg)))
