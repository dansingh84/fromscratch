#!/usr/bin/env python3
# rcl_cbr.py CLIP ARM — form (i) end to end, 3 frames, EXACT PER-FRAME BUDGET like today's CBR (every frame gets
# R bits per luma sample x W x H). Per frame the plan = the finest quarter-octave step Q whose STATIC-TABLE code
# length (tables trained on the 3 disjoint training clips at that Q, same arm) fits the budget (model of the one-pass
# lane decision; one Q per frame, no per-slice plan yet). Vector bits 10 per 16x16 block on inter frames.
# Reports per owner rate R: per-frame bpp and Q, per-frame NEG, frame-2 NEG and PSNR Y/Cb/Cr; compare with today's
# frame 2 (out/today_eval.txt) which ran at exactly R per frame.
import sys, os, json, pickle, subprocess, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from d1_screen import read
from n4_core import po
from dp_screen_core import motion, apply
LO, HI = 0, 1023; W, H = 1280, 720
A = '/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/'
MODEL = '/home/user/fromscratch/OMC_CLOUD/vmaf_model/vmaf_v0.6.1neg.json'
TRAIN = [('cine_4k_A006', 2), ('cine_A005C021', 2), ('gfx444_F003C012', 3)]
RATES = [float(r) for r in os.environ.get('RATES', '0.5,1.0,1.5,2.0,2.5,3.0,4.0').split(',')]
TEST, ARM = sys.argv[1], sys.argv[2]
TOK = ARM.split('_'); cm = float(TOK[0][2:]); CL = 'cl' in TOK
ZB = float([t[2:] for t in TOK if t.startswith('zb')][0]) if any(t.startswith('zb') for t in TOK) else 0.0  # zero-vector bias
SG = 'sg' in TOK   # hysteresis only on SOURCE-still blocks (encoder-only gate, SA20Q)
NF = int(os.environ.get('NF', '3'))
HY = float([t[2:] for t in TOK if t.startswith('hy')][0]) if any(t.startswith('hy') for t in TOK) else 0  # hysteresis kappa
FI = float([t[2:] for t in TOK if t.startswith('fi')][0]) if any(t.startswith('fi') for t in TOK) else 0.7  # inter ladder
OUT = os.path.join(os.path.dirname(__file__), '..', 'out', 'rcl_cbr'); os.makedirs(OUT, exist_ok=True)
GRID = [2 ** (e / 4) for e in range(-8, 28)]
NBLK = ((H + 15) // 16) * ((W + 15) // 16)
def ctx(q):
    nz = q != 0; c = np.zeros_like(nz); c[:, 1:] |= nz[:, :-1]; c[1:, :] |= nz[:-1, :]; return c
def tally(SY, key0, tab):
    for key, q in SY:
        c = ctx(q); q = q.astype(np.int64)
        for cc in (0, 1):
            v = np.clip(q[c == cc], -64, 64); h = tab.setdefault(key0 + key + (cc,), np.zeros(129)); np.add.at(h, v + 64, 1)
def cost(SY, key0, tab):
    bits = 0.0
    for key, q in SY:
        c = ctx(q); q = q.astype(np.int64)
        for cc in (0, 1):
            v = q[c == cc]; h = tab.get(key0 + key + (cc,), np.zeros(129)) + 1; p = h / h.sum()
            bits += -np.log2(p[np.clip(v, -64, 64) + 64]).sum(); esc = np.abs(v) > 63; bits += (12 + 2 * np.log2(np.abs(v[esc]))).sum()
    return bits
def expand(b, shp, bw):   # per-block map (16 rows x bw cols) -> per-sample map
    return np.repeat(np.repeat(b, 16, 0), bw, 1)[:shp[0], :shp[1]]
def code_frame(x, ref, Q, st=None, xprev=None):
    """x = source planes, ref = previous reconstruction (None = intra). returns [(key0, SY)], recon"""
    if ref is None: Ps = [np.zeros_like(p) for p in x]; mode = 'intra'
    else:
        V = motion(x[0], ref[0], Z=ZB); Ps = [apply(ref[0], V, 16, 1), apply(ref[1], V, 16, 2), apply(ref[2], V, 16, 2)]; mode = 'inter'
    out = []; sy = []
    for pl, (p, P) in enumerate(zip(x, Ps)):
        SY = []; Yd = None
        if pl and CL:
            Yf = out[0]; Yd = ((Yf[:, 0::2] + Yf[:, 1::2] + 1) >> 1) - ((Ps[0][:, 0::2] + Ps[0][:, 1::2] + 1) >> 1)
        HT = None
        if HY and st is not None and mode == 'inter':
            bw = 16 if pl == 0 else 8; KQ = HY * expand(st[pl][0], p.shape, bw)
            if SG and xprev is not None:   # gate: block still = >= 95 % of its luma samples within 2 codes of the previous source
                d = np.abs(x[0] - xprev[0]) <= 2; hh, ww = st[0][0].shape[0] * 16, st[0][0].shape[1] * 16
                pad = np.ones((hh, ww), bool); pad[:H, :W] = d
                stl = pad.reshape(hh // 16, 16, ww // 16, 16).mean(axis=(1, 3)) >= 0.95
                KQ = KQ * expand(stl.astype(float), p.shape, bw)
            HT = (KQ, expand(st[pl][1], p.shape, bw))
        y = po(p, Q * (cm if pl else 1), 0.7 if mode == 'intra' else FI, 0, SY, Yd=Yd, P=P, HT=HT)[1]
        out.append(y); sy.append(((min(pl, 1), mode), SY))
    return sy, out
tpath = os.path.join(OUT, 'tables_%s.pkl' % ARM)
if os.path.exists(tpath): TABS = pickle.load(open(tpath, 'rb'))
else:
    TABS = {}
    for Q in GRID:
        tab = {}
        for clip, nf in TRAIN:
            ref = None
            for f in range(nf):
                sy, ref = code_frame(read(A + clip + '_1280x720_422_10.yuv', W, H, f), ref, Q)
                for key0, SY in sy: tally(SY, key0, tab)
        TABS[Q] = tab
    pickle.dump(TABS, open(tpath, 'wb'))
if TEST == 'train': sys.exit(0)
def split(sy, Q):
    # bits per level class: kept = coarsest DPCM grid ('c'), leaves per finer level; summed over planes
    d = {}
    for key0, SY in sy:
        for key, q in SY: d[key[1]] = d.get(key[1], 0.0) + cost([(key, q)], key0, TABS[Q])
    return d
def neg3(src, dec):
    cmd = ['ffmpeg', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'yuv422p10le', '-s', '%dx%d' % (W, H), '-i', dec,
           '-f', 'rawvideo', '-pix_fmt', 'yuv422p10le', '-s', '%dx%d' % (W, H), '-i', src, '-frames:v', str(NF),
           '-lavfi', '[0:v]trim=end_frame=%d[d];[1:v]trim=end_frame=%d[r];[d][r]libvmaf=model=path=%s:n_threads=4:log_fmt=json:log_path=/dev/stdout' % (NF, NF, MODEL),
           '-f', 'null', '-']
    return [f['metrics']['vmaf'] for f in json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)['frames']]
def psnr(a, b): return 10 * np.log10(1023.0 ** 2 / max(((a - b).astype(float) ** 2).mean(), 1e-9))
src = A + TEST + '_1280x720_422_10.yuv'; X = [read(src, W, H, f) for f in range(NF)]
for R in RATES:
    budget = R * W * H; ref = None; rec = []; info = []; spl = []; st = None
    NBY, NBX = (H + 15) // 16, (W + 15) // 16
    for t, x in enumerate(X):
        # binary search over the sorted grid for the finest Q that fits (costs are monotone in Q up to table noise)
        lo, hi = 0, len(GRID) - 1; best = None
        while lo <= hi:
            mid = (lo + hi) // 2; Q = GRID[mid]
            sy, y = code_frame(x, ref, Q, st, X[t - 1] if t else None)
            b = sum(cost(SY, key0, TABS[Q]) for key0, SY in sy) + (10 * NBLK if t else 0)
            if b <= budget: best = (Q, b, y, sy); hi = mid - 1
            else: lo = mid + 1
        if best is None: Q = GRID[-1]; sy, y = code_frame(x, ref, Q, st, X[t - 1] if t else None); best = (Q, sum(cost(SY, k, TABS[Q]) for k, SY in sy), y, sy)
        Q, b, y, sy = best
        # encoder state per block: step and ladder of the last write (block changed = written)
        if st is None: st = [(np.full((NBY, NBX), Q * (cm if k else 1)), np.full((NBY, NBX), 0.7)) for k in range(3)]
        else:
            for k in range(3):
                bw = 16 if k == 0 else 8; ch = (y[k] != ref[k]); hh, ww = NBY * 16, NBX * bw
                pad = np.zeros((hh, ww), bool); pad[:ch.shape[0], :ch.shape[1]] = ch
                wr = pad.reshape(NBY, 16, NBX, bw).any(axis=(1, 3))
                st[k][0][wr] = Q * (cm if k else 1); st[k][1][wr] = FI
        ref = y; rec.append(y); info.append((Q, b / (W * H))); spl.append(split(sy, Q))
    fn = os.path.join(OUT, '%s_%s_%.1f.yuv' % (TEST, ARM, R))
    with open(fn, 'wb') as fo:
        for fr in rec:
            for p in fr: p.astype('<u2').tofile(fo)
    ng = neg3(src, fn); oob = sum(int(((p < LO) | (p > HI)).sum()) for fr in rec for p in fr)
    L_ = NF - 1
    print('%s %s @%.1f Q per frame %s bpp %s | NEG %s | last NEG %.3f PSNR %.2f/%.2f/%.2f oob %d' % (
        TEST, ARM, R, '/'.join('%.2f' % q for q, _ in info), '/'.join('%.3f' % b for _, b in info),
        '/'.join('%.2f' % v for v in ng), ng[L_], *[psnr(o, p) for o, p in zip(rec[L_], X[L_])], oob), flush=True)
    # churn: share of source-still samples (|x_t - x_t-1| <= 2 in that plane) whose reconstruction changed, per plane
    ch = []
    for t in range(1, NF):
        ch.append('/'.join('%.2f%%' % (100 * (rec[t][k] != rec[t-1][k])[np.abs(X[t][k] - X[t-1][k]) <= 2].mean()) for k in range(3)))
    print('   churn still Y/Cb/Cr per transition ' + ' '.join(ch) + ' | Y PSNR per frame ' + '/'.join('%.2f' % psnr(rec[t][0], X[t][0]) for t in range(NF)), flush=True)
    print('   bits/level (bpp, level 5 = kept DPCM) ' + ' ; '.join(
        'f%d ' % t + ' '.join('%d:%.3f' % (l, v / (W * H)) for l, v in sorted(d.items(), reverse=True)) for t, d in enumerate(spl)), flush=True)
    os.unlink(fn)
