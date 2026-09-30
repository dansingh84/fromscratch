# SA18 IPL: interpolating (predict-only) pyramid with per-sample leaves. Same band names/shapes as pyr.py (AVG) so the
# codec machinery is shared. Every output sample is written ONCE: sample = clip(prediction from FINAL samples/residuals
# + leaf). Legality = plain per-sample clip: legal, never away (moves only an overshooting value to the rail), exact
# (leaf read back = final sample - prediction; smallest |q| reproducing the clipped value is canonical), no symbol.
# Prediction: 4-point interpolation (Deslauriers-Dubuc 1989) (-1, 9, 9, -1)/16, mirror at picture edges.
import numpy as np
from pyr import mir, par, bands, canon_index, clampf   # canon_index/clampf work with ('iv', lo, hi) sets

def interp(e, axis):
    """prediction of the odd samples between even samples e[k], e[k+1] along axis (mirror at the far edge)."""
    a0 = mir(e, 0, axis); a1 = mir(e, 1, axis); am = mir(e, -1, axis); a2 = mir(e, 2, axis)
    return (9 * (a0 + a1) - (am + a2) + 8) >> 4

def analysis(x, Lv=2, Lh=5):
    T = {}; ll = x.astype(np.int64)
    for l in range(1, Lv + 1):
        VM = ll[0::2]; VO = ll[1::2]
        VD = VO - interp(VM, 0)                          # residual of odd rows (per sample)
        LL = VM[:, 0::2]; T['HL%d' % l] = VM[:, 1::2] - interp(LL, 1)
        LHr = VD[:, 0::2]; T['LH%d' % l] = LHr
        T['HH%d' % l] = VD[:, 1::2] - interp(LHr, 1)
        ll = LL
    for l in range(Lv + 1, Lh + 1):
        e = ll[:, 0::2]; T['H%d' % l] = ll[:, 1::2] - interp(e, 1); ll = e
    T['LL'] = ll
    return T

def synthesis(V, lo, hi, Lv=2, Lh=5, legal=True, want_iv=False):
    F = {}; IV = {}
    cl = (lambda v, p: np.clip(v, lo - p, hi - p)) if legal else (lambda v, p: v)
    ll = V['LL']
    if legal: ll = np.clip(ll, lo, hi)
    F['LL'] = ll; IV['LL'] = ('iv', np.full(ll.shape, lo), np.full(ll.shape, hi))
    for l in range(Lh, Lv, -1):
        p = interp(ll, 1); v = cl(V['H%d' % l], p); F['H%d' % l] = v; IV['H%d' % l] = ('iv', lo - p, hi - p)
        h, w = ll.shape; o = np.empty((h, 2 * w), np.int64); o[:, 0::2] = ll; o[:, 1::2] = p + v; ll = o
    for l in range(Lv, 0, -1):
        h, w = ll.shape
        p = interp(ll, 1); v = cl(V['HL%d' % l], p); F['HL%d' % l] = v; IV['HL%d' % l] = ('iv', lo - p, hi - p)
        VM = np.empty((h, 2 * w), np.int64); VM[:, 0::2] = ll; VM[:, 1::2] = p + v
        pv = interp(VM, 0)                               # vertical prediction of the odd rows
        # LH: odd row, even column
        p = pv[:, 0::2]; v = cl(V['LH%d' % l], p); F['LH%d' % l] = v; IV['LH%d' % l] = ('iv', lo - p, hi - p)
        LHr = v                                          # final residual (after clip) -- read by the HH predictor
        # HH: odd row, odd column: vertical prediction + horizontal interpolation of the final residuals
        p = pv[:, 1::2] + interp(LHr, 1); v = cl(V['HH%d' % l], p); F['HH%d' % l] = v; IV['HH%d' % l] = ('iv', lo - p, hi - p)
        VO = np.empty((h, 2 * w), np.int64); VO[:, 0::2] = pv[:, 0::2] + LHr; VO[:, 1::2] = p + v
        o = np.empty((2 * h, 2 * w), np.int64); o[0::2] = VM; o[1::2] = VO; ll = o
    return ll, F, IV
