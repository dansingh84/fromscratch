# CQP-1 transform, final form: pair mean/difference pyramid, 2 vertical x Lh horizontal levels, 4-row blocks,
# TWO-SIDED difference predictors in both axes (P = (m[k-1]-m[k+1]+2)>>2, one-sided at frame edges),
# position-alternating rounding, legality by interval clamp of every leaf from already-final values.
# Whole-frame arrays; the slice/ahead structure only decides WHEN data is available (see omc16.py).
import numpy as np
from pyr import phase, split_h, merge_h, split_v, merge_v, dbox, mbox, BANDS

def pred_h(m):
    p = np.zeros_like(m)
    if m.shape[1] >= 3: p[:, 1:-1] = (m[:, :-2] - m[:, 2:] + 2) >> 2
    if m.shape[1] >= 2: p[:, 0] = (m[:, 0] - m[:, 1] + 1) >> 1; p[:, -1] = (m[:, -2] - m[:, -1] + 1) >> 1
    return p

def pred_v(m):
    p = np.zeros_like(m)
    if m.shape[0] >= 3: p[1:-1] = (m[:-2] - m[2:] + 2) >> 2
    if m.shape[0] >= 2: p[0] = (m[0] - m[1] + 1) >> 1; p[-1] = (m[-2] - m[-1] + 1) >> 1
    return p
import os
HH_TWO = os.environ.get('HH_TWO', '0') == '1'     # design-comparison switch: two-sided HH predictors (4-block ahead)
def pred_hh2(m):
    """HH2: causal across blocks (one row per block): (m[b-1]-m[b]+1)>>1, 0 at the top."""
    if HH_TWO: return pred_v(m)
    p = np.zeros_like(m); p[1:] = (m[:-1] - m[1:] + 1) >> 1; return p
def pred_hh1(m):
    """HH1: in-block symmetric over the block's two pair rows: (m[2b]-m[2b+1]+1)>>1 for both pairs."""
    if HH_TWO: return pred_v(m)
    return np.repeat((m[0::2] - m[1::2] + 1) >> 1, 2, axis=0)

GROUP = {'LL': 'll', 'LH2': 'mid', 'HL2': 'mid', 'HH2': 'mid', 'HL1': 'fine', 'LH1': 'fine', 'HH1': 'fine'}
def group(b): return GROUP.get(b, 'll')          # H3..H5 -> 'll' group (LL-level, two blocks ahead)
def rows_per_block(b): return 2 if b in ('LH1', 'HL1', 'HH1') else 1
def cols_per_unit(b, Lh):
    if b == 'LL' or b == 'H%d' % Lh: return 1
    if b[0] == 'H' and b[1:].isdigit(): return 1 << (Lh - int(b[1:]))
    return 1 << (Lh - 2) if b[-1] == '2' else 1 << (Lh - 1)

def analysis(x, Lh, b0=0):
    """open-loop analysis of a plane (or a window of whole 4-row blocks starting at block b0): band -> array."""
    T = {}
    L1, d = split_h(x, 4 * b0); E1 = d - pred_h(L1)
    LL1, dv = split_v(L1, 2 * b0); T['LH1'] = dv - pred_v(LL1)
    HL1, dv = split_v(E1, 2 * b0); T['HL1'] = HL1; T['HH1'] = dv - pred_hh1(HL1)
    L2, d = split_h(LL1, 2 * b0); E2 = d - pred_h(L2)
    LL2, dv = split_v(L2, b0); T['LH2'] = dv - pred_v(LL2)
    HL2, dv = split_v(E2, b0); T['HL2'] = HL2; T['HH2'] = dv - pred_hh2(HL2)
    ll = LL2
    for k in range(3, Lh + 1):
        ll, d = split_h(ll, b0); T['H%d' % k] = d - pred_h(ll)
    T['LL'] = ll
    return T

def synthesis(C, Lh, lo, hi, b0=0):
    """C: band -> values before clamping (a plane or a window of whole blocks from block b0). Returns (x, Cfinal, IV)."""
    F = {}; IV = {}
    def leaf(name, v, ilo, ihi):
        w = np.clip(v, ilo, ihi); F[name] = w; IV[name] = (ilo, ihi); return w
    full = lambda a: (np.full(a.shape, lo, np.int64), np.full(a.shape, hi, np.int64))
    ll = leaf('LL', C['LL'], *full(C['LL']))
    for k in range(Lh, 2, -1):
        p = pred_h(ll); A0, A1 = full(ll); s = phase(ll.shape[0], ll.shape[1], 1, b0)
        dlo, dhi = dbox(A0, A1, A0, A1, ll, s)
        e = leaf('H%d' % k, C['H%d' % k], dlo - p, dhi - p); ll = merge_h(ll, e + p, b0)
    LL2 = ll
    p = pred_v(LL2); A0, A1 = full(LL2); s = phase(LL2.shape[0], LL2.shape[1], 0, b0)
    dlo, dhi = dbox(A0, A1, A0, A1, LL2, s)
    e = leaf('LH2', C['LH2'], dlo - p, dhi - p); L2 = merge_v(LL2, e + p, b0)
    ph = pred_h(L2); A0, A1 = full(L2); sh = phase(L2.shape[0], L2.shape[1], 1, 2 * b0)
    elo, ehi = dbox(A0, A1, A0, A1, L2, sh); elo = elo - ph; ehi = ehi - ph
    sv = phase(L2.shape[0] // 2, L2.shape[1], 0, b0)
    mlo, mhi = mbox(elo[0::2], ehi[0::2], elo[1::2], ehi[1::2], sv)
    HL2 = leaf('HL2', C['HL2'], mlo, mhi); p = pred_hh2(HL2)
    dlo, dhi = dbox(elo[0::2], ehi[0::2], elo[1::2], ehi[1::2], HL2, sv)
    e = leaf('HH2', C['HH2'], dlo - p, dhi - p); E2 = merge_v(HL2, e + p, b0)
    LL1 = merge_h(L2, E2 + ph, 2 * b0)
    p = pred_v(LL1); A0, A1 = full(LL1); s = phase(LL1.shape[0], LL1.shape[1], 0, 2 * b0)
    dlo, dhi = dbox(A0, A1, A0, A1, LL1, s)
    e = leaf('LH1', C['LH1'], dlo - p, dhi - p); L1 = merge_v(LL1, e + p, 2 * b0)
    ph = pred_h(L1); A0, A1 = full(L1); sh = phase(L1.shape[0], L1.shape[1], 1, 4 * b0)
    elo, ehi = dbox(A0, A1, A0, A1, L1, sh); elo = elo - ph; ehi = ehi - ph
    sv = phase(L1.shape[0] // 2, L1.shape[1], 0, 2 * b0)
    mlo, mhi = mbox(elo[0::2], ehi[0::2], elo[1::2], ehi[1::2], sv)
    HL1 = leaf('HL1', C['HL1'], mlo, mhi); p = pred_hh1(HL1)
    dlo, dhi = dbox(elo[0::2], ehi[0::2], elo[1::2], ehi[1::2], HL1, sv)
    e = leaf('HH1', C['HH1'], dlo - p, dhi - p); E1 = merge_v(HL1, e + p, 2 * b0)
    x = merge_h(L1, E1 + ph, 4 * b0)
    return x, F, IV

if __name__ == '__main__':
    import sys; sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model'); import yuv
    rng = np.random.default_rng(2)
    Y, Cb, Cr = yuv.read_frame(yuv.CELLS['dng720'][0], 1280, 720, 5)
    for pl, Lh in ((Y, 5), (Cb, 4), (Cr, 4)):
        T = analysis(pl, Lh); x, F, IV = synthesis(T, Lh, 0, 1023)
        assert np.array_equal(x, pl)
        for b in BANDS(Lh): assert np.all(F[b] == T[b])
        R = {b: rng.integers(-3000, 3000, T[b].shape) for b in BANDS(Lh)}
        x2, F2, _ = synthesis(R, Lh, 0, 1023); assert x2.min() >= 0 and x2.max() <= 1023
        T2 = analysis(x2, Lh)
        for b in BANDS(Lh): assert np.array_equal(T2[b], F2[b])
    print('pyr2: bijection, legality, reading OK')
