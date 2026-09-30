# design test 3: H two-sided; V level-1 in {inblock, two-sided}, V level-2 in {causal, two-sided}; open loop; all planes.
import numpy as np, sys
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import pyr, yuv
W = {'LL': 1, 'H5': 2, 'H4': 2, 'H3': 2, 'LH2': 2, 'HL2': 2, 'HH2': 4, 'LH1': 2, 'HL1': 2, 'HH1': 4}
def ent(q):
    q = np.clip(np.asarray(q).astype(np.int64), -40, 40).ravel() + 40; c = np.bincount(q, minlength=81).astype(float); p = c[c > 0] / c.sum()
    return -(c[c > 0] * np.log2(p)).sum()
def ts_axis1(m):
    p = np.zeros_like(m); p[:, 1:-1] = (m[:, :-2] - m[:, 2:] + 2) >> 2
    p[:, 0] = (m[:, 0] - m[:, 1] + 1) >> 1; p[:, -1] = (m[:, -2] - m[:, -1] + 1) >> 1; return p
def ts_axis0(m):
    p = np.zeros_like(m); p[1:-1] = (m[:-2] - m[2:] + 2) >> 2
    p[0] = (m[0] - m[1] + 1) >> 1; p[-1] = (m[-2] - m[-1] + 1) >> 1; return p
V1 = {'inblock': pyr.pred_v_pairs, 'two': ts_axis0}
V2 = {'causal': pyr.pred_v_blocks, 'two': lambda m, a: ts_axis0(m)}
pyr.pred_h = ts_axis1
res = {}
for clip in yuv.TRAIN[:2]:
    fr = yuv.read_frame(clip, 1920, 1080, 2)
    for pn, Y, Lh in (('Y', fr[0], 5), ('Cb', fr[1], 4), ('Cr', fr[2], 4)):
        for n1, f1 in V1.items():
            for n2, f2 in V2.items():
                pyr.pred_v_pairs = f1; pyr.pred_v_blocks = f2
                pts = []
                for s in (4, 6, 8, 12, 16, 24, 32):
                    T = pyr.analysis(Y, Lh); bits = 0; C = {}
                    for b in pyr.BANDS(Lh):
                        D = W[b] * s; q = np.round(T[b] / D).astype(np.int64); bits += ent(q); C[b] = q * D
                    x, F, _ = pyr.synthesis(C, Lh, 0, 1023); mse = np.mean((x - Y) ** 2.0)
                    pts.append((bits / Y.size, 10 * np.log10(1023 ** 2 / mse)))
                res[(clip, pn, n1, n2)] = pts
def bd(ref, tst):
    ref = sorted(ref); tst = sorted(tst); lo = max(ref[0][0], tst[0][0]); hi = min(ref[-1][0], tst[-1][0])
    bs = np.exp(np.linspace(np.log(lo), np.log(hi), 20))
    f = lambda pts, b: float(np.interp(b, [p[0] for p in pts], [p[1] for p in pts]))
    return np.mean([f(tst, b) - f(ref, b) for b in bs])
for clip in yuv.TRAIN[:2]:
    for pn in ('Y', 'Cb', 'Cr'):
        ref = res[(clip, pn, 'two', 'two')]
        print('%-12s %-2s dPSNR at matched rate vs V1=two/V2=two: ' % (clip.split('/')[-1][:12], pn) +
              ' | '.join('V1=%s V2=%s %+.2f' % (n1, n2, bd(ref, res[(clip, pn, n1, n2)])) for n1 in V1 for n2 in V2))
