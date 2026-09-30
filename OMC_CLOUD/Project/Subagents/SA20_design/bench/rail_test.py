#!/usr/bin/env python3
# rail_test.py — never-away and artifact check of form (i) intra (rho 0.42, S16 real code lengths) on the rail clips.
# For each cell x rate: every frame coded intra at the step whose S16 cost ~ the rate; the SAME frame also decoded
# rail-free (LO/HI = +-inf -> the legality-blind value u). Reports per plane:
#   oob (must be 0); AWAY = samples with |out - src| > |clip(u) - src| (must be 0); TOUCHED = in-range u samples whose
#   output differs from u (must be 0); near-rail level shift = mean signed error in 8x8 blocks whose source mean lies
#   within 32 codes of a rail, ours vs the rail-free decode; owner smudgegroups (thr 6 dens 0.4) + artifactmap per plane.
# Writes decodes to out/rail/ for renders.
import sys, os, re, subprocess, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('RHO', '0.42')
import n4_core
from n4_core import po
SA7 = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/'
TOOLS = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/shared_tools/'
OUT = os.path.join(os.path.dirname(__file__), '..', 'out', 'rail')
CELLS = {'cut24': ('cut24.yuv', 256, 64, 0, 1023, 24), 'ext10': ('ext_10_422_l0.yuv', 512, 128, 0, 1023, 4),
         'ext10l1': ('ext_10_422_l1.yuv', 512, 128, 4, 1019, 4)}
def frames(fn, W, H, n):
    d = np.fromfile(SA7 + fn, '<u2').astype(np.int64); fs = W * H * 2
    return [[d[i*fs:i*fs+W*H].reshape(H, W), d[i*fs+W*H:i*fs+W*H*3//2].reshape(H, W // 2), d[i*fs+W*H*3//2:(i+1)*fs].reshape(H, W // 2)] for i in range(n)]
def ent_bits(SY):   # zeroth-order entropy per symbol array (rate proxy for choosing the step on these small cells)
    b = 0.0
    for _, q in SY:
        v, c = np.unique(q, return_counts=True); p = c / c.sum(); b += -(c * np.log2(p)).sum()
    return b
def code(x, Q, lo, hi):
    n4_core.LO, n4_core.HI = lo, hi; SY = []; outs = []
    for pl, p in enumerate(x): outs.append(po(p, Q, 0.7, 0, SY)[1])
    return outs, ent_bits(SY)
res = []
for name, (fn, W, H, lo, hi, n) in CELLS.items():
    X = frames(fn, W, H, min(n, 6))
    for R in (0.5, 1.0, 2.0):
        decs = []; decu = []; st = dict(oob=0, away=0, touched=0)
        for x in X:
            Qs = [2 ** (e / 4) for e in range(0, 32)]; Qb = Qs[-1]
            for Q in Qs:
                o, b = code(x, Q, lo, hi)
                if b <= R * W * H: Qb = Q; break
            o, _ = code(x, Qb, lo, hi); u, _ = code(x, Qb, -10 ** 9, 10 ** 9)
            for k in range(3):
                cu = np.clip(u[k], lo, hi)
                st['oob'] += int(((o[k] < lo) | (o[k] > hi)).sum())
                st['away'] += int((np.abs(o[k] - x[k]) > np.abs(cu - x[k])).sum())
                st['touched'] += int(((u[k] >= lo) & (u[k] <= hi) & (o[k] != u[k])).sum())
            decs.append(o); decu.append(u)
        # near-rail level shift (luma + chroma), ours vs rail-free, over 8x8 blocks near a rail
        shifts = []
        for k in range(3):
            so, su, nb = [], [], 0
            for x, o, u in zip(X, decs, decu):
                h, w = (x[k].shape[0] // 8) * 8, (x[k].shape[1] // 8) * 8
                bm = lambda a: a[:h, :w].astype(float).reshape(h // 8, 8, w // 8, 8).mean(axis=(1, 3))
                sm = bm(x[k]); near = (sm - lo < 32) | (hi - sm < 32)
                so += list((bm(o[k]) - sm)[near]); su += list((bm(u[k]) - sm)[near]); nb += int(near.sum())
            shifts.append('%s near-rail blocks %d: mean err ours %+.2f rail-free %+.2f, max |block err| ours %.1f' % (
                'YUV'[k], nb, np.mean(so) if so else 0, np.mean(su) if su else 0, np.max(np.abs(so)) if so else 0))
        fo = os.path.join(OUT, '%s_%.1f.yuv' % (name, R)); fsrc = os.path.join(OUT, '%s_src.yuv' % name)
        with open(fo, 'wb') as f:
            for o in decs:
                for p in o: p.astype('<u2').tofile(f)
        with open(fsrc, 'wb') as f:
            for x in X:
                for p in x: p.astype('<u2').tofile(f)
        sg = []
        for fr in range(len(X)):
            t = subprocess.run(['python3', TOOLS + 'smudgegroups.py', fsrc, fo, str(W), str(H), str(fr), fo + '_sg%d' % fr, '--thr', '6', '--dens', '0.4'], capture_output=True, text=True).stdout
            sg.append(' '.join('%s%s' % (m.group(1), m.group(2)) for m in re.finditer(r'^(Y|Cb|Cr): (\d+) groups', t, re.M)))
        print('%s @%.1f frames %d | oob %d AWAY %d TOUCHED %d | smudge groups per frame: %s' % (name, R, len(X), st['oob'], st['away'], st['touched'], ' ; '.join(sg)), flush=True)
        for s_ in shifts: print('   ' + s_, flush=True)
