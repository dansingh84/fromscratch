#!/usr/bin/env python3
# rcl_cbr.py CLIP ARM — form (i) end to end, 3 frames, EXACT PER-FRAME BUDGET like today's CBR (every frame gets
# R bits per luma sample x W x H). Per frame the plan = the finest quarter-octave step Q whose STATIC-TABLE code
# length (tables trained on the 3 disjoint training clips at that Q, same arm) fits the budget (model of the one-pass
# lane decision; one Q per frame, no per-slice plan yet). Vector bits 10 per 16x16 block on inter frames.
# Reports per owner rate R: per-frame bpp and Q, per-frame NEG, frame-2 NEG and PSNR Y/Cb/Cr; compare with today's
# frame 2 (out/today_eval.txt) which ran at exactly R per frame.
import sys, os, re, json, pickle, subprocess, numpy as np
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
KEEP = 'keep' in TOK   # keep the last-write step on source-still blocks
RS_ = 0.5 if 'rs' in TOK else 0.0   # rounding slack added to the hysteresis threshold (codes)
CU = any(re.fullmatch(r'cu[0-9.]*', t) for t in TOK); CUO = float([t[2:] for t in TOK if re.fullmatch(r'cu[0-9.]*', t)][0] or 1) if CU else 1.0  # octaves finer needed   # one catch-up per still episode (SA20P): still, not caught, step >= 1 octave finer than the last write
CAUGHT = [None]
CI = float([t[2:] for t in TOK if t.startswith('ci')][0]) if any(t.startswith('ci') for t in TOK) else None  # inter chroma multiplier
CHP = 'chp' in TOK   # 4:2:2 chroma MC: odd luma dx -> average of the two chroma neighbours (no rounding)
PP = 'pp' in TOK   # per-plane still gate + noise estimate (chroma judged on its own differences)
NFK = float([t[2:] for t in TOK if t.startswith('nf')][0]) if any(t.startswith('nf') for t in TOK) else 2.0  # noise floor in sigma-hat
BZ = 'bz' in TOK     # block-level decision: a still-gated block gets ALL leaves 0 (except in its catch-up)
RAMP = int([t[4:] for t in TOK if t.startswith('ramp')][0] or 1) if any(t.startswith('ramp') for t in TOK) else 0  # frames 1..RAMP refine freely (owner A1 rev.3)
CUAFTER = 'cua' in TOK   # catch-up decided AFTER the frame step (P's (c)): fires only if the frame's budget covers it at that step
CUOFF = [False]; T_ = [0]
RG = 'rg' in TOK   # (a)+(b): moving step Q_m + one catch-up step Q_c for the still, not-caught blocks (whole set, once)
CUB = [None]; QMB = [None]
DR = 'dr' in TOK   # drift release: still only while MAD(x - own recon) <= E_last + 1.5 noise (error-triggered, S5.390)
REFH = [None]; ELAST = [None]; NBH = [None]
MF = 'mf' in TOK   # region plan: moving step never finer than the still region's step (padding left for the catch-up)
ACC = 'acc' in TOK   # SA20Q: still = source unchanged since the block's LAST WRITE (accumulated) + M consecutive passes
XLAST = [None]; PASS = [None]; STILLF = [None]; MPASS = 3
G2 = 'g2' in TOK   # higher-confidence gate: 35th-pct noise, MAD <= 1.5 n, |mean| <= 5 n/16, release after 2 consecutive fails, catch-up step >= moving/2
FAILC = [None]
SH = 'sh' in TOK   # motion-aware hold: release if a 1-px shift of the last-write source explains x_t better than zero shift
RR = 'rr' in TOK   # per-connected-region catch-ups (SA20Q (b)): regions largest first, each whole, at the finest fitting step
def regions(mask):
    from collections import deque
    lab = np.zeros(mask.shape, int); out = []; n = 0
    for i in range(mask.shape[0]):
        for j in range(mask.shape[1]):
            if mask[i, j] and not lab[i, j]:
                n += 1; q = deque([(i, j)]); lab[i, j] = n; cells = []
                while q:
                    a, b = q.popleft(); cells.append((a, b))
                    for da, db in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        u, v = a + da, b + db
                        if 0 <= u < mask.shape[0] and 0 <= v < mask.shape[1] and mask[u, v] and not lab[u, v]: lab[u, v] = n; q.append((u, v))
                out.append(lab == n)
    return sorted(out, key=lambda m: -m.sum())
WIN = 'win' in TOK   # SA20P: re-hold only if sub-block means are stable over a W-frame window; release from the reconstruction side
WW = 4; SUBH = []; ELW = [None]
def submeans(y):   # 8x8 sub-block means of a luma plane, grouped per 16x16 block -> (NBY, NBX, 4)
    NBY, NBX = (H + 15) // 16, (W + 15) // 16; d = np.zeros((NBY * 16, NBX * 16)); d[:H, :W] = y
    m = d.reshape(NBY * 2, 8, NBX * 2, 8).mean(axis=(1, 3))
    return np.stack([m[0::2, 0::2], m[0::2, 1::2], m[1::2, 0::2], m[1::2, 1::2]], -1)
SL = 'sl' in TOK   # step slew limit: after the ramp, the frame step moves at most one quarter-octave per frame
QPREV = [None]
EH = 'eh' in TOK   # SA20Q split rule: hold ONLY where the block's source is byte-identical to its last write (hash in hardware)
XLC = [None]
S16 = 's16' in TOK   # step-invariant model: 16 classes x {intra, inter} = 32 tables pooled over all steps
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
def cls16(q, a):
    qa = np.abs(q.astype(float)); m = np.zeros_like(qa)
    m[:, 1:] += qa[:, :-1]; m[1:, :] += qa[:-1, :]; m[1:, 1:] += 0.5 * qa[:-1, :-1]; m[1:, :-1] += 0.5 * qa[:-1, 1:]
    return np.minimum((np.log2(1 + m + a[:q.shape[0], :q.shape[1]]) * 16 / 7).astype(int), 15)
def tally16(SY, AC, mode, tab):
    for (key, q), a in zip(SY, AC):
        k = cls16(q, a); v = np.clip(q.astype(np.int64), -64, 64) + 64
        for kk in np.unique(k): np.add.at(tab.setdefault((mode, kk), np.zeros(129)), v[k == kk], 1)
def cost16(SY, AC, mode, tab):
    b = 0.0
    for (key, q), a in zip(SY, AC):
        k = cls16(q, a); q = q.astype(np.int64)
        for kk in np.unique(k):
            x = q[k == kk]; h = tab.get((mode, kk), np.zeros(129)) + 1; p = h / h.sum()
            b += -np.log2(p[np.clip(x, -64, 64) + 64]).sum() + (12 + 2 * np.log2(np.abs(x[np.abs(x) > 63]))).sum()
    return b
def fcost(sy, Q):   # frame cost of [(key0, SY, AC)]
    if S16: return sum(cost16(SY, AC, key0[1], TABS) for key0, SY, AC in sy)
    return sum(cost(SY, key0, TABS[Q]) for key0, SY, AC in sy)
NG = 'ng' in TOK   # noise-aware still gate (SA20Q/SA20P): noise level per luma bucket from the lowest-motion blocks
SIG = [None]
def noise_gate(x, xprev, k=0):
    NBY, NBX = (H + 15) // 16, (W + 15) // 16; bw = 16 if k == 0 else 8; hh, ww = NBY * 16, NBX * bw; h_, w_ = x[k].shape
    d = np.zeros((hh, ww)); d[:h_, :w_] = x[k] - xprev[k]; lum = np.zeros((hh, ww)); lum[:h_, :w_] = x[k]
    D = d.reshape(NBY, 16, NBX, bw); mad = np.abs(D).mean(axis=(1, 3)); md = D.mean(axis=(1, 3))
    lb = np.minimum((lum.reshape(NBY, 16, NBX, bw).mean(axis=(1, 3)) / 128).astype(int), 7)
    n = np.zeros(8)
    for b in range(8):
        pc = 35 if G2 else 20; v = mad[lb == b]; n[b] = np.percentile(v, pc) if v.size >= 8 else np.percentile(mad, pc)
    nb = np.maximum(n[lb], 0.5)          # mean |d| of pure noise = sigma sqrt2 sqrt(2/pi) ~ 1.13 sigma
    still = (mad <= 1.5 * nb) & (np.abs(md) <= (5 if G2 else 3) * nb / np.sqrt(16 * bw))
    SIG[0] = nb / 1.13                   # per-block sigma estimate (of the plane asked for)
    return still
def bmad(a, b):
    NBY, NBX = (H + 15) // 16, (W + 15) // 16; d = np.zeros((NBY * 16, NBX * 16)); d[:H, :W] = np.abs(a - b)
    return d.reshape(NBY, 16, NBX, 16).mean(axis=(1, 3))
def still_blocks(x, xprev, k=0):   # encoder-only: block still = >= 95 % of its luma samples within 2 codes of the previous source
    if ACC and k == 0 and STILLF[0] is not None:
        noise_gate(x, xprev, 0); return STILLF[0]
    if NG:
        st_ = noise_gate(x, xprev, k)
        if DR and k == 0 and REFH[0] is not None and ELAST[0] is not None:
            st_ = st_ & (bmad(x[0], REFH[0][0]) <= ELAST[0] + 1.5 * SIG[0] * 1.13)
            noise_gate(x, xprev, k)   # keep SIG for this plane
        return st_
    NBY, NBX = (H + 15) // 16, (W + 15) // 16; d = np.abs(x[0] - xprev[0]) <= 2
    pad = np.ones((NBY * 16, NBX * 16), bool); pad[:H, :W] = d
    return pad.reshape(NBY, 16, NBX, 16).mean(axis=(1, 3)) >= 0.95
def cu_mask(st, Q, stl):
    if not CU or st is None or stl is None: return None
    if CAUGHT[0] is None: CAUGHT[0] = np.zeros(stl.shape, bool)
    return stl & ~CAUGHT[0] & ((Q < st[0][0] / 1.001) if CUO == 0 else (Q <= st[0][0] * 2 ** -CUO * 1.001))
def upd(st, y, ref, Q, stl=None, cu=None):   # encoder state per block: step and ladder of the last write
    # a block's last-write step moves to the current step only if its SOURCE changed (or it was written without a
    # still map); on source-still blocks it is kept (only an explicit catch-up may lower it) -- a partial write of a
    # few samples must not lower the threshold of the whole block (that spreads an uncontrolled catch-up)
    NBY, NBX = (H + 15) // 16, (W + 15) // 16
    if st is None: return [(np.full((NBY, NBX), Q * (cm if k else 1)), np.full((NBY, NBX), 0.7)) for k in range(3)]
    for k in range(3):
        bw = 16 if k == 0 else 8; ch = (y[k] != ref[k]); hh, ww = NBY * 16, NBX * bw
        pad = np.zeros((hh, ww), bool); pad[:ch.shape[0], :ch.shape[1]] = ch
        wr = pad.reshape(NBY, 16, NBX, bw).any(axis=(1, 3))
        if stl is not None and KEEP: wr &= ~stl
        if cu is not None: wr |= cu   # the catch-up rewrites the whole block at the current step
        st[k][0][wr] = Q * ((cm if CI is None else CI) if k else 1); st[k][1][wr] = FI
    return st
def apply_c(ref, V):   # chroma prediction at the exact half-sample position for odd luma dx
    Hh, Ww = ref.shape; R_ = 8; pad = np.pad(ref, R_ + 1, mode='edge'); P = np.zeros_like(ref)
    for i in range(V.shape[0]):
        for j in range(V.shape[1]):
            by, bx = i * 16, j * 8
            if by >= Hh or bx >= Ww: continue
            dy, dx = V[i, j]; h = min(16, Hh - by); w = min(8, Ww - bx); q, r = divmod(int(dx), 2)
            a = pad[by + R_ + 1 + dy:by + R_ + 1 + dy + h, bx + R_ + 1 + q:bx + R_ + 1 + q + w]
            P[by:by + h, bx:bx + w] = a if r == 0 else (a + pad[by + R_ + 1 + dy:by + R_ + 1 + dy + h, bx + R_ + 2 + q:bx + R_ + 2 + q + w] + 1) >> 1
    return P
def expand(b, shp, bw):   # per-block map (16 rows x bw cols) -> per-sample map
    return np.repeat(np.repeat(b, 16, 0), bw, 1)[:shp[0], :shp[1]]
def code_frame(x, ref, Q, st=None, xprev=None):
    """x = source planes, ref = previous reconstruction (None = intra). returns [(key0, SY)], recon"""
    if ref is None: Ps = [np.zeros_like(p) for p in x]; mode = 'intra'
    else:
        V = motion(x[0], ref[0], Z=ZB)
        if SG and xprev is not None: V[:still_blocks(x, xprev).shape[0], :still_blocks(x, xprev).shape[1]][still_blocks(x, xprev)] = 0   # source-still block -> zero vector (encoder)
        Ps = [apply(ref[0], V, 16, 1)] + ([apply_c(ref[1], V), apply_c(ref[2], V)] if CHP else [apply(ref[1], V, 16, 2), apply(ref[2], V, 16, 2)]); mode = 'inter'
    out = []; sy = []
    for pl, (p, P) in enumerate(zip(x, Ps)):
        SY = []; AC = []; Yd = None
        if pl and CL:
            Yf = out[0]; Yd = ((Yf[:, 0::2] + Yf[:, 1::2] + 1) >> 1) - ((Ps[0][:, 0::2] + Ps[0][:, 1::2] + 1) >> 1)
        HT = None
        if HY and st is not None and mode == 'inter' and not (RAMP and T_[0] <= RAMP):
            bw = 16 if pl == 0 else 8; KQ = HY * expand(st[pl][0], p.shape, bw)
            if SG and xprev is not None:
                stl_ = still_blocks(x, xprev, pl if PP else 0)
                if EH: KQ0 = KQ.copy()   # grain-follow blocks keep kappa*Delta_last; exact-still blocks handled below
                KQ = KQ * expand(stl_.astype(float), p.shape, bw)
                NF_ = (NFK * expand(SIG[0], p.shape, bw) if NG else 0.0) + RS_   # additive floor at EVERY level (raw samples carry full noise)
                if BZ: KQ = np.where(KQ > 0, 1e9, 0.0)   # still block: every leaf 0
                cm_ = CUB[0] if RG else (None if CUOFF[0] else cu_mask(st, Q, still_blocks(x, xprev) if PP else stl_))
                if PP and NG: still_blocks(x, xprev, pl)   # restore this plane's sigma for the floor
                if cm_ is not None: KQ = KQ * expand((~cm_).astype(float), p.shape, bw)
                if EH:   # non-still (grain-follow) blocks: per-sample hysteresis kappa*Delta_last, no noise floor
                    ns_ = expand((~stl_).astype(float), p.shape, bw) > 0; KQ = np.where(ns_, KQ0, KQ); NF_ = np.where(ns_, RS_, NF_) if isinstance(NF_, np.ndarray) else NF_
            HT = (KQ, expand(st[pl][1], p.shape, bw), NF_ if (SG and xprev is not None) else RS_)
        QMp = None if (QMB[0] is None or mode == 'intra') else expand(QMB[0], p.shape, 16 if pl == 0 else 8)
        y = po(p, Q * ((cm if (mode == 'intra' or CI is None) else CI) if pl else 1), 0.7 if mode == 'intra' else FI, 0, SY, Yd=Yd, P=P, HT=HT, ACT=AC, QM=QMp)[1]
        out.append(y); sy.append(((min(pl, 1), mode), SY, AC))
    return sy, out
if os.environ.get('LOO') == '1': TRAIN = [c for c in TRAIN if c[0] != TEST]   # leave-one-out when fitting on a training clip
tpath = os.path.join(OUT, 'tables_%s%s.pkl' % (ARM, '_loo_' + TEST if os.environ.get('LOO') == '1' else ''))
if os.path.exists(tpath): TABS = pickle.load(open(tpath, 'rb'))
elif S16:   # pooled over every other quarter-octave step of the owner range, sequences coded with the arm's state
    TABS = {}
    for Q in [2 ** (e / 4) for e in range(-2, 25, 2)]:
        for clip, nf in TRAIN:
            ref = None; st = None; fr = [read(A + clip + '_1280x720_422_10.yuv', W, H, f) for f in range(nf)]
            for f in range(nf):
                sy, y = code_frame(fr[f], ref, Q, st, fr[f - 1] if f else None)
                for key0, SY, AC in sy: tally16(SY, AC, key0[1], TABS)
                st = upd(st, y, ref, Q, still_blocks(fr[f], fr[f - 1]) if f else None); ref = y
    pickle.dump(TABS, open(tpath, 'wb'))
else:
    TABS = {}
    for Q in GRID:
        tab = {}
        for clip, nf in TRAIN:
            ref = None
            for f in range(nf):
                sy, ref = code_frame(read(A + clip + '_1280x720_422_10.yuv', W, H, f), ref, Q)
                for key0, SY, AC in sy: tally(SY, key0, tab)
        TABS[Q] = tab
    pickle.dump(TABS, open(tpath, 'wb'))
if TEST == 'train': sys.exit(0)
def split(sy, Q):
    # bits per level class: kept = coarsest DPCM grid ('c'), leaves per finer level; summed over planes
    d = {}
    for key0, SY, AC in sy:
        for (key, q), a in zip(SY, AC): d[key[1]] = d.get(key[1], 0.0) + (cost16([(key, q)], [a], key0[1], TABS) if S16 else cost([(key, q)], key0, TABS[Q]))
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
    budget = R * W * H; ref = None; rec = []; info = []; spl = []; st = None; CAUGHT[0] = None; cuinfo = []; QPREV[0] = None; ELAST[0] = None; PASS[0] = None; STILLF[0] = None; FAILC[0] = None; ELW[0] = None; SUBH.clear()
    NBY, NBX = (H + 15) // 16, (W + 15) // 16
    for t, x in enumerate(X):
        T_[0] = t; CUOFF[0] = CUAFTER; REFH[0] = ref
        if ACC:
            STILLF[0] = None
            if t == 0:
                XLAST[0] = x[0].copy(); PASS[0] = None; XLC[0] = [x[1].copy(), x[2].copy()]
                if WIN: SUBH.append(submeans(x[0]))
            else:
                ng_ = noise_gate(x, X[t - 1], 0); nb_ = SIG[0] * 1.13
                if EH:   # exact equality on all three planes since the block's last write
                    eq = bmad(x[0], XLAST[0]) == 0
                    for k in (1, 2):
                        dc = np.zeros(((H + 15) // 16 * 16, (W + 15) // 16 * 8)); dc[:H, :W // 2] = np.abs(x[k] - XLC[0][k - 1])
                        eq &= dc.reshape((H + 15) // 16, 16, (W + 15) // 16, 8).max(axis=(1, 3)) == 0
                    STILLF[0] = eq; PASS[0] = None
                    raise_skip = True
                else: raise_skip = False
                m0 = bmad(x[0], XLAST[0]); raw = ng_ & (m0 <= (1.5 if G2 else 1.3) * nb_)
                if raise_skip: raw = STILLF[0]
                if SH:
                    msh = np.min([bmad(x[0], np.roll(XLAST[0], sft, ax)) for sft in (1, -1) for ax in (0, 1)], axis=0)
                    raw &= ~(msh < m0 - 0.15 * nb_)
                prevP = PASS[0] if PASS[0] is not None else np.full(raw.shape, MPASS)
                if WIN:
                    SUBH.append(submeans(x[0]))
                    if len(SUBH) >= 2:   # window of up to WW frames (the earliest available before WW frames exist)
                        dm = np.abs(SUBH[-1] - SUBH[max(0, len(SUBH) - 1 - WW)]).max(-1); raw &= dm <= 0.7 * SIG[0] * np.sqrt(2) * 1.5
                    held = (PASS[0] if PASS[0] is not None else np.zeros(raw.shape, int)) >= MPASS
                    if ELW[0] is not None:   # reconstruction-side release of held blocks
                        rel = held & (bmad(x[0], ref[0]) > ELW[0] + 1.5 * nb_); raw &= ~rel
                if G2:   # release only after 2 consecutive fails; a held block survives one noisy frame
                    FAILC[0] = np.where(raw, 0, (FAILC[0] if FAILC[0] is not None else np.zeros(raw.shape, int)) + 1)
                    keep_ = (prevP >= MPASS) & (FAILC[0] < 2)
                    PASS[0] = np.where(raw, prevP + 1, np.where(keep_, prevP, 0))
                else: PASS[0] = np.where(raw, prevP + 1, 0)
                STILLF[0] = raw if EH else PASS[0] >= MPASS
        # binary search over the sorted grid for the finest Q that fits (costs are monotone in Q up to table noise)
        CUB[0] = None; QMB[0] = None; rginfo = None
        lo, hi = 0, len(GRID) - 1; best = None
        if SL and QPREV[0] is not None and t > max(RAMP, 1):
            ip = GRID.index(QPREV[0]); lo = max(0, ip - 1)   # ASYMMETRIC: refine <= 1 quarter-octave, coarsen freely (CBR at bursts)
        if RG and MF and t and st is not None and not (RAMP and t <= RAMP):
            REFH[0] = ref; stl_m = still_blocks(x, X[t - 1])
            if stl_m.any():
                qfloor = np.median(st[0][0][stl_m]); lo = min(i for i, g in enumerate(GRID) if g >= qfloor * 0.999)
        while lo <= hi:
            mid = (lo + hi) // 2; Q = GRID[mid]
            sy, y = code_frame(x, ref, Q, st, X[t - 1] if t else None)
            b = fcost(sy, Q) + (10 * NBLK if t else 0)
            if b <= budget: best = (Q, b, y, sy); hi = mid - 1
            else: lo = mid + 1
        if RG and best is not None and t and st is not None and not (RAMP and t <= RAMP):
            stl0 = still_blocks(x, X[t - 1]); CAUGHT[0] = np.zeros(stl0.shape, bool) if CAUGHT[0] is None else CAUGHT[0]
            cand = stl0 & ~CAUGHT[0]; Qm = best[0]
            if cand.any() and RR:
                acc_m = np.zeros(cand.shape, bool); qmap = np.ones(cand.shape); got = []
                for reg in regions(cand)[:6]:
                    QLr = st[0][0][reg].max()
                    for Qc in [g for g in GRID[::2] if g <= QLr * 2 ** -0.25 * 1.001 and (not G2 or g >= Qm / 2 * 0.999)]:
                        CUB[0] = acc_m | reg; QMB[0] = np.where(reg, Qc / Qm, qmap)
                        syc, yc = code_frame(x, ref, Qm, st, X[t - 1]); bc = fcost(syc, Qm) + 10 * NBLK + NBLK
                        if bc <= budget:
                            best = (Qm, bc, yc, syc); acc_m = acc_m | reg; qmap = np.where(reg, Qc / Qm, qmap); got.append((int(reg.sum()), Qc)); break
                CUB[0] = acc_m if acc_m.any() else None; QMB[0] = qmap if acc_m.any() else None
                if got: rginfo = (None, got)
            elif cand.any():
                QLr = st[0][0][cand].max()   # the set's coarsest last step: Q_c must be >= 0.25 octave finer than it
                for Qc in [g for g in GRID if g <= QLr * 2 ** -0.25 * 1.001 and (not G2 or g >= Qm / 2 * 0.999)]:
                    CUB[0] = cand; QMB[0] = np.where(cand, Qc / Qm, 1.0)
                    syc, yc = code_frame(x, ref, Qm, st, X[t - 1]); bc = fcost(syc, Qm) + 10 * NBLK + NBLK
                    if bc <= budget: best = (Qm, bc, yc, syc); rginfo = (Qc, int(cand.sum())); break
                else: CUB[0] = None; QMB[0] = None
            if rginfo is None and MF and lo > 0:   # no catch-up used the padding: let the moving step go finer (no waste)
                lo2, hi2 = 0, lo - 1
                while lo2 <= hi2:
                    mid = (lo2 + hi2) // 2; Q2 = GRID[mid]; sy2, y2 = code_frame(x, ref, Q2, st, X[t - 1]); b2 = fcost(sy2, Q2) + 10 * NBLK
                    if b2 <= budget: best = (Q2, b2, y2, sy2); hi2 = mid - 1
                    else: lo2 = mid + 1
        if CUAFTER and best is not None and t:
            CUOFF[0] = False; Q_ = best[0]; sy2, y2 = code_frame(x, ref, Q_, st, X[t - 1]); b2 = fcost(sy2, Q_) + 10 * NBLK
            if b2 <= budget: best = (Q_, b2, y2, sy2)
            else: CUOFF[0] = True
        if best is None: Q = GRID[-1]; sy, y = code_frame(x, ref, Q, st, X[t - 1] if t else None); best = (Q, fcost(sy, Q) + (10 * NBLK if t else 0), y, sy)
        Q, b, y, sy = best
        stl = still_blocks(x, X[t - 1]) if t else None
        if RG: cu = CUB[0] if (CUB[0] is not None) else (np.zeros(stl.shape, bool) if stl is not None else None)
        else: cu = None if CUOFF[0] or (RAMP and t <= RAMP) else cu_mask(st, Q, stl)
        st = upd(st, y, ref, Q, stl, cu)
        if WIN:   # error at last write per block (reconstruction side)
            e_now = bmad(x[0], y[0])
            if ELW[0] is None or t == 0: ELW[0] = e_now
            else: ELW[0] = np.where(bmad(y[0], ref[0]) > 0, e_now, ELW[0])
        if ACC and t:
            wrb = bmad(y[0], ref[0]) > 0; wr_s = np.repeat(np.repeat(wrb, 16, 0), 16, 1)[:H, :W]
            XLAST[0] = np.where(wr_s, x[0], XLAST[0])
            wr_c = np.repeat(np.repeat(wrb, 16, 0), 8, 1)[:H, :W // 2]; XLC[0] = [np.where(wr_c, x[1], XLC[0][0]), np.where(wr_c, x[2], XLC[0][1])]
        if DR:   # error at last write, per block (luma): set where the block was written (changed) or at intra
            e_now = bmad(x[0], y[0])
            if ELAST[0] is None or t == 0: ELAST[0] = e_now
            else:
                wr = bmad(y[0], ref[0]) > 0; ELAST[0] = np.where(wr, e_now, ELAST[0])
        if RG and rginfo is not None:
            if rginfo[0] is None:
                for k in range(3): st[k][0][cu] = (QMB[0][cu] * Q) * ((cm if CI is None else CI) if k else 1)
            else:
                for k in range(3): st[k][0][cu] = rginfo[0] * ((cm if CI is None else CI) if k else 1)
        if RG: cuinfo.append('-' if rginfo is None else ('+'.join('%d@%.1f' % g for g in rginfo[1]) if rginfo[0] is None else '%d@%.1f' % (rginfo[1], rginfo[0])))
        if (CU or RG) and stl is not None and cu is not None:
            CAUGHT[0] = ((CAUGHT[0] if CAUGHT[0] is not None else np.zeros(stl.shape, bool)) | cu) & stl   # caught until the source moves
            if not RG: cuinfo.append(int(cu.sum()))
        QPREV[0] = Q; ref = y; rec.append(y); info.append((Q, b / (W * H))); spl.append(split(sy, Q))
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
    print('   changed share ALL samples Y/Cb/Cr per transition ' + ' '.join('/'.join('%.2f%%' % (100 * (rec[t][k] != rec[t-1][k]).mean()) for k in range(3)) for t in range(1, NF))
          + ((' | still-labelled blocks ' + '/'.join('%.0f%%' % (100 * still_blocks(X[t], X[t - 1]).mean()) for t in range(1, NF))) if SG else ''), flush=True)
    # temporal activity vs the SOURCE (A2 'sub-source calm'): boil = mean |frame-to-frame delta|, ants = share |delta| > 6
    bo = []
    for k in range(3):
        do = np.mean([np.abs(rec[t][k] - rec[t - 1][k]).mean() for t in range(1, NF)]); ds = np.mean([np.abs(X[t][k] - X[t - 1][k]).mean() for t in range(1, NF)])
        ao = np.mean([(np.abs(rec[t][k] - rec[t - 1][k]) > 6).mean() for t in range(1, NF)]); as_ = np.mean([(np.abs(X[t][k] - X[t - 1][k]) > 6).mean() for t in range(1, NF)])
        bo.append('%s boil %.3f (src %.3f) ants %.2f%% (src %.2f%%)' % ('YUV'[k], do, ds, 100 * ao, 100 * as_))
    print('   temporal activity ' + ' | '.join(bo), flush=True)
    print('   Y ants per transition ' + ' '.join('%.2f%%(src %.2f%%)' % (100 * (np.abs(rec[t][0] - rec[t - 1][0]) > 6).mean(), 100 * (np.abs(X[t][0] - X[t - 1][0]) > 6).mean()) for t in range(1, NF)), flush=True)
    if NF >= 6:   # per-block luma change histogram over all transitions (SA20Q bound): 0 / 1 / intermittent / continuous
        NBY_, NBX_ = (H + 15) // 16, (W + 15) // 16; cnt = np.zeros((NBY_, NBX_), int)
        for t in range(1, NF): cnt += bmad(rec[t][0], rec[t - 1][0]) > 0
        n = NF - 1; tot = cnt.size
        print('   per-block change count over %d transitions: 0: %.1f%% | 1: %.1f%% | 2..%d (intermittent): %.1f%% | >=%d: %.1f%%' % (
            n, 100 * (cnt == 0).mean(), 100 * (cnt == 1).mean(), n - 2, 100 * ((cnt >= 2) & (cnt <= n - 2)).mean(), n - 1, 100 * (cnt >= n - 1).mean()), flush=True)
    if CU or RG: print('   catch-up blocks per inter frame ' + '/'.join(map(str, cuinfo)), flush=True)
    print('   churn still Y/Cb/Cr per transition ' + ' '.join(ch) + ' | Y PSNR per frame ' + '/'.join('%.2f' % psnr(rec[t][0], X[t][0]) for t in range(NF)), flush=True)
    print('   bits/level (bpp, level 5 = kept DPCM) ' + ' ; '.join(
        'f%d ' % t + ' '.join('%d:%.3f' % (l, v / (W * H)) for l, v in sorted(d.items(), reverse=True)) for t, d in enumerate(spl)), flush=True)
    os.unlink(fn)
