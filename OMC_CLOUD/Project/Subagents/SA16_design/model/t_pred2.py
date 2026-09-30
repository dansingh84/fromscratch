# design test 2: {H causal / two-sided} x {V causal / two-sided(ahead)} x {open / closed loop}; training clips.
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
H = {'causal': pyr.pred_h, 'two': ts_axis1}
V = {'causal': (pyr.pred_v_pairs, pyr.pred_v_blocks), 'two': (ts_axis0, lambda m, a: ts_axis0(m))}
Q = lambda v, D: np.round(v / D).astype(np.int64) * D

def closed(x, Lh, s):
    """closed-loop encoder: every leaf's residual is taken against the RECONSTRUCTED predictor."""
    lo, hi = 0, 1023; bits = 0
    # source decomposition (pure splits)
    S = {}
    L1s, d1 = pyr.split_h(x); LL1s, dv1 = pyr.split_v(L1s); HL1s_e = d1  # E1 source diffs need pred -> handled below
    L2s, d2 = pyr.split_h(LL1s); LL2s, dv2 = pyr.split_v(L2s)
    lls = LL2s; hs = {}
    for k in range(3, Lh + 1): lls, d = pyr.split_h(lls); hs[k] = (lls.copy(), d)
    # LL
    ll = np.clip(Q(lls, W['LL'] * s), lo, hi); bits += ent(np.round(lls / (W['LL'] * s)))
    def leafq(name, target, ilo, ihi):
        nonlocal bits; D = W[name] * s; q = np.round(target / D); bits += ent(q); return np.clip((q * D).astype(np.int64), ilo, ihi)
    full = lambda a: (np.full(a.shape, lo, np.int64), np.full(a.shape, hi, np.int64))
    for k in range(Lh, 2, -1):
        p = pyr.pred_h(ll); A0, A1 = full(ll); sph = pyr.phase(ll.shape[0], ll.shape[1], 1)
        dlo, dhi = pyr.dbox(A0, A1, A0, A1, ll, sph)
        e = leafq('H%d' % k, hs[k][1] - p, dlo - p, dhi - p); ll = pyr.merge_h(ll, e + p)
    LL2 = ll
    p = pyr.pred_v_blocks(LL2, None); A0, A1 = full(LL2); sp = pyr.phase(LL2.shape[0], LL2.shape[1], 0)
    dlo, dhi = pyr.dbox(A0, A1, A0, A1, LL2, sp); e = leafq('LH2', dv2 - p, dlo - p, dhi - p); L2 = pyr.merge_v(LL2, e + p)
    ph = pyr.pred_h(L2); A0, A1 = full(L2); sh = pyr.phase(L2.shape[0], L2.shape[1], 1)
    elo, ehi = pyr.dbox(A0, A1, A0, A1, L2, sh); elo -= ph; ehi -= ph
    E2s = d2 - ph                      # source diff against reconstructed predictor
    HL2s, HH2s = pyr.split_v(E2s)
    sv = pyr.phase(L2.shape[0] // 2, L2.shape[1], 0); mlo, mhi = pyr.mbox(elo[0::2], ehi[0::2], elo[1::2], ehi[1::2], sv)
    HL2 = leafq('HL2', HL2s, mlo, mhi); p = pyr.pred_v_blocks(HL2, None)
    dlo, dhi = pyr.dbox(elo[0::2], ehi[0::2], elo[1::2], ehi[1::2], HL2, sv); e = leafq('HH2', HH2s - p, dlo - p, dhi - p)
    E2 = pyr.merge_v(HL2, e + p); LL1 = pyr.merge_h(L2, E2 + ph)
    p = pyr.pred_v_pairs(LL1); A0, A1 = full(LL1); sp = pyr.phase(LL1.shape[0], LL1.shape[1], 0)
    dlo, dhi = pyr.dbox(A0, A1, A0, A1, LL1, sp); e = leafq('LH1', dv1 - p, dlo - p, dhi - p); L1 = pyr.merge_v(LL1, e + p)
    ph = pyr.pred_h(L1); A0, A1 = full(L1); sh = pyr.phase(L1.shape[0], L1.shape[1], 1)
    elo, ehi = pyr.dbox(A0, A1, A0, A1, L1, sh); elo -= ph; ehi -= ph
    E1s = d1 - ph; HL1s, HH1s = pyr.split_v(E1s)
    sv = pyr.phase(L1.shape[0] // 2, L1.shape[1], 0); mlo, mhi = pyr.mbox(elo[0::2], ehi[0::2], elo[1::2], ehi[1::2], sv)
    HL1 = leafq('HL1', HL1s, mlo, mhi); p = pyr.pred_v_pairs(HL1)
    dlo, dhi = pyr.dbox(elo[0::2], ehi[0::2], elo[1::2], ehi[1::2], HL1, sv); e = leafq('HH1', HH1s - p, dlo - p, dhi - p)
    E1 = pyr.merge_v(HL1, e + p); xr = pyr.merge_h(L1, E1 + ph)
    return xr, bits

for clip in yuv.TRAIN[:2]:
    fr = yuv.read_frame(clip, 1920, 1080, 2)
    for pn, Y, Lh in (('Y', fr[0], 5), ('Cb', fr[1], 4), ('Cr', fr[2], 4)):
     for hn, hf in H.items():
        for vn, (vp, vb) in V.items():
            pyr.pred_h = hf; pyr.pred_v_pairs = vp; pyr.pred_v_blocks = vb
            for s in (6, 8, 12, 16, 24):
                T = pyr.analysis(Y, Lh); bits = 0; C = {}
                for b in pyr.BANDS(Lh):
                    D = W[b] * s; q = np.round(T[b] / D).astype(np.int64); bits += ent(q); C[b] = q * D
                x, F, _ = pyr.synthesis(C, Lh, 0, 1023); mse = np.mean((x - Y) ** 2.0)
                print('%-10s %-2s H=%-6s V=%-6s open   step %2d  bpp %.3f  PSNR %.2f' % (clip.split('/')[-1][:10], pn, hn, vn, s, bits / Y.size, 10 * np.log10(1023 ** 2 / mse)), flush=True)
                xr, bits = closed(Y, Lh, s); mse = np.mean((xr - Y) ** 2.0)
                print('%-10s %-2s H=%-6s V=%-6s closed step %2d  bpp %.3f  PSNR %.2f' % (clip.split('/')[-1][:10], pn, hn, vn, s, bits / Y.size, 10 * np.log10(1023 ** 2 / mse)), flush=True)
