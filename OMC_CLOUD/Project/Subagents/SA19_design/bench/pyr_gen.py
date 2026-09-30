# SA18: generalised continuous pair pyramid with an arbitrary level-type string, e.g. 'QQHHH' (= pyr.py 2V x 5H) or
# 'QHQHH' (second vertical level moved to horizontal level 3). Q = quad level (vertical pair, then horizontal pairs of
# the vertical mean and difference rows), H = horizontal pair level. Same leaf-interval legality as pyr.py.
import numpy as np
from pyr import pa, ps, par, slope, hhpred, dset, dclamp, inner, mset
import os
LT = os.environ.get('SA18_LT', 'QQHHH')

def bands(lt=None):
    lt = lt or LT; b = ['LL']
    for l in range(len(lt), 0, -1):
        b += ['H%d' % l] if lt[l - 1] == 'H' else ['HL%d' % l, 'LH%d' % l, 'HH%d' % l]
    return b

def analysis(x, Lv=None, Lh=None, lt=None):
    lt = lt or LT; T = {}; ll = x.astype(np.int64)
    for l in range(1, len(lt) + 1):
        h, w = ll.shape
        if lt[l - 1] == 'Q':
            VM, VD = pa(ll[0::2], ll[1::2], par(h // 2, w))
            pv = par(h // 2, w // 2)
            LL, HLr = pa(VM[:, 0::2], VM[:, 1::2], pv)
            LHm, HHr = pa(VD[:, 0::2], VD[:, 1::2], pv)
            T['HL%d' % l] = HLr - slope(LL, 1, pv); T['LH%d' % l] = LHm - slope(LL, 0, pv)
            T['HH%d' % l] = HHr - hhpred(HLr, LHm, pv); ll = LL
        else:
            pv = par(h, w // 2, l)
            m, d = pa(ll[:, 0::2], ll[:, 1::2], pv); T['H%d' % l] = d - slope(m, 1, pv); ll = m
    T['LL'] = ll
    return T

def synthesis(V, lo, hi, Lv=None, Lh=None, legal=True, want_iv=False, lt=None):
    lt = lt or LT; F = {}; IV = {}
    ll = V['LL']
    if legal: ll = np.clip(ll, lo, hi)
    F['LL'] = ll; IV['LL'] = ('iv', np.full(ll.shape, lo), np.full(ll.shape, hi))
    for l in range(len(lt), 0, -1):
        h, w = ll.shape
        if lt[l - 1] == 'H':
            pv = par(h, w, l); p = slope(ll, 1, pv); v = V['H%d' % l] + p
            if legal:
                S = dset(ll, pv, lo, hi, lo, hi); v = dclamp(v, S); IV['H%d' % l] = ('set', p, S)
            F['H%d' % l] = v - p
            a, b = ps(ll, v, pv); ll = np.empty((h, 2 * w), np.int64); ll[:, 0::2] = a; ll[:, 1::2] = b
        else:
            pv = par(h, w)
            p = slope(ll, 1, pv); v = V['HL%d' % l] + p
            if legal:
                S = dset(ll, pv, lo, hi, lo, hi); v = dclamp(v, S); IV['HL%d' % l] = ('set', p, S)
            HLr = v; F['HL%d' % l] = v - p
            a, b = ps(ll, HLr, pv); VM = np.empty((h, 2 * w), np.int64); VM[:, 0::2] = a; VM[:, 1::2] = b
            pvv = par(h, 2 * w)
            SV = dset(VM, pvv, lo, hi, lo, hi); Jlo, Jhi = inner(SV)
            p = slope(ll, 0, pv); v = V['LH%d' % l] + p
            if legal:
                mlo, mhi = mset(pv, Jlo[:, 0::2], Jhi[:, 0::2], Jlo[:, 1::2], Jhi[:, 1::2])
                v = np.clip(v, mlo, mhi); IV['LH%d' % l] = ('iv', mlo - p, mhi - p)
            LHm = v; F['LH%d' % l] = v - p
            p = hhpred(HLr, LHm, pv); v = V['HH%d' % l] + p
            if legal:
                S = dset(LHm, pv, Jlo[:, 0::2], Jhi[:, 0::2], Jlo[:, 1::2], Jhi[:, 1::2]); v = dclamp(v, S)
                IV['HH%d' % l] = ('set', p, S)
            F['HH%d' % l] = v - p
            a, b = ps(LHm, v, pv); VD = np.empty((h, 2 * w), np.int64); VD[:, 0::2] = a; VD[:, 1::2] = b
            x0, x1 = ps(VM, VD, pvv); ll = np.empty((2 * h, 2 * w), np.int64); ll[0::2] = x0; ll[1::2] = x1
    return ll, F, IV
