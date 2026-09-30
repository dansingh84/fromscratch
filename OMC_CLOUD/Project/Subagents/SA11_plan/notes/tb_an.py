#!/usr/bin/env python3
"""[SA11 T-B] usage: tb_an.py src dec W H nf err [dist]  (4:2:2 10-bit planar LE)"""
import sys, numpy as np, re, collections
from scipy.ndimage import distance_transform_cdt
src, dec, W, H, nf, err = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5]), sys.argv[6]
dist = len(sys.argv) > 7
cw = W // 2; fs = W * H + 2 * cw * H
def planes(path, f):
    a = np.fromfile(path, dtype='<u2', count=fs, offset=f * fs * 2).astype(np.int32)
    return [a[:W * H].reshape(H, W), a[W * H:W * H + cw * H].reshape(H, cw), a[W * H + cw * H:].reshape(H, cw)]
S = [planes(src, f) for f in range(nf)]; D = [planes(dec, f) for f in range(nf)]
print('per frame pair f-1->f: changed decoded samples per plane Y/Cb/Cr  [amplitude 1 | 2-3 | >=4]  (of N)')
if dist: print('  (source-static samples only, split by Chebyshev distance to nearest changing source sample: <=8 | 9-32 | >32)')
usl = collections.defaultdict(dict)
for ln in open(err):
    if ln.startswith('USL '):
        d = dict(t.split('=', 1) for t in ln.split()[1:]); usl[int(d['f'])][int(d['s'])] = int(d['inter'])
ns = max(len(v) for v in usl.values()) if usl else 1
sh = -(-H // ns)
tot = collections.Counter()
for f in range(1, nf):
    if not dist:
        rows = np.zeros(H, bool)
        for s_, it in usl[f].items():
            if not it: rows[s_ * sh:(s_ + 1) * sh] = True
        segY = []
        for p in range(3):
            d = np.abs(D[f][p] - D[f - 1][p]) > 0
            a, b = int(d[rows].sum()), int(d[~rows].sum())
            segY.append('%s refresh-rows %d/%d inter-rows %d/%d' % ('YBR'[p], a, int(rows.sum()) * d.shape[1], b, int((~rows).sum()) * d.shape[1]))
        print('  split f%d: ' % f + ' | '.join(segY))
    parts = []
    for p in range(3):
        d = np.abs(D[f][p] - D[f - 1][p])
        if not dist:
            n = d.size; c = int((d > 0).sum())
            parts.append('%s %d/%d (%.2f%%) [%d|%d|%d] max %d' % ('YBR'[p], c, n, 100.0 * c / n, int((d == 1).sum()), int(((d >= 2) & (d <= 3)).sum()), int((d >= 4).sum()), int(d.max())))
        else:
            sc = S[f][p] != S[f - 1][p]
            st = ~sc
            dd = distance_transform_cdt(~sc, metric='chessboard') if sc.any() else np.full(sc.shape, 10**6)
            segs = []
            for nm, m in (('<=8', st & (dd <= 8)), ('9-32', st & (dd > 8) & (dd <= 32)), ('>32', st & (dd > 32))):
                n = int(m.sum()); c = int(((d > 0) & m).sum()); big = int(((d >= 4) & m).sum())
                tot[(p, nm, 'n')] += n; tot[(p, nm, 'c')] += c; tot[(p, nm, 'b')] += big
                segs.append('%s %d/%d(%.1f%%,>=4:%d)' % (nm, c, n, 100.0 * c / max(n, 1), big))
            parts.append('%s static=%d srcchg=%d: %s' % ('YBR'[p], int(st.sum()), int(sc.sum()), ' '.join(segs)))
    print(' f%d: ' % f + ' || '.join(parts))
if dist:
    for p in range(3):
        print(' TOTAL %s: ' % 'YBR'[p] + ' '.join('%s %d/%d (%.1f%%; >=4 %.1f%%)' % (nm, tot[(p, nm, 'c')], tot[(p, nm, 'n')], 100.0 * tot[(p, nm, 'c')] / max(tot[(p, nm, 'n')], 1), 100.0 * tot[(p, nm, 'b')] / max(tot[(p, nm, 'n')], 1)) for nm in ('<=8', '9-32', '>32')))
# convergence: first frame after which no change
if not dist:
    last = 0
    for f in range(1, nf):
        if any((D[f][p] != D[f - 1][p]).any() for p in range(3)): last = f
    print('converged: %s' % ('no change after frame %d' % last if last < nf - 1 else 'NOT converged (frame %d still changes)' % (nf - 1)))
    # error vs source per frame
    print('PSNR vs source Y/Cb/Cr per frame: ' + ' '.join('f%d %.2f/%.2f/%.2f' % ((f,) + tuple(10 * np.log10(1023.0 ** 2 / max(np.mean((S[f][p] - D[f][p]) ** 2), 1e-9)) for p in range(3))) for f in range(nf)))
# bits per frame from USL lines
fr = collections.defaultdict(lambda: collections.Counter())
for ln in open(err):
    if not ln.startswith('USL '): continue
    d = dict(t.split('=', 1) for t in ln.split()[1:])
    f = int(d['f']); inter = int(d['inter']); k = 'intra' if (not inter) else 'inter'
    fr[f][k + '_n'] += 1; fr[f][k + '_used'] += int(d['used']); fr[f][k + '_budget'] += int(d['budget'])
    fr[f]['held'] += int(d['held']); fr[f]['pinned'] += int(d['pinned'])
    e = list(map(int, d['est'].split(',')))
    for i, g in enumerate(('LL', 'b1-3', 'b4-6', 'b7-9')): fr[f][k + '_' + g] += e[i]
    fr[f]['bands_inter'] += int(d['popm'])
print('bits per frame (payload used / budget) by slice type; estimated split LL/b1-3/b4-6/b7-9; held = static-slice holds; bands_inter = inter-coded bands summed over slices')
for f in sorted(fr):
    c = fr[f]
    s = ' f%d: total used %d' % (f, c['intra_used'] + c['inter_used'])
    for k in ('intra', 'inter'):
        if c[k + '_n']:
            s += ' | %s %d slices used %d / budget %d est %d/%d/%d/%d' % (k, c[k + '_n'], c[k + '_used'], c[k + '_budget'], c[k + '_LL'], c[k + '_b1-3'], c[k + '_b4-6'], c[k + '_b7-9'])
    s += ' | held %d pinned %d bands_inter %d' % (c['held'], c['pinned'], c['bands_inter'])
    print(s)
