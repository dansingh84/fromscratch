# HH-band vertical predictor variants (LH bands stay two-sided): two-sided vs causal-across vs in-block; training clips; all planes
import numpy as np, sys
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import pyr2, pyr, yuv
from pyr import split_h, split_v
W = {'LL': 1, 'H5': 2, 'H4': 2, 'H3': 2, 'LH2': 2, 'HL2': 2, 'HH2': 4, 'LH1': 2, 'HL1': 2, 'HH1': 4}
def ent(q):
    q = np.clip(np.asarray(q).astype(np.int64), -40, 40).ravel() + 40; c = np.bincount(q, minlength=81).astype(float); p = c[c > 0] / c.sum()
    return -(c[c > 0] * np.log2(p)).sum()
def causal_v(m):
    p = np.zeros_like(m); p[1:] = (m[:-1] - m[1:] + 1) >> 1; return p
def inblock_pairs(m):
    p = (m[0::2] - m[1::2] + 1) >> 1; return np.repeat(p, 2, axis=0)
VAR = {'two': (pyr2.pred_v, pyr2.pred_v), 'causal': (causal_v, causal_v), 'inblock1_causal2': (inblock_pairs, causal_v)}
def analysis(x, Lh, ph1, ph2):
    T = {}
    L1, d = split_h(x); E1 = d - pyr2.pred_h(L1)
    LL1, dv = split_v(L1); T['LH1'] = dv - pyr2.pred_v(LL1)
    HL1, dv = split_v(E1); T['HL1'] = HL1; T['HH1'] = dv - ph1(HL1)
    L2, d = split_h(LL1); E2 = d - pyr2.pred_h(L2)
    LL2, dv = split_v(L2); T['LH2'] = dv - pyr2.pred_v(LL2)
    HL2, dv = split_v(E2); T['HL2'] = HL2; T['HH2'] = dv - ph2(HL2)
    ll = LL2
    for k in range(3, Lh + 1): ll, d = split_h(ll); T['H%d' % k] = d - pyr2.pred_h(ll)
    T['LL'] = ll; return T
res = {}
for clip in yuv.TRAIN[:2]:
    fr = yuv.read_frame(clip, 1920, 1080, 2)
    for pn, Y, Lh in (('Y', fr[0], 5), ('Cb', fr[1], 4), ('Cr', fr[2], 4)):
        for name, (ph1, ph2) in VAR.items():
            pts = []
            for s in (4, 6, 8, 12, 16, 24, 32):
                T = analysis(Y, Lh, ph1, ph2); bits = 0
                for b in pyr2.BANDS(Lh): bits += ent(np.round(T[b] / (W[b] * s)))
                # distortion: reconstruct with the matching synthesis (monkeypatch pred_v used for HH only)
                # (quantisation error is what matters; use open-loop values)
                C = {b: np.round(T[b] / (W[b] * s)).astype(np.int64) * (W[b] * s) for b in pyr2.BANDS(Lh)}
                # synthesis with HH predictors = variant: temporarily patch
                orig = pyr2.pred_v
                def pv_patched(m, _ph1=ph1, _ph2=ph2, _orig=orig):
                    return _orig(m)
                # pyr2.synthesis calls pred_v for LH2, HL2->HH2, LH1, HL1->HH1 in a fixed order; patch by call count
                calls = {'n': 0}
                def pv(m):
                    calls['n'] += 1
                    # order in synthesis: LH2 (1), HH2 via HL2 (2), LH1 (3), HH1 via HL1 (4)
                    return {1: orig, 2: ph2, 3: orig, 4: ph1}[calls['n']](m)
                pyr2.pred_v = pv
                x, F, _ = pyr2.synthesis(C, Lh, 0, 1023); pyr2.pred_v = orig
                mse = np.mean((x - Y) ** 2.0); pts.append((bits / Y.size, 10 * np.log10(1023 ** 2 / mse)))
            res[(clip, pn, name)] = pts
def bd(ref, tst):
    ref = sorted(ref); tst = sorted(tst); lo = max(ref[0][0], tst[0][0]); hi = min(ref[-1][0], tst[-1][0])
    bs = np.exp(np.linspace(np.log(lo), np.log(hi), 20)); f = lambda pts, b: float(np.interp(b, [p[0] for p in pts], [p[1] for p in pts]))
    return np.mean([f(tst, b) - f(ref, b) for b in bs])
for clip in yuv.TRAIN[:2]:
    for pn in ('Y', 'Cb', 'Cr'):
        ref = res[(clip, pn, 'two')]
        print('%-12s %-2s HH predictor dPSNR at matched rate vs two-sided: ' % (clip.split('/')[-1][:12], pn) + ' | '.join('%s %+.3f' % (n, bd(ref, res[(clip, pn, n)])) for n in VAR))
