#!/usr/bin/env python3
# intra_eval.py CLIP R LOG : for an intra arm (env F / RHOK / RHO as in the run that wrote LOG), pick the step whose
# logged S16 bpp is closest to R, re-code frame 0, and report vs today's f0 at R:
#   NEG + VIF/ADM per scale, per-band error ratio (Y/Cb/Cr), owner smudgegroups (thr 6 dens 0.4) per plane.
import sys, os, re, json, subprocess, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from d1_screen import read
from n4_core import po
W, H = 1280, 720; ROOT = '/home/user/fromscratch/OMC_CLOUD/'; MODEL = ROOT + 'vmaf_model/vmaf_v0.6.1neg.json'
TOOLS = ROOT + 'Project/Subagents/shared_tools/'
CLIP, R, LOG = sys.argv[1], float(sys.argv[2]), sys.argv[3]; F = float(os.environ.get('F', '0.7'))
pts = [(float(m.group(2)), float(m.group(1))) for m in (re.match(r'\S+ \S+ Q=(\S+) bpp (\S+)', l) for l in open(LOG)) if m]
bpp, Q = min(pts, key=lambda p: abs(np.log2(p[0] / R)))
src = ROOT + 'Project/.work/arms/%s_1280x720_422_10.yuv' % CLIP; x = read(src, W, H, 0)
tag = os.path.basename(LOG).replace('.log', ''); tmp = '/tmp/claude-0/-home-user-fromscratch/ca3365f6-68f7-5957-a3a2-a3df5f0ee7ba/scratchpad/ie_%s_%s' % (tag, R)
ours = [po(p, Q, F, 0, [])[1] for p in x]
with open(tmp + '_o.yuv', 'wb') as f:
    for p in ours: p.astype('<u2').tofile(f)
with open(tmp + '_s.yuv', 'wb') as f:
    for p in x: p.astype('<u2').tofile(f)
tdec = ROOT + 'scratch/today/%s_1280x720_b%s.d.yuv' % (CLIP, sys.argv[2]); t = read(tdec, W, H, 0)
def feats(dec):
    cmd = ['ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'yuv422p10le', '-s', '%dx%d' % (W, H), '-i', dec,
           '-f', 'rawvideo', '-pix_fmt', 'yuv422p10le', '-s', '%dx%d' % (W, H), '-i', tmp + '_s.yuv', '-frames:v', '1',
           '-lavfi', 'libvmaf=model=path=%s:log_fmt=json:log_path=/dev/stdout' % MODEL, '-f', 'null', '-']
    return json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)['frames'][0]['metrics']
def box(e, k):
    if k == 0: return e.astype(float)
    b = 2 ** k; h, w = (e.shape[0] // b) * b, (e.shape[1] // b) * b
    return np.repeat(np.repeat(e[:h, :w].astype(float).reshape(h // b, b, w // b, b).mean(axis=(1, 3)), b, 0), b, 1)
def bands(e):
    h, w = (e.shape[0] // 32) * 32, (e.shape[1] // 32) * 32; e = e[:h, :w]
    return [((box(e, k) - box(e, k + 1)) ** 2).mean() for k in range(5)] + [(box(e, 5) ** 2).mean()]
def smudge(dec):
    out = subprocess.run(['python3', TOOLS + 'smudgegroups.py', src, dec, str(W), str(H), '0', tmp + '_sg', '--thr', '6', '--dens', '0.4'],
                         capture_output=True, text=True).stdout
    return ' '.join('%s%s' % (m.group(1), m.group(2)) for m in re.finditer(r'^(Y|Cb|Cr): (\d+) groups', out, re.M))
o, tt = feats(tmp + '_o.yuv'), feats(tdec)
ps = lambda a, b: 10 * np.log10(1023 ** 2 / ((a - b).astype(float) ** 2).mean())
print('%s %s @%.1f Q=%.2f bpp %.3f | NEG %+.2f | PSNR %s | VIF s0..3 %s | ADM s0..3 %s' % (CLIP, tag, R, Q, bpp, o['vmaf'] - tt['vmaf'],
      '/'.join('%+.2f' % (ps(a, s) - ps(b, s)) for a, b, s in zip(ours, t, x)),
      ' '.join('%+.3f' % (o['integer_vif_scale%d_egl_1' % k] - tt['integer_vif_scale%d_egl_1' % k]) for k in range(4)),
      ' '.join('%+.3f' % (o['integer_adm_scale%d_egl_1' % k] - tt['integer_adm_scale%d_egl_1' % k]) for k in range(4))), flush=True)
for k, nm in enumerate(('Y', 'Cb', 'Cr')):
    print('   band ratio %s ' % nm + ' '.join('%.2f' % (a / max(b, 1e-9)) for a, b in zip(bands(ours[k] - x[k]), bands(t[k] - x[k]))))
print('   smudge groups ours %s | today %s' % (smudge(tmp + '_o.yuv'), smudge(tdec)), flush=True)
