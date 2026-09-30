# design test: causal vs two-sided vs none horizontal predictor; training clips only.
import numpy as np, sys
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import pyr, yuv
W = {'LL': 1, 'H5': 2, 'H4': 2, 'H3': 2, 'LH2': 2, 'HL2': 2, 'HH2': 4, 'LH1': 2, 'HL1': 2, 'HH1': 4}
def ent(q):
    q = np.clip(q, -40, 40).ravel() + 40; c = np.bincount(q, minlength=81).astype(float); p = c[c > 0] / c.sum()
    return -(c[c > 0] * np.log2(p)).sum()
def two_sided(m):
    p = np.zeros_like(m); p[:, 1:-1] = (m[:, :-2] - m[:, 2:] + 2) >> 2
    p[:, 0] = (m[:, 0] - m[:, 1] + 1) >> 1; p[:, -1] = (m[:, -2] - m[:, -1] + 1) >> 1; return p
def none(m): return np.zeros_like(m)
orig = pyr.pred_h
for clip in yuv.TRAIN[:3]:
    Y = yuv.read_frame(clip, 1920, 1080, 2)[0]
    for name, fn in (('causal', orig), ('two-sided', two_sided), ('haar', none)):
        pyr.pred_h = fn
        T = pyr.analysis(Y, 5)
        for s in (4, 8, 16):
            bits = 0; C = {}
            for b in pyr.BANDS(5):
                D = W[b] * s; q = np.round(T[b] / D).astype(np.int64); bits += ent(q); C[b] = q * D
            x, F, _ = pyr.synthesis(C, 5, 0, 1023)
            mse = np.mean((x - Y) ** 2.0)
            print('%-12s %-9s step %2d  bpp %.3f  PSNR %.2f' % (clip.split('/')[-1][:12], name, s, bits / Y.size, 10 * np.log10(1023 ** 2 / mse)), flush=True)
pyr.pred_h = orig
