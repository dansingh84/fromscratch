#!/usr/bin/env python3
# visual_check.py SRC DEC TODAY NF [W H] : per plane and frame, ours vs today (both against the source)
#   smudge  : owner smudgegroups (thr 6, dens 0.4) group count
#   lines   : rows / columns whose mean |error| exceeds 1.5x the median of the 17 rows / columns around them
#             (count, and the worst ratio); content lines hit both codecs, so compare against today
#   phase   : max/min mean |error| over sample phase (row mod 4, column mod 32 = the kept-grid period of the
#             pyramid: 2 two-D levels + 3 horizontal levels); 1.00 = no grid pattern
#   seams   : mean |signed error step| between neighbours ACROSS a B-px boundary / elsewhere, B = 8, 16, 32
#             (1.00 = no seam; the still/grain decisions are per 16x16 luma / 8x16 chroma block)
import sys, re, subprocess, numpy as np
src, dec, tdy, NF = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
W, H = (int(sys.argv[5]), int(sys.argv[6])) if len(sys.argv) > 6 else (1280, 720)
TOOLS = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/shared_tools/'
TMP = '/tmp/claude-0/-home-user-fromscratch/ca3365f6-68f7-5957-a3a2-a3df5f0ee7ba/scratchpad/vc'
def rd(fn, f):
    n = W * H * 2; a = np.fromfile(fn, '<u2', n, offset=f * n * 2).astype(float)
    return [a[:W * H].reshape(H, W), a[W * H:W * H * 3 // 2].reshape(H, W // 2), a[W * H * 3 // 2:].reshape(H, W // 2)]
def lines(e):
    out = []
    for prof in (e.mean(1), e.mean(0)):
        pad = np.pad(prof, 8, mode='reflect'); med = np.array([np.median(pad[i:i + 17]) for i in range(prof.size)])
        r = prof / np.maximum(med, 0.05); out += [int((r > 1.5).sum()), float(r.max())]
    return out   # rows>1.5, worst row, cols>1.5, worst col
def phase(e, px):
    pr = [e[k::4].mean() for k in range(4)]; pc = [e[:, k::px].mean() for k in range(px)]
    return max(pr) / max(min(pr), 1e-3), max(pc) / max(min(pc), 1e-3)
def seams(s, B):
    dx = np.abs(np.diff(s, axis=1)); dy = np.abs(np.diff(s, axis=0))
    bx = (np.arange(1, s.shape[1]) % B) == 0; by = (np.arange(1, s.shape[0]) % B) == 0
    return dx[:, bx].mean() / max(dx[:, ~bx].mean(), 1e-3), dy[by].mean() / max(dy[~by].mean(), 1e-3)
def smudge(fn, f):
    o = subprocess.run(['python3', TOOLS + 'smudgegroups.py', src, fn, str(W), str(H), str(f), TMP, '--thr', '6', '--dens', '0.4'],
                       capture_output=True, text=True).stdout
    return {m.group(1): int(m.group(2)) for m in re.finditer(r'^(Y|Cb|Cr): (\d+) groups', o, re.M)}
for f in range(NF):
    x, o, t = rd(src, f), rd(dec, f), rd(tdy, f); so, st = smudge(dec, f), smudge(tdy, f)
    for k, nm in enumerate(('Y', 'Cb', 'Cr')):
        px = 32 if k == 0 else 16
        row = []
        for d in (o, t):
            s = d[k] - x[k]; e = np.abs(s); L = lines(e); P = phase(e, px)
            S = [seams(s, B) for B in ((8, 16, 32) if k == 0 else (4, 8, 16))]
            row.append('lines r%d/%.2f c%d/%.2f phase %.2f/%.2f seams %s' % (L[0], L[1], L[2], L[3], P[0], P[1],
                       ' '.join('%.2f/%.2f' % v for v in S)))
        print('f%d %-2s smudge %d|%d  OURS %s  || TODAY %s' % (f, nm, so.get(nm, -1), st.get(nm, -1), row[0], row[1]), flush=True)
