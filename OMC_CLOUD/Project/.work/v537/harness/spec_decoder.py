#!/usr/bin/env python3
"""Independent OMC decoder written from docs/BITSTREAM.md alone (C8 exercise).

Normative inputs used:
  - docs/BITSTREAM.md (spec v4.7)
  - src/tables.c        : omc_tans_counts_legacy[16][4][16]   (read as data, spec section 6)
  - src/tables_v4.c.inc : omc_tans_counts_v4[G][16][16]       (read as data, spec section 6 / 9.2)
  - src/alloc.c         : omc_off / omc_off_c444 / omc_refine_order (read as data, spec section 6)

No implementation source (codec.c, tans.c, dwt.c, ...) was consulted.
Ambiguities encountered are listed in docs/SPEC_GAPS.md.

Usage:
  spec_decoder.py header <in.omc>
  spec_decoder.py decode <in.omc> <out.raw>
  spec_decoder.py trace  <in.omc> <frame> <slice> <prefix>   (dump coef/recon of one slice)
"""
import sys, os, re, zlib, struct, hashlib
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")

# ---------------------------------------------------------------- normative tables

def _parse_c_array(path, name):
    txt = open(path).read()
    txt = re.sub(r"/\*.*?\*/", "", txt, flags=re.S)
    m = re.search(re.escape(name) + r"\s*\[[^=]*=\s*\{(.*?)\n\};", txt, flags=re.S)
    if not m:
        raise RuntimeError("array %s not found in %s" % (name, path))
    return [int(t) for t in re.findall(r"-?\d+", m.group(1))]

_legacy = _parse_c_array(os.path.join(SRC, "tables.c"), "omc_tans_counts_legacy")
assert len(_legacy) == 16 * 4 * 16, len(_legacy)
TANS_LEGACY = np.array(_legacy, np.int64).reshape(16, 4, 16)

_v4 = _parse_c_array(os.path.join(SRC, "tables_v4.c.inc"), "omc_tans_counts_v4")
assert len(_v4) % (16 * 16) == 0, len(_v4)
TANS_V4 = np.array(_v4, np.int64).reshape(len(_v4) // 256, 16, 16)

# alloc.c (spec 3.2 / 6): transcribed constants (verified against src/alloc.c data)
OMC_OFF = [
    [[-4,-3,-3,-2,-1,-1, 0, 0, 0, 1],
     [-4,-3,-3,-2,-1,-1, 0, 0, 0, 1],
     [-4,-3,-3,-2,-1,-1, 0, 0, 0, 1]],
    [[-4,-3,-3,-2,-1,-1,-1,-1,-1, 0],
     [-4,-3,-3,-2,-1,-1, 0, 0, 0, 1],
     [-4,-3,-3,-2,-1,-1, 0, 0, 0, 1]],
    [[-4,-3,-3,-2,-1,-1, 0, 0, 0, 1],
     [-4,-3,-2,-1, 0, 1, 2, 2, 2, 3],
     [-4,-3,-2,-1, 0, 1, 2, 2, 2, 3]],
    [[-4,-3,-3,-2,-1,-1,-1,-1,-1, 0],
     [-4,-3,-2,-1, 0, 1, 2, 2, 2, 3],
     [-4,-3,-2,-1, 0, 1, 2, 2, 2, 3]],
]
OFF444 = [0, 0, 1, 1, 1, 1, 1, 1, 1, 1]
_round1 = [(0,3),(0,4),(0,5),(1,3),(2,3),(1,4),(1,5),(2,4),(2,5),
           (0,6),(1,6),(2,6),
           (0,7),(0,8),(1,7),(1,8),(2,7),(2,8),(0,9),(1,9),(2,9)]
REFINE = _round1 + _round1 + [(0,3),(0,4),(0,5),(0,6),(0,7),(0,8),(0,9)]
LL_CAP = 2

# ---------------------------------------------------------------- tANS

L = 1024
STEP = L // 2 + L // 8 + 3  # 643

_table_cache = {}

def tans_table(era, group, ctx):
    """era: 'legacy' or 'v4'. Returns (sym, nbits, base) lists indexed by state 0..1023."""
    key = (era, group, ctx)
    t = _table_cache.get(key)
    if t is not None:
        return t
    counts = (TANS_LEGACY if era == "legacy" else TANS_V4)[group][ctx]
    assert counts.sum() == L
    spread = [0] * L
    pos = 0
    for s in range(16):
        for _ in range(int(counts[s])):
            spread[pos] = s
            pos = (pos + STEP) % L
    sym = spread
    nbits = [0] * L
    base = [0] * L
    occ = [0] * 16
    for i in range(L):
        s = spread[i]
        x = int(counts[s]) + occ[s]
        occ[s] += 1
        nb = 11 - x.bit_length()          # 10 - floor(log2 x)
        nbits[i] = nb
        base[i] = (x << nb) - L
    t = (sym, nbits, base)
    _table_cache[key] = t
    return t

# ---------------------------------------------------------------- bit access

def bits_le(buf, pos, n):
    """Read n bits at bit position pos of buf, LSB-first convention (spec 4)."""
    if n == 0:
        return 0
    b0 = pos >> 3
    b1 = (pos + n - 1) >> 3
    v = int.from_bytes(buf[b0:b1 + 1], "little")
    return (v >> (pos & 7)) & ((1 << n) - 1)

class BackBits:
    """Backward reader from bit `used_bits` down to 0 (spec 4.5)."""
    __slots__ = ("d", "pos")
    def __init__(self, data, used_bits):
        self.d = data
        self.pos = used_bits
    def read(self, n):
        p = self.pos - n
        if p < 0:
            raise ValueError("payload bit underflow")
        self.pos = p
        b0 = p >> 3
        b1 = (p + n - 1) >> 3
        v = int.from_bytes(self.d[b0:b1 + 1], "little")
        return (v >> (p & 7)) & ((1 << n) - 1)

# ---------------------------------------------------------------- sign tiles (spec 4.6, 9.4)

def build_white_tile():
    tile = np.zeros((256, 256), np.uint8)
    x = 0x4F4D4331
    for r in range(256):
        for w in range(8):
            for j in range(32):
                x = (x * 1103515245 + 12345) & 0xFFFFFFFF
                tile[r][w * 32 + j] = (x >> 30) & 1
    return tile

def build_corr_tile(white):
    w = white.astype(np.int32) * 2 - 1  # +1 set, -1 clear
    s = (w + np.roll(w, -1, 1) + np.roll(w, -1, 0) + np.roll(np.roll(w, -1, 0), -1, 1))
    bit = np.where(s > 0, 1, np.where(s < 0, 0, white)).astype(np.uint8)
    yy, xx = np.mgrid[0:256, 0:256]
    return (bit ^ ((xx + yy) & 1)).astype(np.uint8)

_WHITE = None
_CORR = None

def get_tile(correlated):
    global _WHITE, _CORR
    if _WHITE is None:
        _WHITE = build_white_tile()
    if not correlated:
        return _WHITE
    global _CORR
    if _CORR is None:
        _CORR = build_corr_tile(_WHITE)
    return _CORR

# ---------------------------------------------------------------- wavelet (spec 4.1)

def _refl(idx, half):
    """whole-sample symmetric reflection, clamped to >= 0"""
    out = []
    for j in idx:
        if j < 0:
            j = -j
        if j >= half:
            j = 2 * half - 1 - j
        if j < 0:
            j = 0
        out.append(j)
    return out

def fwd53(x):
    half = x.shape[-1] // 2
    s = x[..., 0::2]
    od = x[..., 1::2]
    ip1 = _refl(list(range(1, half + 1)), half)
    d = od - ((s + s[..., ip1]) >> 1)
    dm1 = np.concatenate([d[..., :1], d[..., :-1]], axis=-1)
    Lo = s + ((dm1 + d + 2) >> 2)
    return np.concatenate([Lo, d], axis=-1)

def inv53(y):
    half = y.shape[-1] // 2
    Lo = y[..., :half]
    d = y[..., half:]
    dm1 = np.concatenate([d[..., :1], d[..., :-1]], axis=-1)
    s = Lo - ((dm1 + d + 2) >> 2)
    ip1 = _refl(list(range(1, half + 1)), half)
    od = d + ((s + s[..., ip1]) >> 1)
    out = np.empty_like(y)
    out[..., 0::2] = s
    out[..., 1::2] = od
    return out

def fwd97(x):
    half = x.shape[-1] // 2
    s = x[..., 0::2]
    od = x[..., 1::2]
    im1 = _refl(list(range(-1, half - 1)), half)
    ip1 = _refl(list(range(1, half + 1)), half)
    ip2 = _refl(list(range(2, half + 2)), half)
    d = od - ((9 * (s + s[..., ip1]) - (s[..., im1] + s[..., ip2]) + 8) >> 4)
    dm1 = np.concatenate([d[..., :1], d[..., :-1]], axis=-1)
    Lo = s + ((dm1 + d + 2) >> 2)
    return np.concatenate([Lo, d], axis=-1)

def inv97(y):
    half = y.shape[-1] // 2
    Lo = y[..., :half]
    d = y[..., half:]
    dm1 = np.concatenate([d[..., :1], d[..., :-1]], axis=-1)
    s = Lo - ((dm1 + d + 2) >> 2)
    im1 = _refl(list(range(-1, half - 1)), half)
    ip1 = _refl(list(range(1, half + 1)), half)
    ip2 = _refl(list(range(2, half + 2)), half)
    od = d + ((9 * (s + s[..., ip1]) - (s[..., im1] + s[..., ip2]) + 8) >> 4)
    out = np.empty_like(y)
    out[..., 0::2] = s
    out[..., 1::2] = od
    return out

def forward_transform(block, sh, W):
    """block: (sh, W) int array of centred samples. Returns transform-domain (sh, W)."""
    A = block.astype(np.int64)
    A = fwd53(A.T).T                          # vertical level 1, rows reorder L|H
    A = fwd97(A)                              # horizontal level 1
    A[:sh // 2, :W // 2] = fwd53(A[:sh // 2, :W // 2].T).T   # vertical level 2
    A[:sh // 2, :W // 2] = fwd97(A[:sh // 2, :W // 2])       # horizontal level 2
    for wl in (W // 4, W // 8, W // 16):      # horizontal 5/3 levels 3..5
        A[:sh // 4, :wl] = fwd53(A[:sh // 4, :wl])
    return A

def inverse_transform(coef, sh, W):
    A = coef.astype(np.int64).copy()
    for wl in (W // 16, W // 8, W // 4):
        A[:sh // 4, :wl] = inv53(A[:sh // 4, :wl])
    A[:sh // 2, :W // 2] = inv97(A[:sh // 2, :W // 2])
    A[:sh // 2, :W // 2] = inv53(A[:sh // 2, :W // 2].T).T
    A = inv97(A)
    A = inv53(A.T).T
    return A

def band_geoms(sh, Wp):
    r2 = sh // 4
    r1 = sh // 2
    return [
        (0, r2,      0,       Wp // 32),
        (0, r2,      Wp // 32, Wp // 16),
        (0, r2,      Wp // 16, Wp // 8),
        (0, r2,      Wp // 8,  Wp // 4),
        (r2, 2 * r2, 0,        Wp // 4),
        (0, r2,      Wp // 4,  Wp // 2),
        (r2, 2 * r2, Wp // 4,  Wp // 2),
        (r1, sh,     0,        Wp // 2),
        (0, r1,      Wp // 2,  Wp),
        (r1, sh,     Wp // 2,  Wp),
    ]

# ---------------------------------------------------------------- headers

class StreamHeader:
    pass

def parse_stream_header(d):
    h = StreamHeader()
    (h.magic, h.major, h.minor) = struct.unpack_from("<IBB", d, 0)
    (h.width, h.height) = struct.unpack_from("<HH", d, 6)
    h.depth = d[10]
    h.chroma = d[11]           # 0 = 4:2:2, 1 = 4:4:4
    h.slice_h = d[12]
    (h.fps_n, h.fps_d) = struct.unpack_from("<HH", d, 13)
    h.primaries, h.transfer, h.matrix, h.full_range = d[17], d[18], d[19], d[20]
    (h.bits_per_slice,) = struct.unpack_from("<I", d, 21)
    h.refresh_r = d[25] or 8
    h.scan_type = d[26]
    h.pixel_flags = d[27]
    (h.display_h, h.display_w) = struct.unpack_from("<HH", d, 28)
    if h.magic != 0x4F4D4331:
        raise ValueError("bad magic")
    if h.major != 4 or h.minor > 7:
        raise ValueError("unsupported version %d.%d" % (h.major, h.minor))
    h.N = h.height // h.slice_h
    h.F = h.N * h.bits_per_slice // 8
    return h

class SliceHeader:
    pass

def parse_slice_header(buf, minor):
    """buf: >= 48 bytes at slice start. Returns SliceHeader or None on bad sync/range."""
    if len(buf) < 48:
        return None
    g = lambda pos, n: bits_le(buf, pos, n)
    s = SliceHeader()
    s.sync = g(0, 32)
    if s.sync != 0x4F4D5331:
        return None
    s.fidx8 = g(32, 8)
    s.slice_idx = g(40, 16)
    s.Q = g(56, 4)
    s.profile = g(60, 2)
    nsb = g(62, 8)
    s.blockmv = bool(nsb & 0x80) and minor >= 3
    s.n_steps = nsb & 0x7F
    s.partial_chunks = g(70, 16)
    s.used_bits = g(86, 24)
    s.state = g(110, 16)
    s.groups = [g(126 + 4 * i, 4) for i in range(30)]
    mm = g(246, 30)
    s.mode = [(mm >> i) & 1 for i in range(30)]          # index p*10+b
    if minor == 0:
        s.mv = [(g(276 + 9 * r, 5) - 16, g(276 + 9 * r + 5, 4) - 8) for r in range(4)]
        fb = g(312, 18)
        s.gain = [0, 0, 0]
    else:
        s.mv = [(g(276 + 13 * r, 7) - 64, g(276 + 13 * r + 7, 6) - 32) for r in range(4)]
        fb = g(328, 18)
        s.gain = [g(346 + 2 * p, 2) for p in range(3)]
    s.fill = [(fb >> i) & 1 for i in range(18)]          # index p*6+(b-4)
    s.crc = struct.unpack_from("<I", buf, 44)[0]
    if s.n_steps > len(REFINE) or s.state >= 1024:
        return None
    return s

# ---------------------------------------------------------------- shifts (spec 3.2)

def band_shifts(Q, profile, n_steps, partial_chunks, chroma444):
    shift = [[0] * 10 for _ in range(3)]
    for p in range(3):
        for b in range(10):
            v = Q + OMC_OFF[profile][p][b] + (OFF444[b] if (chroma444 and p > 0) else 0)
            shift[p][b] = min(max(v, 0), 15)
    for k in range(n_steps):
        p, b = REFINE[k]
        shift[p][b] = max(shift[p][b] - 1, 0)
    partial = None
    if partial_chunks > 0 and n_steps < len(REFINE):
        partial = REFINE[n_steps]                        # (plane, band)
    for p in range(3):
        shift[p][0] = min(shift[p][0], LL_CAP)
    return shift, partial

# ---------------------------------------------------------------- entropy decode

def q2(a):
    if a == 0:
        return 0
    if a == 1:
        return 1
    if a <= 3:
        return 2
    return 3

def decode_slice_symbols(sh, widths, groups, era, rd, x0):
    """Decode all coded values v (per spec 4.4) for the 3 planes.
    Returns (list of 3 (sh,Wp) int32 arrays of coded values, final_state)."""
    v2 = era == "v4"
    x = x0
    read = rd.read
    planes = []
    for p in range(3):
        Wp = widths[p]
        buf = np.zeros((sh, Wp), np.int32)
        geoms = band_geoms(sh, Wp)
        for b in range(10):
            r0, r1, c0, c1 = geoms[b]
            rows = r1 - r0
            cols = c1 - c0
            grp = groups[p * 10 + b]
            nctx = 16 if v2 else 4
            tabs = [tans_table(era, grp, c) for c in range(nctx)]
            prev = [0] * cols           # row buffer of ctx codes (sig or q2)
            band = buf[r0:r1, c0:c1]
            for r in range(rows):
                rowv = band[r]
                left = 0
                for c in range(cols):
                    above = prev[c]
                    ctx = left * 4 + above if v2 else left + 2 * above
                    sym, nb, base = tabs[ctx]
                    cat = sym[x]
                    n = nb[x]
                    x = base[x] + (read(n) if n else 0)
                    if cat:
                        raw = read(cat)
                        mag = (1 << (cat - 1)) | (raw & ((1 << (cat - 1)) - 1))
                        v = -mag if (raw >> (cat - 1)) & 1 else mag
                        rowv[c] = v
                        if v2:
                            a = mag
                            code = 1 if a == 1 else (2 if a <= 3 else 3)
                        else:
                            code = 1
                    else:
                        code = 0
                    prev[c] = code
                    left = code
        planes.append(buf)
    return planes, x

# ---------------------------------------------------------------- motion (spec 3.1, 4.2b, 9.1)

def column_vectors(Wp, W, mv, blockfield, sub_x):
    """Per-column (mvx_half, mvy_half, intra) for a plane of width Wp.
    sub_x = 2 for 4:2:2 chroma else 1. Region/block indexing follows luma columns."""
    mvx = np.zeros(Wp, np.int32)
    mvy = np.zeros(Wp, np.int32)
    intra = np.zeros(Wp, bool)
    regw = Wp // 4
    for r in range(4):
        vx, vy = mv[r]
        if sub_x == 2:
            vx = int(vx / 2) if vx >= 0 else -((-vx) // 2)   # trunc toward zero
        mvx[r * regw:(r + 1) * regw] = vx
        mvy[r * regw:(r + 1) * regw] = vy
    if blockfield is not None:
        bw = 16 // sub_x
        for k, byte in enumerate(blockfield):
            cols = slice(k * bw, min((k + 1) * bw, Wp))
            if byte & 1:
                intra[cols] = True
            else:
                dx = ((byte >> 1) & 15) - 8
                dy = ((byte >> 4) & 7) - 4
                if sub_x == 2:
                    mvx[cols] += dx          # full-pel luma == half-chroma-pel
                else:
                    mvx[cols] += 2 * dx
                mvy[cols] += 2 * dy
    return mvx, mvy, intra

def mc_fetch(ref, y0, sh, mvx, mvy, intra, mid):
    H, Wp = ref.shape
    cols = np.arange(Wp)
    bx = mvx >> 1
    fx = mvx & 1
    by = mvy >> 1
    fy = mvy & 1
    xs = cols + bx
    x0c = np.clip(xs, 0, Wp - 1)
    x1c = np.clip(xs + 1, 0, Wp - 1)
    out = np.empty((sh, Wp), np.int32)
    for r in range(sh):
        ys = y0 + r + by
        y0c = np.clip(ys, 0, H - 1)
        y1c = np.clip(ys + 1, 0, H - 1)
        a = ref[y0c, x0c].astype(np.int32)
        b = ref[y0c, x1c].astype(np.int32)
        c = ref[y1c, x0c].astype(np.int32)
        d = ref[y1c, x1c].astype(np.int32)
        v = np.where(fx & fy, (a + b + c + d + 2) >> 2,
            np.where(fx, (a + b + 1) >> 1,
            np.where(fy, (a + c + 1) >> 1, a)))
        out[r] = np.where(intra, mid, v)
    return out

# ---------------------------------------------------------------- grain fill (spec 4.6)

def apply_grain_fill(coef, qv, shiftmap, sh, Wp, fill_bits, gain_code, tile,
                     f_off, slice_idx, p, mid, graded):
    r2 = sh // 4
    llc = Wp // 32
    LLb = coef[0:r2, 0:llc]
    dimr, dimc = r2, llc
    foy = (61 * f_off + 37 * slice_idx) & 255
    geoms = band_geoms(sh, Wp)
    for b in range(4, 10):
        if not fill_bits[p * 6 + (b - 4)]:
            continue
        r0, r1, c0, c1 = geoms[b]
        rows = r1 - r0
        cols = c1 - c0
        s = shiftmap[r0:r1, c0:c1]
        cond = (qv[r0:r1, c0:c1] == 0) & (coef[r0:r1, c0:c1] == 0) & (s >= 3)
        if not cond.any():
            continue
        R, C = np.mgrid[0:rows, 0:cols]
        if b <= 6:
            rc = R
            xc = C >> 3
        else:
            rc = R >> 1
            xc = C >> 4
        rc = np.minimum(np.maximum(rc, 1), dimr - 2)     # ordered clamp (spec 4.6)
        xc = np.minimum(np.maximum(xc, 1), dimc - 2)
        r_lo = np.maximum(rc - 1, 0)
        r_hi = np.minimum(rc + 1, dimr - 1)
        x_lo = np.maximum(xc - 1, 0)
        x_hi = np.minimum(xc + 1, dimc - 1)
        actv = (np.abs(LLb[rc, x_hi] - LLb[rc, x_lo]) +
                np.abs(LLb[r_hi, xc] - LLb[r_lo, xc]))
        act = actv >= 12
        head = np.abs(LLb[rc, xc]) <= mid - (mid >> 4)
        m = cond & act & head
        if not m.any():
            continue
        if graded:
            # NOT in BITSTREAM.md (spec gap): minor >= 6 reference behavior,
            # reverse-engineered from golden traces (c6_gr_corr, c7_*).
            # base = 1<<(s-2); gain code 1 HALVES it for s >= 4 (spec says
            # 1.25x); then the amplitude grades down with LL activity:
            # >>1 for act < 48, >>2 for act < 24, floored at 1.
            # Gain codes 2/3 were never observed in the vectors; behavior
            # under them is unknown (documented in SPEC_GAPS.md).
            base = (1 << np.maximum(s.astype(np.int64) - 2, 0)).astype(np.int64)
            if gain_code == 1:
                base = np.where(s >= 4, base >> 1, base)
            elif gain_code in (2, 3):
                raise ValueError("gain code %d semantics unverified for minor>=6" % gain_code)
            t = np.where(actv >= 48, 0, np.where(actv >= 24, 1, 2))
            a = np.maximum(base >> t, 1)
        else:
            a = (1 << (s.astype(np.int64) - 2)).astype(np.int64)
            if gain_code:
                g = a.copy()
                if gain_code == 1:
                    g = a + (a >> 2)
                elif gain_code == 2:
                    g = a + (a >> 1)
                elif gain_code == 3:
                    g = a + (a >> 1) + (a >> 2)
                a = np.where(s >= 4, g, a)
        fox = (97 * f_off + 21 * b + 124 * p) & 255
        sign = tile[(R + foy) & 255, (C + fox) & 255]
        val = np.where(sign == 1, a, -a)
        blk = coef[r0:r1, c0:c1]
        blk[m] = val[m]

# ---------------------------------------------------------------- slice decode

class SliceResult:
    pass

def decode_slice(h, sl, mvfield, payload, refs, y0, want_trace=False):
    era = "legacy" if h.minor <= 3 else "v4"
    W = h.width
    widths = [W, W, W] if h.chroma == 1 else [W, W // 2, W // 2]
    sh = h.slice_h
    mid = 1 << (h.depth - 1)
    shift, partial = band_shifts(sl.Q, sl.profile, sl.n_steps, sl.partial_chunks,
                                 h.chroma == 1)
    rd = BackBits(payload, sl.used_bits)
    vplanes, xfin = decode_slice_symbols(sh, widths, sl.groups, era, rd, sl.state)
    if xfin != 0:
        raise ValueError("tANS final state %d != 0" % xfin)
    if rd.pos != 0:
        raise ValueError("payload not fully consumed: %d bits left" % rd.pos)
    static_fill = bool(h.pixel_flags & 4)
    tile = get_tile(bool(h.pixel_flags & 2))
    f_off = 0 if static_fill else sl.fidx8
    res = SliceResult()
    res.coefs = []
    res.recons = []
    for p in range(3):
        Wp = widths[p]
        geoms = band_geoms(sh, Wp)
        v = vplanes[p]
        # LL DPCM (spec 4.3): horizontal prefix sum per band row
        q = v.copy()
        r0, r1, c0, c1 = geoms[0]
        q[r0:r1, c0:c1] = np.cumsum(v[r0:r1, c0:c1], axis=1, dtype=np.int64)
        # per-coefficient shift map
        smap = np.zeros((sh, Wp), np.int16)
        for b in range(10):
            br0, br1, bc0, bc1 = geoms[b]
            smap[br0:br1, bc0:bc1] = shift[p][b]
        if partial is not None and partial[0] == p:
            pb = partial[1]
            br0, br1, bc0, bc1 = geoms[pb]
            bw = bc1 - bc0
            ncoef = min(sl.partial_chunks * 256, (br1 - br0) * bw)
            idx = np.arange(ncoef)
            rr = br0 + idx // bw
            cc = bc0 + idx % bw
            smap[rr, cc] = np.maximum(smap[rr, cc] - 1, 0)
        deq = (q.astype(np.int64)) << smap.astype(np.int64)
        # temporal prediction (spec 4.2b)
        inter_bits = [sl.mode[p * 10 + b] for b in range(10)]
        coef = deq
        if any(inter_bits):
            sub_x = 2 if (h.chroma == 0 and p > 0) else 1
            mvx, mvy, intra = column_vectors(Wp, W, sl.mv, mvfield, sub_x)
            fetch = mc_fetch(refs[p], y0, sh, mvx, mvy, intra, mid)
            pred = forward_transform(fetch - mid, sh, Wp)
            for b in range(10):
                if inter_bits[b]:
                    br0, br1, bc0, bc1 = geoms[b]
                    coef[br0:br1, bc0:bc1] += pred[br0:br1, bc0:bc1]
        # grain fill (spec 4.6): q-domain zeros; for inter bands composed value must be 0 too
        apply_grain_fill(coef, q, smap, sh, Wp, sl.fill, sl.gain[p], tile,
                         f_off, sl.slice_idx, p, mid, graded=(h.minor >= 6))
        rec = inverse_transform(coef, sh, Wp) + mid
        rec = np.clip(rec, 0, (1 << h.depth) - 1)
        res.coefs.append(coef.astype(np.int32))
        res.recons.append(rec.astype(np.uint16))
    return res

# ---------------------------------------------------------------- frame/stream walk

def slice_wire_size(h, sl):
    mvb = ( (h.width + 15) // 16 ) if sl.blockmv else 0
    return 48 + mvb + (sl.used_bits + 7) // 8, mvb

def try_slice_at(h, frame, pos, fidx):
    """Parse+validate a slice at byte pos of the frame. Returns (sl, mvfield, payload, end) or None."""
    sl = parse_slice_header(frame[pos:pos + 48], h.minor)
    if sl is None:
        return None
    total, mvb = slice_wire_size(h, sl)
    if pos + total > len(frame):
        return None
    if total > 2 * (h.bits_per_slice // 8):
        return None
    mvfield = frame[pos + 48:pos + 48 + mvb] if mvb else None
    payload = frame[pos + 48 + mvb:pos + total]
    if zlib.crc32(frame[pos:pos + 44] + (mvfield or b"") + payload) != sl.crc:
        return None
    return sl, mvfield, payload, pos + total

def scan_frame(h, frame, fidx):
    """Locate valid slices. Normal path is contiguous; on failure scan for sync."""
    found = {}
    pos = 0
    guard = 0
    while pos + 48 <= len(frame) and len(found) < h.N:
        r = try_slice_at(h, frame, pos, fidx)
        if r is not None:
            sl, mvfield, payload, end = r
            if sl.slice_idx < h.N and sl.slice_idx not in found and sl.fidx8 == (fidx & 255):
                found[sl.slice_idx] = (sl, mvfield, payload)
                pos = end
                continue
        # resync: scan for next sync pattern (LSB-first bytes of 0x4F4D5331)
        nxt = frame.find(b"\x31\x53\x4d\x4f", pos + 1)
        if nxt < 0:
            break
        pos = nxt
        guard += 1
        if guard > 4096:
            break
    return found

def decode_stream(path, out_path=None, trace=None, verbose=False):
    data = open(path, "rb").read()
    h = parse_stream_header(data[:32])
    W, H = h.width, h.height
    widths = [W, W, W] if h.chroma == 1 else [W, W // 2, W // 2]
    mid = 1 << (h.depth - 1)
    refs = [np.full((H, w), mid, np.int32) for w in widths]
    nframes = (len(data) - 32) // h.F
    out = bytearray()
    damaged = 0
    trace_out = None
    for f in range(nframes):
        frame = data[32 + f * h.F:32 + (f + 1) * h.F]
        found = scan_frame(h, frame, f)
        planes = [np.zeros((H, w), np.uint16) for w in widths]
        for s in range(h.N):
            y0 = s * h.slice_h
            res = None
            if s in found:
                sl, mvfield, payload = found[s]
                try:
                    res = decode_slice(h, sl, mvfield, payload, refs, y0)
                except (ValueError, IndexError) as e:
                    if verbose:
                        print("frame %d slice %d decode error: %s" % (f, s, e))
                    res = None
            if res is None:
                damaged += 1
                for p in range(3):
                    planes[p][y0:y0 + h.slice_h] = refs[p][y0:y0 + h.slice_h]
                continue
            for p in range(3):
                planes[p][y0:y0 + h.slice_h] = res.recons[p]
                refs[p][y0:y0 + h.slice_h] = res.recons[p]
            if trace is not None and f == trace[0] and s == trace[1]:
                trace_out = res
        dw = h.display_w or W
        dh = h.display_h or H
        for p in range(3):
            pw = widths[p]
            cw = dw if widths[p] == W else dw * pw // W
            img = planes[p][:dh, :cw]
            if h.depth == 8:
                out += img.astype(np.uint8).tobytes()
            else:
                out += img.astype("<u2").tobytes()
    if out_path:
        open(out_path, "wb").write(bytes(out))
    return h, bytes(out), damaged, trace_out

# ---------------------------------------------------------------- CLI

def cmd_header(path):
    data = open(path, "rb").read()
    h = parse_stream_header(data[:32])
    for k in ("magic", "major", "minor", "width", "height", "depth", "chroma",
              "slice_h", "fps_n", "fps_d", "primaries", "transfer", "matrix",
              "full_range", "bits_per_slice", "refresh_r", "scan_type",
              "pixel_flags", "display_w", "display_h", "N", "F"):
        print("%-16s %s" % (k, getattr(h, k)))
    frame0 = data[32:32 + h.F]
    sl = parse_slice_header(frame0[:48], h.minor)
    if sl is None:
        print("slice 0: PARSE FAILED")
        return
    print("--- frame 0 slice 0 header ---")
    for k in ("sync", "fidx8", "slice_idx", "Q", "profile", "blockmv", "n_steps",
              "partial_chunks", "used_bits", "state", "gain"):
        print("%-16s %s" % (k, getattr(sl, k)))
    print("groups          ", sl.groups)
    print("modes           ", sl.mode)
    print("mv              ", sl.mv)
    print("fill            ", sl.fill)
    ok = try_slice_at(h, frame0, 0, 0) is not None
    print("crc             ", "OK" if ok else "MISMATCH")

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    if cmd == "header":
        cmd_header(sys.argv[2])
    elif cmd == "decode":
        h, out, damaged, _ = decode_stream(sys.argv[2], sys.argv[3], verbose=True)
        print("decoded %d bytes, damaged slices: %d" % (len(out), damaged))
        print("sha256:", hashlib.sha256(out).hexdigest())
    elif cmd == "trace":
        f, s = int(sys.argv[3]), int(sys.argv[4])
        prefix = sys.argv[5]
        h, out, damaged, tr = decode_stream(sys.argv[2], None, trace=(f, s))
        if tr is None:
            print("trace slice not decoded")
            return 1
        for p in range(3):
            open("%s.coef.p%d.i32" % (prefix, p), "wb").write(tr.coefs[p].astype("<i4").tobytes())
            open("%s.recon.p%d.u16" % (prefix, p), "wb").write(tr.recons[p].astype("<u2").tobytes())
        print("trace written")
    else:
        print("unknown command", cmd)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
