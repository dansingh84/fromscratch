#!/usr/bin/env python3
"""eval_dec.py SRC DEC W H NF SH TAG -- the same instruments on any decode (SA13 or today's OMC).
NEG (negscore.sh, all NF frames), PSNR Y/Cb/Cr frames 2+, level offset per plane frames 8+,
smudgegroups (owner tool) groups per plane summed over frames 8..NF-1, flatplane on frame 10."""
import sys, subprocess, re, os, numpy as np
T = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/shared_tools'
src, dec, W, H, NF, SH, tag = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), sys.argv[6], sys.argv[7]
cw = W // 2; n = W * H + 2 * cw * H
def fr(p, f):
    a = np.fromfile(p, dtype='<u2', count=n, offset=2 * n * f).astype(float)
    return a[:W*H].reshape(H, W), a[W*H:W*H+cw*H].reshape(H, cw), a[W*H+cw*H:].reshape(H, cw)
ps = [[], [], []]; off = [[], [], []]
for f in range(NF):
    s, d = fr(src, f), fr(dec, f)
    for k in range(3):
        if f >= 2: ps[k].append(10 * np.log10(1023 ** 2 / max(np.mean((s[k] - d[k]) ** 2), 1e-9)))
        if f >= 8: off[k].append(np.mean(d[k] - s[k]))
# NEG needs a source file cut to NF frames
cut = dec + '.srccut'
np.fromfile(src, dtype='<u2', count=n * NF).tofile(cut)
neg = subprocess.run(['bash', f'{T}/negscore.sh', cut, dec, str(W), str(H), '422', '10', str(NF)],
                     capture_output=True, text=True).stdout.strip().split()[-1]
sm = [0, 0, 0]
for f in range(8, NF):
    o = subprocess.run(['python3', f'{T}/smudgegroups.py', cut, dec, str(W), str(H), str(f),
                        f'/tmp/claude-1000/-home-dan-Documents-Apps-Codec/349df860-b2b7-4717-bcf8-5bdc1c07368a/scratchpad/sg_{tag}',
                        '--sh', SH, '--fmt', '422'], capture_output=True, text=True).stdout
    for k, nm in enumerate(('Y', 'Cb', 'Cr')):
        m = re.search(rf'^{nm}: (\d+) groups', o, re.M); sm[k] += int(m.group(1)) if m else -999
fp = subprocess.run(['python3', f'{T}/flatplane.py', cut, dec, str(W), str(H), str(min(10, NF - 1)),
                     '--fmt', '422', '--depth', '10'], capture_output=True, text=True).stdout.strip()
os.remove(cut)
print(f'{tag} NEG={neg} PSNR(f2+) Y/Cb/Cr {np.mean(ps[0]):.2f}/{np.mean(ps[1]):.2f}/{np.mean(ps[2]):.2f} '
      f'offset(f8+) {np.mean(off[0]):+.3f}/{np.mean(off[1]):+.3f}/{np.mean(off[2]):+.3f} '
      f'smudge groups f8+ Y/Cb/Cr {sm[0]}/{sm[1]}/{sm[2]} | flat f10: {fp}', flush=True)
