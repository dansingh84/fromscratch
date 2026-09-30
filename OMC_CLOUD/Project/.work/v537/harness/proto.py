"""Numpy prototype of the OMC-1 datapath for design validation (C6 measure-first).

Mirrors the planned C codec exactly at the algorithm level:
  - slice = 16-line strip, independent, symmetric extension
  - 5/3 integer lifting: 2 vertical x 5 horizontal levels (Mallat 2 levels, then
    3 horizontal-only levels on the LL), LL DPCM
  - per-band power-of-two shift quantizer, round-half-away, recon = q<<s
  - band shift = master Q + per-band offset o_b (perceptual table), chunk refinement
  - entropy = zero-run buckets {Z1..Z64} + magnitude categories, cost measured by
    Shannon entropy of the symbol stream + raw LSB/sign bits (upper-bounds tANS within ~1-3%)

Used to: validate rate/quality feasibility at 0.5x XS rates, tune o_b offsets,
collect symbol statistics for the static tANS tables.
"""

import numpy as np

# ----------------------------------------------------------------- 5/3 lifting

def fwd53_1d(x):
    """Forward integer 5/3 along last axis. x: int32 array, even length. Returns L,H."""
    s = x[..., 0::2].astype(np.int64)
    d = x[..., 1::2].astype(np.int64)
    # predict: d -= floor((s_i + s_{i+1})/2), symmetric extension at right edge
    s_r = np.concatenate([s[..., 1:], s[..., -1:]], axis=-1)
    d = d - ((s + s_r) >> 1)
    # update: s += floor((d_{i-1} + d_i + 2)/4), symmetric extension at left edge
    d_l = np.concatenate([d[..., :1], d[..., :-1]], axis=-1)
    s = s + ((d_l + d + 2) >> 2)
    return s.astype(np.int32), d.astype(np.int32)


def inv53_1d(L, H):
    s = L.astype(np.int64)
    d = H.astype(np.int64)
    d_l = np.concatenate([d[..., :1], d[..., :-1]], axis=-1)
    s = s - ((d_l + d + 2) >> 2)
    s_r = np.concatenate([s[..., 1:], s[..., -1:]], axis=-1)
    d = d + ((s + s_r) >> 1)
    n = L.shape[-1] + H.shape[-1]
    out = np.zeros(L.shape[:-1] + (n,), dtype=np.int64)
    out[..., 0::2] = s
    out[..., 1::2] = d
    return out.astype(np.int32)


def fwd97m_1d(x):
    """Forward (9,7)-M reversible integer lifting along last axis - exact
    mirror of src/dwt.c fwd1d_97 (predict taps (-1,9,9,-1)/16, update (1,1)/4,
    whole-sample symmetric extension). Used on horizontal levels 1-2."""
    s = x[..., 0::2].astype(np.int64)
    d0 = x[..., 1::2].astype(np.int64)
    half = s.shape[-1]

    def ext(j):
        if j < 0:
            j = -j
        elif j >= half:
            j = max(2 * half - 1 - j, 0)
        return s[..., j:j + 1]

    a = np.concatenate([ext(i - 1) for i in range(half)], axis=-1)
    b = s
    c = np.concatenate([ext(i + 1) for i in range(half)], axis=-1)
    dd = np.concatenate([ext(i + 2) for i in range(half)], axis=-1)
    nine = ((b + c) << 3) + (b + c)
    H = d0 - ((nine - (a + dd) + 8) >> 4)
    H_l = np.concatenate([H[..., :1], H[..., :-1]], axis=-1)
    L = s + ((H_l + H + 2) >> 2)
    return L.astype(np.int32), H.astype(np.int32)


def inv97m_1d(L, H):
    """Inverse (9,7)-M reversible lifting - exact mirror of src/dwt.c
    inv1d_97 (F-7 fix: this function was missing; slice_inv2 wrongly used
    inv53_1d on levels 1-2, breaking perfect reconstruction)."""
    Lc = L.astype(np.int64); Hc = H.astype(np.int64)
    half = Lc.shape[-1]
    H_l = np.concatenate([Hc[..., :1], Hc[..., :-1]], axis=-1)
    s = Lc - ((H_l + Hc + 2) >> 2)
    def ext(j):
        if j < 0: j = -j
        elif j >= half: j = max(2 * half - 1 - j, 0)
        return s[..., j:j + 1]
    a = np.concatenate([ext(i - 1) for i in range(half)], axis=-1)
    c = np.concatenate([ext(i + 1) for i in range(half)], axis=-1)
    dd = np.concatenate([ext(i + 2) for i in range(half)], axis=-1)
    nine = ((s + c) << 3) + (s + c)
    d = Hc + ((nine - (a + dd) + 8) >> 4)
    n = Lc.shape[-1] + Hc.shape[-1]
    out = np.zeros(Lc.shape[:-1] + (n,), dtype=np.int64)
    out[..., 0::2] = s; out[..., 1::2] = d
    return out.astype(np.int32)


def fwd53_v(x):
    """Vertical transform via transpose."""
    L, H = fwd53_1d(np.swapaxes(x, -1, -2))
    return np.swapaxes(L, -1, -2), np.swapaxes(H, -1, -2)


def inv53_v(L, H):
    return np.swapaxes(inv53_1d(np.swapaxes(L, -1, -2), np.swapaxes(H, -1, -2)), -1, -2)


# Band ids in coding order (low->high frequency priority):
# 0:LL  1:HL5 2:HL4 3:HL3  (horizontal-only levels on 4-row LL2 strip)
# 4:LH2 5:HL2 6:HH2  7:LH1 8:HL1 9:HH1
NBANDS = 10


def slice_fwd2(tile):
    """Mallat structure mirroring src/dwt.c omc_slice_fwd: horizontal levels
    1-2 use the (9,7)-M filter, levels 3-5 use 5/3 (matches the C codec)."""
    # Level 1
    Lv, Hv = fwd53_v(tile)          # 8 x W each
    LL1, HL1 = fwd97m_1d(Lv)        # 8 x W/2
    LH1, HH1 = fwd97m_1d(Hv)        # 8 x W/2
    # Level 2 on LL1
    L2, H2 = fwd53_v(LL1)           # 4 x W/2
    LL2, HL2 = fwd97m_1d(L2)        # 4 x W/4
    LH2, HH2 = fwd97m_1d(H2)
    # Horizontal-only levels 3-5 on LL2
    LL3, HL3 = fwd53_1d(LL2)        # 4 x W/8
    LL4, HL4 = fwd53_1d(LL3)        # 4 x W/16
    LL5, HL5 = fwd53_1d(LL4)        # 4 x W/32
    return {0: LL5, 1: HL5, 2: HL4, 3: HL3, 4: LH2, 5: HL2, 6: HH2,
            7: LH1, 8: HL1, 9: HH1}


def slice_inv2(bands):
    LL4 = inv53_1d(bands[0], bands[1])
    LL3 = inv53_1d(LL4, bands[2])
    LL2 = inv53_1d(LL3, bands[3])
    L2 = inv97m_1d(LL2, bands[5])   # F-7 fix: levels 1-2 use (9,7)-M
    H2 = inv97m_1d(bands[4], bands[6])
    LL1 = inv53_v(L2, H2)
    Lv = inv97m_1d(LL1, bands[8])
    Hv = inv97m_1d(bands[7], bands[9])
    return inv53_v(Lv, Hv)


# ----------------------------------------------------------------- quant

def quant(c, s):
    if s == 0:
        return c.copy()
    a = np.abs(c.astype(np.int64))
    q = (a + (1 << (s - 1))) >> s
    return (np.sign(c) * q).astype(np.int32)


def dequant(q, s):
    return (np.sign(q) * (np.abs(q.astype(np.int64)) << s)).astype(np.int32)


# ----------------------------------------------------------------- entropy model

ZRUNS = [64, 32, 16, 8, 4, 2, 1]


NSYM = 7 + 16  # Z64..Z1, CAT1..CAT16


def symbol_counts(q):
    """Histogram of the symbol stream + raw bit count (vectorized, no explicit stream).

    Alphabet: 0..6 = Z64,Z32,Z16,Z8,Z4,Z2,Z1 ; 7.. = CAT1..CAT16 (id 6+cat).
    Raw bits per nonzero: (cat-1) magnitude LSBs + 1 sign.
    """
    flat = q.ravel()
    counts = np.zeros(NSYM, dtype=np.int64)
    nz = np.nonzero(flat)[0]
    if len(nz) == 0:
        runs = np.array([len(flat)], dtype=np.int64)
        raw = 0
    else:
        a = np.abs(flat[nz]).astype(np.int64)
        cat = np.searchsorted(2 ** np.arange(1, 17, dtype=np.int64), a, side="right") + 1
        cc = np.bincount(cat, minlength=17)
        counts[7:7 + 16] = cc[1:17]
        raw = int(cat.sum())  # (cat-1) mag bits + 1 sign bit each
        runs = np.diff(np.concatenate([[-1], nz, [len(flat)]])) - 1
        runs = runs[runs > 0]
    r = runs.copy()
    for zi, zlen in enumerate(ZRUNS):
        counts[zi] += int((r // zlen).sum())
        r = r % zlen
    return counts, raw


def entropy_from_counts(counts):
    tot = counts.sum()
    if tot == 0:
        return 0.0
    nzc = counts[counts > 0]
    p = nzc / tot
    return float(-(nzc * np.log2(p)).sum())


def band_cost_bits(q):
    counts, raw = symbol_counts(q)
    return entropy_from_counts(counts) + raw, counts


# ----------------------------------------------------------------- slice codec

# Perceptual band offsets o_b (added to master Q). Negative = finer.
# order: LL5 HL5 HL4 HL3 LH2 HL2 HH2 LH1 HL1 HH1
DEFAULT_OFF_Y = np.array([-4, -3, -3, -2, -1, -1, 0, 0, 0, 1])
DEFAULT_OFF_C = np.array([-4, -3, -3, -2, -1, -1, 0, 0, 0, 1])
LL_CAP = 2  # absolute max shift for LL band


def encode_slice_est(planes_tiles, Q, offs, bits=10):
    """planes_tiles: list of (tile int32 centered) per plane.
    Returns (total_bits, recon_tiles, all_syms per band for stats)."""
    total = 0.0
    recons = []
    for pi, tile in enumerate(planes_tiles):
        off = offs[pi]
        bands = slice_fwd2(tile)
        rb = {}
        for b in range(NBANDS):
            s = max(0, Q + int(off[b]))
            if b == 0:
                s = min(s, LL_CAP)
            qb = quant(bands[b], s)
            if b == 0:
                d = np.diff(qb, axis=-1, prepend=0)
                cost, _ = band_cost_bits(d)
            else:
                cost, _ = band_cost_bits(qb)
            total += cost
            rb[b] = dequant(qb, s)
        recons.append(slice_inv2(rb))
    return total, recons


def encode_frame_est(Y, Cb, Cr, Q, bits=10, slice_h=16,
                     offY=DEFAULT_OFF_Y, offC=DEFAULT_OFF_C):
    """Whole-frame estimate at fixed master Q. Returns (bits_total, recon planes)."""
    h, w = Y.shape
    mid = 1 << (bits - 1)
    recon = [np.zeros_like(Y, dtype=np.int32),
             np.zeros_like(Cb, dtype=np.int32),
             np.zeros_like(Cr, dtype=np.int32)]
    total = 0.0
    for y0 in range(0, h, slice_h):
        tiles = [Y[y0:y0 + slice_h].astype(np.int32) - mid,
                 Cb[y0:y0 + slice_h].astype(np.int32) - mid,
                 Cr[y0:y0 + slice_h].astype(np.int32) - mid]
        cost, recs = encode_slice_est(tiles, Q, [offY, offC, offC], bits)
        total += cost
        recon[0][y0:y0 + slice_h] = recs[0]
        recon[1][y0:y0 + slice_h] = recs[1]
        recon[2][y0:y0 + slice_h] = recs[2]
    maxv = (1 << bits) - 1
    out = [np.clip(r + mid, 0, maxv).astype(np.uint16) for r in recon]
    return total, out
