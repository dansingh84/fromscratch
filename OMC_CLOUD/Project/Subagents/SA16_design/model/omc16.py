# CQP-1 sequence codec model (SA16, 2026-09-28).  numpy, whole frames, real code lengths from static tables.
# One reconstruction path shared by encoder and decoder; pass 1 = rate control on the source (lanes costed at the
# plan each slice will be EMITTED with = its own canonical reading), pass 2 = canonical re-description of the
# reconstruction (= what a generation-2 encoder does).  Code length is monotone under re-description by
# construction: value-based contexts (plan-invariant), tables monotone in |q|, chained hold-plan codes.
import numpy as np, os, pickle
import pyr2
from pyr2 import BANDS, group, rows_per_block, cols_per_unit

# Step ladder from the transform's measured per-coefficient synthesis gains g_b (impulse energy; pyr2, 2026-09-29):
# RD-optimal allocation = equal distortion per coefficient in the gain-normalised domain -> step_b ~ 1/sqrt(g_b).
# x_b = ideal step exponent of band b relative to LL (log2), split into an integer base and a sub-octave offset
# in 30ths; plan P advances one band-octave per 30 units. P = 0 is lossless. Same rule for every plane.
XEXP = {5: {'LL': 0.0, 'H5': 0.98, 'H4': 1.49, 'H3': 2.00, 'LH2': 2.53, 'HL2': 2.47, 'HH2': 3.56, 'LH1': 3.58, 'HL1': 3.52, 'HH1': 4.60},
        4: {'LL': 0.0, 'H4': 1.00, 'H3': 1.50, 'LH2': 2.03, 'HL2': 1.97, 'HH2': 3.06, 'LH1': 3.08, 'HL1': 3.02, 'HH1': 4.10}}
NP = 30; KOFF = 5; PMAX = NP * 12 - 1
HOLD = os.environ.get('HOLD', '0') == '1'   # exact hold of static refresh units: not sound as built (see RESUME bug 12); off
CHROMA_LH = 4
def _bo(pi, band):
    x = XEXP[5 if pi == 0 else CHROMA_LH][band]; base = int(np.floor(x)); off = int(round(NP * (x - base)))
    if off == NP: base += 1; off = 0
    return base, off
ESC = 16; NSYM = 2 * ESC
L_TANS = 1024
DZ = float(os.environ.get('DZ', '0.45'))
OFF = {'fine': 0, 'mid': 1, 'll': 2}
CTX_T = 24                        # value-context threshold in 10-bit codes (scaled by depth)

def expo(pi, band, P):
    base, off = _bo(pi, band); return max(0, (P + off) // NP + base - KOFF)
def pbound(pi, band, e):
    base, off = _bo(pi, band); return NP * (e + KOFF + 1 - base) - 1 - off
def Q(r, D): return (np.sign(r) * np.floor(np.abs(r) / D + DZ)).astype(np.int64)
def eg0_bits(v): return 2 * np.floor(np.log2(np.asarray(v) + 1)).astype(np.int64) + 1
def val2(a):
    a = np.abs(np.asarray(a, np.int64)); low = a & (-a)
    return np.where(a == 0, 60, np.log2(np.maximum(low, 1)).astype(np.int64))
def blockmin(a, r, c): return a.reshape(a.shape[0] // r, r, a.shape[1] // c, c).min(axis=(1, 3))
def blocksum(a, r, c): return a.reshape(a.shape[0] // r, r, a.shape[1] // c, c).sum(axis=(1, 3))

# ---------------------------------------------------------------- static tables (tANS-quantised, monotone in |q|)
class Tables:
    def __init__(self, path=None):
        self.len = {}; self.cnt = {}; self.training = False; self.ok = False; self.comb = {}
        if path and os.path.exists(path): self.len = pickle.load(open(path, 'rb')); self.ok = True
    def length(self, key, nsym):
        if key in self.len: return self.len[key]
        if nsym == NSYM:
            ctx = key[2] if len(key) == 3 else 2
            p0 = [0.93, 0.85, 0.7, 0.9, 0.8, 0.6, 0.9, 0.9, 0.9][ctx]; tail = [0.45, 0.55, 0.65, 0.5, 0.6, 0.7, 0.55, 0.55, 0.55][ctx]
            q = np.arange(nsym) - ESC; p = tail ** np.abs(q); p[ESC] = 0; p = p / p.sum() * (1 - p0); p[ESC] = p0; p[0] = 0.002
        elif key[0] == 'sig': p = np.array([0.85, 0.15]) if key[3] < 2 or key[3] == 6 else np.array([0.6, 0.4])
        else: q = np.arange(nsym) - nsym // 2; p = 0.7 ** np.abs(q)
        p = p / p.sum(); return -np.log2(np.maximum(p, 1e-6))
    def combined(self, pc, band):
        key = (pc, band)
        if key not in self.comb: self.comb[key] = np.stack([self.length((pc, band, k), NSYM) for k in range(9)])
        return self.comb[key]
    def lenmap2(self, pc, band, idx, sym):
        ln = self.combined(pc, band)[idx, sym]
        if self.training:
            c = self.cnt.setdefault((pc, band), np.zeros((9, NSYM), np.int64)); np.add.at(c, (idx.ravel(), sym.ravel()), 1)
        return ln
    def lenmap(self, key, nsym, sym):
        ln = self.length(key, nsym)
        if self.training:
            c = self.cnt.setdefault(key, np.zeros(nsym, np.int64)); np.add.at(c, sym.ravel(), 1)
        return ln[sym]
    @staticmethod
    def quantise(c, monotone):
        n = c.size; p = (c + 0.5) / (c.sum() + 0.5 * n)
        f = np.maximum(1, np.round(p * L_TANS)).astype(np.int64)
        if monotone:
            for sgn in (1, -1):
                for k in range(1, ESC):
                    s = ESC + sgn * k; s0 = ESC + sgn * (k - 1); f[s] = min(f[s], f[s0])
            f[0] = min(f[0], f[1], f[2 * ESC - 1])
        while f.sum() > L_TANS: f[np.argmax(f)] -= 1
        while f.sum() < L_TANS: f[ESC if monotone else np.argmax(p / f)] += 1
        return -np.log2(f / L_TANS)
    def build(self, path):
        out = {}
        for key, c in self.cnt.items():
            if len(key) == 2 and c.ndim == 2:
                for i in range(9): out[(key[0], key[1], i)] = self.quantise(c[i], True)
            else: out[key] = self.quantise(c, False)
        self.len = out; self.comb = {}; pickle.dump(out, open(path, 'wb')); self.ok = True

def symbolise(q):
    a = np.abs(q); esc = a >= ESC
    s = np.where(esc, 0, np.clip(q, -ESC + 1, ESC - 1) + ESC).astype(np.int64)
    extra = np.where(esc, eg0_bits(np.maximum(a - ESC, 0)) + 1, 0)
    return s, extra
NCTX = 6   # inter: 3 prediction-magnitude classes x 2 vector classes (rows 0..5); intra: 3 LL-brightness classes (rows 6..8)
def tile_of(pc, band):
    Lh = 5 if pc == 0 else CHROMA_LH
    return rows_per_block(band), cols_per_unit(band, Lh)
def bits_map(tabs, pc, band, q, ctx):
    """per-coefficient code-length map. Coding = one significance flag per (unit, band) tile (context = the tile's
    maximum coefficient context, plan-invariant) + the coefficient symbols inside significant tiles only.
    ctx: per-coefficient context row index (0..8), identical at every generation."""
    r, c = tile_of(pc, band); R, C = q.shape[0] // r, q.shape[1] // c
    qt = q.reshape(R, r, C, c); sig = (qt != 0).any(axis=(1, 3))
    ct = ctx.reshape(R, r, C, c).max(axis=(1, 3))
    fl = np.zeros((R, C), np.float64)
    for k in range(9):
        m = ct == k
        if m.any(): fl[m] = tabs.lenmap(('sig', pc, band, k), 2, sig[m].astype(np.int64))
    s, extra = symbolise(q)
    sym = (extra + tabs.lenmap2(pc, band, ctx, s)) * np.repeat(np.repeat(sig, r, 0), c, 1)
    out = sym.astype(np.float64); out[::r, ::c] += fl
    return out

# ---------------------------------------------------------------- motion
def clipidx(a, n): return np.clip(a, 0, n - 1)
def search(ref, ref2, S, BW=64):
    H, W = ref.shape; nby, nbx = H // S, W // BW
    ys = np.arange(0, H, 2); xs = np.arange(0, W, 2); A = ref[ys][:, xs]
    cands = [(0, 0)] + [(dy, dx) for dy in range(-16, 17, 4) for dx in range(-32, 33, 4) if (dy, dx) != (0, 0)]
    best = np.full((nby, nbx), np.iinfo(np.int64).max); V = np.zeros((nby, nbx, 2), np.int64)
    for (dy, dx) in cands:
        B = ref2[clipidx(ys[:, None] + dy, H), clipidx(xs[None, :] + dx, W)]
        s = np.abs(A - B).reshape(nby, S // 2, nbx, BW // 2).sum(axis=(1, 3)); m = s < best; best[m] = s[m]; V[m] = (dy, dx)
    for step in (2, 1):
        base = V.copy()
        for ddy in (-step, 0, step):
            for ddx in (-step, 0, step):
                if ddy == 0 and ddx == 0: continue
                vy = base[..., 0] + ddy; vx = base[..., 1] + ddx
                VY = np.repeat(np.repeat(vy, S // 2, 0), BW // 2, 1); VX = np.repeat(np.repeat(vx, S // 2, 0), BW // 2, 1)
                B = ref2[clipidx(ys[:, None] + VY, H), clipidx(xs[None, :] + VX, W)]
                s = np.abs(A - B).reshape(nby, S // 2, nbx, BW // 2).sum(axis=(1, 3))
                ok = (np.abs(vy) <= 16) & (np.abs(vx) <= 32) & (s < best)
                best[ok] = s[ok]; V[ok, 0] = vy[ok]; V[ok, 1] = vx[ok]
    return V
def obmc(ref, V, S, BW, barrier=None):
    H, W = ref.shape; nby, nbx = V.shape[:2]
    y = np.arange(H)[:, None]; x = np.arange(W)[None, :]
    by0 = (y - S // 2) // S; fy = (y - S // 2) - S * by0; bx0 = (x - BW // 2) // BW; fx = (x - BW // 2) - BW * bx0
    acc = np.zeros((H, W), np.int64)
    for (oy, wy) in ((0, S - fy), (1, fy)):
        for (ox, wx) in ((0, BW - fx), (1, fx)):
            by = clipidx(by0 + oy, nby); bx = clipidx(bx0 + ox, nbx)
            yy = clipidx(y + V[by, bx, 0], H); xx = clipidx(x + V[by, bx, 1], W)
            if barrier is not None: xx = np.minimum(xx, barrier[None, :])
            acc += wy * wx * ref[yy, xx]
    return (acc + (S * BW) // 2) // (S * BW)

# ---------------------------------------------------------------- codec
class Codec:
    def __init__(self, W, H, fmt=422, depth=10, S=8, bpp=0.5, tabs=None, Nc=8, refresh=True, legal=True):
        self.W, self.H, self.fmt, self.depth, self.S, self.bpp = W, H, fmt, depth, S, bpp
        self.lo, self.hi = 0, (1 << depth) - 1; self.T = max(1, CTX_T * (1 << depth) // 1024)
        self.tabs = tabs or Tables(); self.Nc = Nc; self.refresh = refresh; self.legal = legal
        self.B = S // 4; self.NS = H // S; self.nblk = H // 4
        self.sub = 2 if fmt in (422, 420) else 1
        self.Lh = [5, 5 if self.sub == 1 else 4, 5 if self.sub == 1 else 4]
        global CHROMA_LH; CHROMA_LH = self.Lh[1]
        self.U = W // 32; self.Bw = -(-self.U // Nc); self.BWm = 64; self.nbx = W // self.BWm; self.nby = H // S
        self.F = int(round(bpp * W * H)); self.ref = None; self.ref2 = None; self.t = 0; self.stats = {}
        sets = np.zeros(self.NS, np.int64)
        for b in range(self.nblk):
            for off in (0, 1, 2): sets[max(0, b - off) // self.B] += 1
        self.share = sets / sets.sum()
        self.carrier = {g: np.array([max(0, b - OFF[g]) // self.B for b in range(self.nblk)]) for g in OFF}
        self.canon = False; self.BND = None
    def ucols(self, pi, band): return cols_per_unit(band, self.Lh[pi])
    def step(self, pi, band, P): return 1 << expo(pi, band, P)
    def steps_arr(self, pi, band, Parr):
        base, off = _bo(pi, band); Parr = np.asarray(Parr, np.int64); return (1 << np.maximum(0, (Parr + off) // NP + base - KOFF)).astype(np.int64)
    def rawbits(self, D): return int(np.ceil(np.log2(-(-self.hi // D) + 1)))
    def rows_of(self, band, k):
        bs = np.where(self.carrier[group(band)] == k)[0]; r = rows_per_block(band)
        return bs, (np.concatenate([np.arange(r * b, r * b + r) for b in bs]) if bs.size else np.zeros(0, np.int64))
    # ---- frame-level preparation
    def prepare(self, V, intra_frame, phi, ref=None):
        ref = self.ref if ref is None else ref; S, W = self.S, self.W
        ucls = np.zeros(self.U, np.int64); clean_units = 0
        if self.refresh and not intra_frame:
            a, b = phi * self.Bw, min(self.U, (phi + 1) * self.Bw); ucls[a:b] = 1
            if b < self.U: ucls[b] = 1
            if b + 1 < self.U: ucls[b + 1] = 2
            clean_units = phi * self.Bw
        xp = []; Tp = []
        for pi in range(3):
            if intra_frame: xp.append(None); Tp.append(None); continue
            sub = 1 if pi == 0 else self.sub; Vp = V.copy()
            if sub == 2: Vp[..., 1] = Vp[..., 1] >> 1
            Wp = W // sub; barrier = None
            if clean_units > 0:
                lim = clean_units * (32 // sub); barrier = np.where(np.arange(Wp) < lim, lim - 1, Wp - 1)
            p = obmc(ref[pi], Vp, S, self.BWm // sub, barrier); xp.append(p); T = pyr2.analysis(p, self.Lh[pi])
            if clean_units > 0:
                # clean units take their prediction coefficients from a barrier-consistent picture: columns beyond the
                # barrier replicated from the last clean column, so no two-sided read inside T(x_p) crosses it
                pc_ = p.copy(); pc_[:, lim:] = p[:, lim - 1:lim]; Tc = pyr2.analysis(pc_, self.Lh[pi])
                for band in BANDS(self.Lh[pi]):
                    c = self.ucols(pi, band); ncl = clean_units * c
                    T[band][:, :ncl] = Tc[band][:, :ncl]
            Tp.append(T)
        static = np.zeros((self.nblk, self.U), bool)
        if not intra_frame:
            nz = (V != 0).any(-1).astype(np.int64)
            cs = np.zeros((self.nby + 1, self.nbx + 1), np.int64); cs[1:, 1:] = nz.cumsum(0).cumsum(1)
            bb = np.arange(self.nblk); r0 = np.clip((4 * bb - S // 2) // S, 0, self.nby - 1); r1 = np.clip((4 * bb + 3 - S // 2) // S + 1, 0, self.nby - 1)
            uu = np.arange(self.U); c0 = np.clip((32 * uu - 32) // 64, 0, self.nbx - 1); c1 = np.clip((32 * uu + 31 - 32) // 64 + 1, 0, self.nbx - 1)
            R0, C0 = np.meshgrid(r0, c0, indexing='ij'); R1, C1 = np.meshgrid(r1, c1, indexing='ij')
            static = (cs[R1 + 1, C1 + 1] - cs[R0, C1 + 1] - cs[R1 + 1, C0] + cs[R0, C0]) == 0
        return ucls, xp, Tp, static
    def boundary_masks(self, T):
        """(up, lo) masks per plane/band: value on its own legal interval boundary."""
        UP = []; LO = []
        for pi in range(3):
            _, F, IV = pyr2.synthesis(T[pi], self.Lh[pi], self.lo, self.hi)
            UP.append({b: T[pi][b] == IV[b][1] for b in BANDS(self.Lh[pi])}); LO.append({b: T[pi][b] == IV[b][0] for b in BANDS(self.Lh[pi])})
        return UP, LO
    def vof(self, pi, band, rows, a, M=None):
        """2-adic valuation with boundary values counted as reproducible at any plan (M = (UP, LO) masks)."""
        v = val2(a)
        if M is not None and self.legal: v = np.where(M[0][pi][band][rows] | M[1][pi][band][rows], 60, v)
        return v
    def quant(self, pi, band, rows, x, base, D, raw=False, M=None):
        """index of x against base at step D; canonical (smallest reaching) index on interval boundaries when M given."""
        t = x - base; q = np.clip((t + D // 2) // D, 0, -(-self.hi // D)) if raw else Q(t, D)
        if M is not None and self.legal:
            up = M[0][pi][band][rows]; lo = M[1][pi][band][rows]
            q = np.where(up, np.maximum(0, np.ceil(t / D).astype(np.int64)), q)
            q = np.where(lo & ~up, np.minimum(0, np.floor(t / D).astype(np.int64)), q)
            q = np.where(up & lo, 0, q)          # degenerate interval: every index reproduces, canonical = 0
        return q
    # ---- plan-invariant contexts (frame level): inter from |c_p| class x vector class; intra from the LL value
    def contexts(self, Tp, V, intra_frame):
        T1, T2 = 8 * self.hi // 1023, 32 * self.hi // 1023
        cx = []
        for pi in range(3):
            d = {}
            for band in BANDS(self.Lh[pi]):
                if intra_frame: d[band] = None; continue
                a = np.abs(Tp[pi][band]); cls = np.where(a < T1, 0, np.where(a < T2, 1, 2))
                d[band] = cls if band != 'LL' else np.zeros(a.shape, np.int64)
            cx.append(d)
        # vector class per unit: any nonzero vector among the contributing motion blocks
        vc = None
        if not intra_frame:
            nz = (V != 0).any(-1).astype(np.int64); S = self.S
            cs = np.zeros((self.nby + 1, self.nbx + 1), np.int64); cs[1:, 1:] = nz.cumsum(0).cumsum(1)
            bb = np.arange(self.nblk); r0 = np.clip((4 * bb - S // 2) // S, 0, self.nby - 1); r1 = np.clip((4 * bb + 3 - S // 2) // S + 1, 0, self.nby - 1)
            uu = np.arange(self.U); c0 = np.clip((32 * uu - 32) // 64, 0, self.nbx - 1); c1 = np.clip((32 * uu + 31 - 32) // 64 + 1, 0, self.nbx - 1)
            R0, C0 = np.meshgrid(r0, c0, indexing='ij'); R1, C1 = np.meshgrid(r1, c1, indexing='ij')
            vc = ((cs[R1 + 1, C1 + 1] - cs[R0, C1 + 1] - cs[R1 + 1, C0] + cs[R0, C0]) > 0).astype(np.int64)
        return cx, vc
    def ctx_rows(self, pi, band, rows, cx, vc, inter, llval):
        """context row per coefficient: inter -> cp class + 3*vector class (0..5); intra -> 6 + LL brightness class."""
        r = rows_per_block(band); c = self.ucols(pi, band); bs = rows[::r] // r
        lcls = np.where(llval < self.hi // 4, 0, np.where(llval < self.hi // 2, 1, 2))          # per unit (len(bs), U)
        intra_ctx = 6 + np.repeat(np.repeat(lcls, r, 0), c, 1)
        if cx[pi][band] is None: return intra_ctx
        inter_ctx = cx[pi][band][rows] + 3 * np.repeat(np.repeat(vc[bs], r, 0), c, 1)
        return np.where(inter, inter_ctx, intra_ctx)
    # ---- reading: coarsest plan reproducing the (non-hold) content carried by slice k, from the input picture
    def reading_plan(self, Ts, Tp, k, intra_frame, ucls, holdg, mode, M, explain=False):
        """coarsest plan at which every carried unit reproduces in its (fixed, or for new units: some) mode.
        Units the lane will hold (static band units whose group residual is exactly zero) are excluded."""
        Pbest = PMAX; any_ = False; newb = np.where(self.carrier['ll'] == k)[0]
        Pi_u = np.full((self.nblk, self.U), PMAX, np.int64); Pr_u = np.full((self.nblk, self.U), PMAX, np.int64)
        hm = {}
        if not intra_frame:
            for g in ('ll', 'mid', 'fine'):
                bs = np.where(self.carrier[g] == k)[0]
                if not bs.size: continue
                z = np.ones((len(bs), self.U), bool)
                for pi in range(3):
                    for band in BANDS(self.Lh[pi]):
                        if group(band) != g: continue
                        r = rows_per_block(band); c = self.ucols(pi, band); rows = np.concatenate([np.arange(r * b, r * b + r) for b in bs])
                        z &= blockmin((Ts[pi][band][rows] == Tp[pi][band][rows]).astype(np.int64), r, c).astype(bool)
                Pref = self._Pe[k - 1] if k > 0 else PMAX
                hm[g] = (ucls == 1)[None, :] & self._static[bs] & z & (self._PuP[bs] >= Pref)
        worst = None
        for pi in range(3):
            for band in BANDS(self.Lh[pi]):
                bs, rows = self.rows_of(band, k)
                if not bs.size: continue
                r = rows_per_block(band); c = self.ucols(pi, band); x = Ts[pi][band][rows]
                if intra_frame: v = self.vof(pi, band, rows, x, M)
                else:
                    xp = Tp[pi][band][rows]; vi = self.vof(pi, band, rows, x, M); vr = self.vof(pi, band, rows, x - xp, M)
                    ucl = np.repeat(np.repeat(ucls[None, :], x.shape[0], 0), c, 1); hd = np.repeat(np.repeat(hm[group(band)], r, 0), c, 1)
                    nw = np.repeat(np.isin(bs, newb), r)[:, None]; md = np.repeat(np.repeat(mode[bs], r, 0), c, 1)
                    v = np.where(md == 1, vr, vi); v = np.where(ucl == 1, vi, v)
                    if band == 'LL': v = np.where(ucl == 2, vi, v); vr = np.where(ucl == 2, vi, vr)
                    v = np.where(hd, 60, v); vi = np.where(hd, 60, vi); vr = np.where(hd, 60, vr)
                    nwb = np.isin(bs, newb)
                    if nwb.any():
                        sel = np.repeat(nwb, r); bb = bs[nwb]
                        Pi_u[bb] = np.minimum(Pi_u[bb], pbound(pi, band, blockmin(vi[sel], r, c)))
                        Pr_u[bb] = np.minimum(Pr_u[bb], pbound(pi, band, blockmin(np.where(ucl == 1, vi, vr)[sel], r, c)))
                        v = np.where(sel[:, None], 60, v)
                if v.size == 0: continue
                any_ = True; pb = pbound(pi, band, int(v.min()))
                if pb < Pbest: Pbest = pb; i, j = np.unravel_index(int(v.argmin()), v.shape); worst = (pi, band, int(v.min()), i, j, int(x[i, j]), int(Tp[pi][band][rows][i, j]) if not intra_frame else None, int(ucls[j // c]), int(mode[bs[i // r], j // c]))
        if len(newb) and not intra_frame:
            pu = int(np.maximum(Pi_u[newb], Pr_u[newb]).min())
            if pu < Pbest: Pbest = pu; worst = ('new-unit', int(np.argmin(np.maximum(Pi_u[newb], Pr_u[newb]))))
        if explain: print('     reading limited by', worst)
        return max(0, min(PMAX, Pbest)) if any_ else None
    def unit_plan(self, T, bs, M):
        """coarsest intra-reproducing plan of every unit of blocks bs, from the values T with masks M."""
        Pm = np.full((len(bs), self.U), PMAX, np.int64)
        for pi in range(3):
            for band in BANDS(self.Lh[pi]):
                if band == 'LL': continue          # the LL of a held unit travels at full precision
                r = rows_per_block(band); c = self.ucols(pi, band)
                rows = np.concatenate([np.arange(r * b, r * b + r) for b in bs]); x = T[pi][band][rows]
                Pm = np.minimum(Pm, pbound(pi, band, blockmin(self.vof(pi, band, rows, x, M), r, c)))
        return np.clip(Pm, 0, PMAX)
    # ---- intra LL: value-domain DPCM from the left unit's final LL (row start: the block above's final LL, or mid-grey)
    def ll_chain(self, x, base_inter, use_inter, hold_val, use_hold, D, above):
        """x, base_inter, hold_val: (nb, U). Intra units: absolute index idx = round(pred/D) + q, final = clip(D*idx);
        inter: clip(base + D*q); hold: the exact held value. Row start predictor = the block above's first final."""
        nb, U = x.shape; q = np.zeros((nb, U), np.int64); fin = np.zeros((nb, U), np.int64)
        mid = (self.lo + self.hi + 1) // 2; top = int(np.asarray(above).ravel()[0]) if above is not None else mid
        for i in range(nb):
            for u in range(U):
                pred = fin[i, u - 1] if u > 0 else (fin[i - 1, 0] if i > 0 else top)
                if use_inter[i, u]:
                    q[i, u] = Q(x[i, u] - base_inter[i, u], D); fin[i, u] = min(self.hi, max(self.lo, base_inter[i, u] + D * q[i, u]))
                elif use_hold[i, u]:
                    q[i, u] = hold_val[i, u] - pred; fin[i, u] = hold_val[i, u]
                else:
                    pidx = (pred + D // 2) // D; idx = (x[i, u] + D // 2) // D
                    q[i, u] = idx - pidx; fin[i, u] = min(self.hi, max(self.lo, D * (pidx + q[i, u])))
        return q, fin
    def ll_bits(self, pc, q, use_inter, use_hold, ctxm):
        """LL symbol bits: table-coded (inter and intra index residuals), hold residual = signed EG0 at step 1."""
        b = bits_map(self.tabs, pc, 'LL', np.where(use_hold, 0, q), ctxm)
        return np.where(use_hold, eg0_bits(np.abs(q)) + 1, b)
    def ll_pred(self, fin_row, above):
        """DPCM predictor per unit from a row of final LL values (for reading / emission)."""
        mid = (self.lo + self.hi + 1) // 2; p = np.empty_like(fin_row); p[:, 1:] = fin_row[:, :-1]
        p[:, 0] = int(np.asarray(above).ravel()[0]) if above is not None else mid; return p
    # ---- hold target of a reference unit: its values, boundary ones replaced by the reaching lattice value at Dq
    def hold_target(self, pi, band, rows, xp, Dq, MP):
        if MP is None: return xp
        up = MP[0][pi][band][rows]; lo = MP[1][pi][band][rows]
        t = np.where(up, Dq * np.maximum(0, np.ceil(xp / Dq).astype(np.int64)), np.where(lo, Dq * np.minimum(0, np.floor(xp / Dq).astype(np.int64)), xp))
        return t
    # ---- one open-loop lane: exact symbol bits of slice k at plan P + conservative flag bits (no coding, no clamp)
    def lane(self, Ts, Tp, k, P, intra_frame, ucls, V, st, cx, vc, Mq):
        mode, Pk, MP, PuP, static = st['mode'], st['Pk'], st['MP'], st['PuP'], st['static']
        newb = np.where(self.carrier['ll'] == k)[0]; nb = len(newb); Pk[k] = P
        mode_l = mode.copy()
        if not intra_frame and nb:
            ci = np.zeros((nb, self.U)); cr = np.zeros((nb, self.U)); rep_i = np.ones((nb, self.U), bool); rep_r = np.ones((nb, self.U), bool); xlat = np.ones((nb, self.U), bool)
            for pi in range(3):
                pc = 0 if pi == 0 else 1
                for band in BANDS(self.Lh[pi]):
                    r = rows_per_block(band); c = self.ucols(pi, band); D = self.step(pi, band, P); e = expo(pi, band, P)
                    rows = np.concatenate([np.arange(r * b, r * b + r) for b in newb]); x = Ts[pi][band][rows]; xp = Tp[pi][band][rows]
                    if band == 'LL':
                        above = Ts[pi]['LL'][newb[0] - 1] if newb[0] > 0 else None
                        pr = np.empty_like(x)
                        for i in range(nb): pr[i] = self.ll_pred(x[i:i + 1], above)[0]; above = x[i]
                        qi = (x + D // 2) // D - (pr + D // 2) // D; llv_new = blockmin(np.clip(D * ((x + D // 2) // D), self.lo, self.hi), r, c)
                        bi = bits_map(self.tabs, pc, band, qi, self.ctx_rows(pi, band, rows, cx, vc, np.zeros(x.shape, bool), np.clip(pr, self.lo, self.hi)))
                    else:
                        qi = self.quant(pi, band, rows, x, 0, D, M=Mq)
                        bi = bits_map(self.tabs, pc, band, qi, self.ctx_rows(pi, band, rows, cx, vc, np.zeros(x.shape, bool), llv_new))
                    ci += blocksum(bi, r, c)
                    qr = self.quant(pi, band, rows, x, xp, D, M=Mq)
                    br = bits_map(self.tabs, pc, band, qr, self.ctx_rows(pi, band, rows, cx, vc, np.ones(x.shape, bool), llv_new))
                    vr_ = self.vof(pi, band, rows, x - xp, Mq); xl = val2(xp) >= e
                    if band == 'LL':
                        llx = np.repeat(np.repeat((ucls == 2)[None, :], nb * r, 0), c, 1); br = np.where(llx, bi, br); vr_ = np.where(llx, self.vof(pi, band, rows, x, Mq), vr_); xl = xl | llx
                    cr += blocksum(br, r, c)
                    if group(band) == 'll':
                        rep_i &= blockmin(self.vof(pi, band, rows, x, Mq), r, c) >= e; rep_r &= blockmin(vr_, r, c) >= e
                        xlat &= blockmin(xl.astype(np.int64), r, c).astype(bool)
            ci += self.tabs.length(('mode',), 2)[0]; cr += self.tabs.length(('mode',), 2)[1]
            for i, b in enumerate(newb):
                prefer_r = rep_r[i] | (~rep_i[i] & ((cr[i] <= ci[i]) | xlat[i]))
                mode_l[b] = np.where(ucls == 1, 0, prefer_r.astype(np.int64))
        # pass 1: residual indices of every carried band; per (group, block, unit): all-zero residual -> lane hold
        tot = 80.0 + (self.vector_bits(V, k) if not intra_frame else 0.0); self._lane_bb = {}
        pre = {}; zr = {}
        for pi in range(3):
            for band in BANDS(self.Lh[pi]):
                bs, rows = self.rows_of(band, k)
                if not bs.size: continue
                r = rows_per_block(band); c = self.ucols(pi, band); D = self.step(pi, band, P); x = Ts[pi][band][rows]
                if intra_frame: continue
                xp = Tp[pi][band][rows]; qr = self.quant(pi, band, rows, x, xp, D, M=Mq); pre[(pi, band)] = qr
                g = group(band); z = blockmin((qr == 0).astype(np.int64), r, c).astype(bool)
                zr[g] = z if g not in zr else (zr[g] & z)
        holdg = {}
        if not intra_frame:
            Pref = st['Pe'][k - 1] if k > 0 else PMAX
            for g in zr:
                bs = np.where(self.carrier[g] == k)[0]
                holdg[g] = (ucls == 1)[None, :] & static[bs] & zr[g] & (PuP[bs] >= Pref) & HOLD
        Qv = []; Cv = []
        for pi in range(3):
            pc = 0 if pi == 0 else 1; Qp = {}; Cp = {}
            for band in BANDS(self.Lh[pi]):
                bs, rows = self.rows_of(band, k)
                if not bs.size: Qp[band] = None; Cp[band] = None; continue
                r = rows_per_block(band); c = self.ucols(pi, band); D = self.step(pi, band, P); x = Ts[pi][band][rows]
                skip = (P == PMAX)     # the floor plan: no symbol stream, every non-LL index is 0 by definition
                if band == 'LL':
                    above = st['Fc'][pi]['LL'][bs[0] - 1] if bs[0] > 0 else None
                    if intra_frame:
                        use_inter = np.zeros(x.shape, bool); use_hold = np.zeros(x.shape, bool); base_i = np.zeros_like(x); hv = np.zeros_like(x)
                    else:
                        xp = Tp[pi][band][rows]; mdx = mode_l[bs]; hdx = holdg['ll']
                        use_inter = (mdx == 1) & ~(ucls == 2)[None, :] & ~hdx; use_hold = hdx; base_i = xp
                        Dq = self.steps_arr(pi, band, PuP[bs]) * np.ones((1, self.U), np.int64) if hdx.any() else D * np.ones(x.shape, np.int64)
                        hv = np.clip(self.hold_target(pi, band, rows, xp, np.where(hdx, Dq, D), MP), self.lo, self.hi) if hdx.any() else np.zeros_like(x)
                    q, fin = self.ll_chain(x, base_i, use_inter, hv, use_hold, D, above)
                    if skip: q = np.where(use_inter, 0, q); fin = np.where(use_inter, np.clip(base_i, self.lo, self.hi), fin)
                    pr = np.empty_like(fin); ab = above
                    for i in range(fin.shape[0]): pr[i] = self.ll_pred(fin[i:i + 1], ab)[0]; ab = fin[i]
                    self.llu[pi][bs] = fin
                    ctxm = self.ctx_rows(pi, band, rows, cx, vc, use_inter, np.clip(pr, self.lo, self.hi))
                    bl = self.ll_bits(pc, q, use_inter, use_hold, ctxm)
                    tot += bl.sum() if not skip else bl[~use_inter].sum()
                    self._lane_bb[(pi, band)] = float(bl.sum() if not skip else bl[~use_inter].sum())
                    if os.environ.get('DBG_SLICE') and k == int(os.environ['DBG_SLICE']): self._lane_dbg = getattr(self, '_lane_dbg', {}); self._lane_dbg.setdefault((P, pi, band), (q.copy(), ctxm.copy(), use_inter.copy(), use_hold.copy(), bl.copy()))
                    Qp[band] = q; Cp[band] = fin; continue
                if intra_frame:
                    q = self.quant(pi, band, rows, x, 0, D, M=Mq)
                    if skip: q = np.zeros_like(q)
                    val = D * q; t0_ = tot; ctxm = self.ctx_rows(pi, band, rows, cx, vc, np.zeros(x.shape, bool), self.llu[pi][bs])
                    bl = None if skip else bits_map(self.tabs, pc, band, q, ctxm); tot += 0 if skip else bl.sum()
                    self._lane_bb[(pi, band)] = tot - t0_
                    if os.environ.get('DBG_SLICE') and k == int(os.environ['DBG_SLICE']) and bl is not None: self._lane_dbg = getattr(self, '_lane_dbg', {}); self._lane_dbg.setdefault((P, pi, band), (q.copy(), ctxm.copy(), np.zeros(x.shape, bool), np.zeros(x.shape, bool), bl.copy()))
                    Qp[band] = q; Cp[band] = val; continue
                xp = Tp[pi][band][rows]; g = group(band)
                mdx = np.repeat(np.repeat(mode_l[bs], r, 0), c, 1); hdx = np.repeat(np.repeat(holdg[g], r, 0), c, 1)
                llx = np.repeat(np.repeat((ucls == 2)[None, :], x.shape[0], 0), c, 1) if band == 'LL' else np.zeros(x.shape, bool)
                inter = (mdx == 1) & ~llx & ~hdx
                Dq = D * np.ones(x.shape, np.int64)
                if hdx.any():
                    pux = np.repeat(np.repeat(PuP[bs], r, 0), c, 1)
                    for p_ in np.unique(pux[hdx]): Dq = np.where(hdx & (pux == p_), self.step(pi, band, int(p_)), Dq)
                qr = pre[(pi, band)]; qi = self.quant(pi, band, rows, x, 0, D, raw=(band == 'LL'), M=Mq)
                th = self.hold_target(pi, band, rows, xp, Dq, MP) if hdx.any() else np.zeros(x.shape, np.int64)
                q = np.where(inter, qr, np.where(hdx, th // Dq, qi))
                if skip: q = np.where(hdx, q, np.where(inter | (band != 'LL'), 0, q))
                val = np.where(inter, xp, 0) + Dq * q
                # reservation: a static band unit coded fresh may be held at emission (finals == reference): add the
                # excess of its hold symbols over its fresh symbols, per unit
                sb = np.repeat(np.repeat(((ucls == 1)[None, :] & static[bs] & ~holdg[g]), r, 0), c, 1)
                if sb.any() and HOLD:
                    Dq2 = np.repeat(np.repeat(self.steps_arr(pi, band, PuP[bs]), r, 0), c, 1)
                    qh2 = self.hold_target(pi, band, rows, xp, Dq2, MP) // Dq2
                    ctx2 = self.ctx_rows(pi, band, rows, cx, vc, np.zeros(x.shape, bool), self.llu[pi][bs])
                    bh = blocksum(bits_map(self.tabs, pc, band, np.where(sb, qh2, 0), ctx2) * sb, r, c); bf = blocksum(bits_map(self.tabs, pc, band, np.where(sb, qi, 0), ctx2) * sb, r, c)
                    tot += float(np.maximum(0.0, bh - bf).sum())
                t0_ = tot; ctxm = self.ctx_rows(pi, band, rows, cx, vc, inter, self.llu[pi][bs])
                if not skip:
                    bl = bits_map(self.tabs, pc, band, q, ctxm); tot += bl.sum()
                    if os.environ.get('DBG_SLICE') and k == int(os.environ['DBG_SLICE']): self._lane_dbg = getattr(self, '_lane_dbg', {}); self._lane_dbg.setdefault((P, pi, band), (q.copy(), ctxm.copy(), inter.copy(), hdx.copy(), bl.copy()))
                elif hdx.any(): tot += bits_map(self.tabs, pc, band, np.where(hdx, q, 0), ctxm)[hdx].sum()
                self._lane_bb[(pi, band)] = tot - t0_
                Qp[band] = q; Cp[band] = val
            Qv.append(Qp); Cv.append(Cp)
        self._flagdbg = {}; t_pre = tot
        if not intra_frame:
            for g in ('ll', 'mid', 'fine'):
                bsg = np.where(self.carrier[g] == k)[0]
                if not bsg.size: continue
                b1m = (ucls == 1)[None, :].repeat(len(bsg), 0); hb = holdg[g]
                tot += self.tabs.lenmap(('hold',), 2, hb[b1m].astype(np.int64)).sum() if b1m.any() else 0.0
                if g == 'll': first = hb & b1m
                elif g == 'mid': first = hb & b1m & ~st['holdg']['ll'][bsg]
                else: first = hb & b1m & ~st['holdg']['ll'][bsg] & ~st['holdg']['mid'][bsg]
                hp = PuP[bsg][first]
                if hp.size: tot += eg0_bits(PMAX - hp).sum()
                self._flagdbg[g] = (int(hb.sum()), int(first.sum()), float(eg0_bits(PMAX - hp).sum() if hp.size else 0))
            if nb:
                b1m = (ucls == 1)[None, :].repeat(nb, 0); mb = mode_l[newb]
                tot += self.tabs.lenmap(('mode',), 2, mb[~b1m]).sum() if (~b1m).any() else 0.0
        hdr_ = 80.0 + (self.vector_bits(V, k) if not intra_frame else 0.0); fl_ = tot - t_pre
        if abs(tot - (hdr_ + sum(self._lane_bb.values()) + fl_)) > 1e-3 and os.environ.get('DBG_EST'): print('   LANE hidden term %.1f' % (tot - (hdr_ + sum(self._lane_bb.values()) + fl_)))
        return dict(bits=float(tot), Q=Qv, C=Cv, mode=mode_l, holdg=holdg, bb=dict(self._lane_bb), hdr=hdr_, flags=fl_, flagdbg=dict(self._flagdbg))
    # ---- the one closed-loop synthesis of the slice + canonical emission from final values (= what gen 2 reads)
    def window(self, k):
        m = 5 if pyr2.HH_TWO else 3
        return max(0, self.B * k - m), min(self.nblk, self.B * k + self.B + m)
    def finalize(self, Ts, Tp, k, P, res, intra_frame, ucls, V, st, cx, vc):
        Fc, mode, Pk, MP, PuP, static, holdc, Puc = st['Fc'], st['mode'], st['Pk'], st['MP'], st['PuP'], st['static'], st['holdg'], st['Pu']
        b0, b1 = self.window(k); newb = np.where(self.carrier['ll'] == k)[0]; nb = len(newb)
        mode_l = res['mode']
        C = []; M = []
        for pi in range(3):
            Cw = {}; Mw = {}
            for band in BANDS(self.Lh[pi]):
                r = rows_per_block(band); c = self.ucols(pi, band); car = self.carrier[group(band)]
                rows = np.arange(r * b0, r * b1); carr = np.repeat(car[b0:b1], r); cur = carr == k; done = carr < k
                Cv = np.zeros((rows.size, Ts[pi][band].shape[1]), np.int64)
                if cur.any():
                    bs_, rr = self.rows_of(band, k); Cv[np.isin(rows, rr)] = res['C'][pi][band]
                Cw[band] = np.where(cur[:, None], Cv, np.where(done[:, None], Fc[pi][band][rows], 0))
                Mw[band] = dict(rows=rows, cur=cur, r=r, c=c)
            C.append(Cw); M.append(Mw)
        F = []; IV = []
        for pi in range(3):
            _, Fw, IVw = pyr2.synthesis(C[pi], self.Lh[pi], self.lo, self.hi, b0) if self.legal else synth_clip(C[pi], self.Lh[pi], self.lo, self.hi, b0)
            F.append(Fw); IV.append(IVw)
        bnd = lambda pi, band, sel: (F[pi][band][sel] == IV[pi][band][0][sel]) | (F[pi][band][sel] == IV[pi][band][1][sel])
        # --- holds decided from FINALS (identical at every generation): static band unit whose group finals equal
        #     the clamped hold target of the reference unit
        holdg_e = {g: v.copy() for g, v in holdc.items()}; Pu_e = Puc.copy()
        if not intra_frame:
            for g in ('ll', 'mid', 'fine'):
                bs = np.where(self.carrier[g] == k)[0]
                if not bs.size: continue
                ok = (ucls == 1)[None, :] & static[bs] & HOLD
                for pi in range(3):
                    for band in BANDS(self.Lh[pi]):
                        if group(band) != g or not HOLD: continue
                        m = M[pi][band]; r, c = m['r'], m['c']; cur = m['cur']; rows = m['rows'][cur]
                        f = F[pi][band][cur]; ilo, ihi = IV[pi][band][0][cur], IV[pi][band][1][cur]; xp = Tp[pi][band][rows]
                        Dq = np.repeat(np.repeat(self.steps_arr(pi, band, PuP[bs]), r, 0), c, 1)
                        th = np.clip(self.hold_target(pi, band, rows, xp, Dq, MP), ilo, ihi) if band != 'LL' else np.clip(xp, self.lo, self.hi)
                        ok &= blockmin((f == th).astype(np.int64), r, c).astype(bool)
                holdg_e[g][bs] = ok
                for i, b in enumerate(bs): Pu_e[b] = np.where(ok[i], PuP[b], Pu_e[b])
                nflip = int((ok != res['holdg'][g]).sum())
                if nflip: self.stats['hold_flip'] = self.stats.get('hold_flip', 0) + nflip
        # --- plan self-read (candidates counted as intra; fixed modes for earlier units; new units: some mode)
        Pe = PMAX; Pi_u = np.full((self.nblk, self.U), PMAX, np.int64); Pr_u = np.full((self.nblk, self.U), PMAX, np.int64)
        for pi in range(3):
            for band in BANDS(self.Lh[pi]):
                m = M[pi][band]; cur = m['cur']
                if not cur.any(): continue
                f = F[pi][band][cur]; b_ = bnd(pi, band, cur); r, c = m['r'], m['c']
                vi = np.where(b_, 60, val2(f))
                if intra_frame: v = vi
                else:
                    xp = Tp[pi][band][m['rows']][cur]; vr = np.where(b_, 60, val2(f - xp))
                    ucl = np.repeat(np.repeat(ucls[None, :], f.shape[0], 0), c, 1)
                    nw = np.repeat(np.isin(np.arange(b0, b1), newb), r)[cur]
                    md = np.repeat(np.repeat(mode[b0:b1], r, 0), c, 1)[cur]
                    hd = np.repeat(np.repeat(holdg_e[group(band)][b0:b1], r, 0), c, 1)[cur]
                    v = np.where(md == 1, vr, vi); v = np.where(ucl == 1, vi, v)
                    if band == 'LL': v = np.where(ucl == 2, vi, v); vr = np.where(ucl == 2, vi, vr)
                    vi = np.where(hd, 60, vi); vr = np.where(hd, 60, vr); v = np.where(hd, 60, v)
                    if nw.any():
                        bb = (m['rows'][cur][nw][::r] // r)
                        Pi_u[bb] = np.minimum(Pi_u[bb], pbound(pi, band, blockmin(vi[nw], r, c)))
                        Pr_u[bb] = np.minimum(Pr_u[bb], pbound(pi, band, blockmin(np.where(ucl == 1, vi, vr)[nw], r, c)))
                        v = np.where(nw[:, None], 60, v)
                Pe = min(Pe, pbound(pi, band, int(v.min())))
        if nb and not intra_frame: Pe = min(Pe, int(np.maximum(Pi_u[newb], Pr_u[newb]).min()))
        Pe = int(max(0, min(PMAX, Pe)))
        mode_e = mode.copy()
        if not intra_frame and nb:
            ci = np.zeros((nb, self.U)); cr = np.zeros((nb, self.U)); rep_r = Pr_u[newb] >= Pe; rep_i = Pi_u[newb] >= Pe
            for pi in range(3):
                pc = 0 if pi == 0 else 1
                for band in BANDS(self.Lh[pi]):
                    if group(band) != 'll': continue
                    m = M[pi][band]; r, c = m['r'], m['c']; De = self.step(pi, band, Pe)
                    rr = np.concatenate([np.arange(r * (b - b0), r * (b - b0) + r) for b in newb]); rows = m['rows'][rr]
                    f = F[pi][band][rr]; ilo, ihi = IV[pi][band][0][rr], IV[pi][band][1][rr]; xp = Tp[pi][band][rows]; llv = F[pi]['LL'][newb - b0]
                    qi_ = canon_index(f, 0, De * np.ones(f.shape, np.int64), ilo, ihi); qr_ = canon_index(f, xp, De * np.ones(f.shape, np.int64), ilo, ihi)
                    if band == 'LL':
                        ci += blocksum(np.full(f.shape, self.rawbits(De), np.float64), r, c); llx = np.repeat((ucls == 2)[None, :], nb, 0)
                        cr += np.where(llx, self.rawbits(De), blocksum(bits_map(self.tabs, pc, band, qr_, self.ctx_rows(pi, band, rows, cx, vc, np.ones(f.shape, bool), llv)), r, c))
                    else:
                        ci += blocksum(bits_map(self.tabs, pc, band, qi_, self.ctx_rows(pi, band, rows, cx, vc, np.zeros(f.shape, bool), llv)), r, c)
                        cr += blocksum(bits_map(self.tabs, pc, band, qr_, self.ctx_rows(pi, band, rows, cx, vc, np.ones(f.shape, bool), llv)), r, c)
            ci += self.tabs.length(('mode',), 2)[0]; cr += self.tabs.length(('mode',), 2)[1]
            for i, b in enumerate(newb): mode_e[b] = np.where(ucls == 1, 0, rep_r[i].astype(np.int64))
        # --- emitted indices and exact bits for the carried rows (symbol counting for training happens here only)
        self.tabs.training = getattr(self, 'train', False)
        tot = 80.0 + (self.vector_bits(V, k) if not intra_frame else 0.0); self._fin_bb = {}
        E = []; Fo = []; self._fin_bb = {}
        for pi in range(3):
            pc = 0 if pi == 0 else 1; Ep = {}; Fp = {}
            for band in BANDS(self.Lh[pi]):
                m = M[pi][band]; cur = m['cur']
                if not cur.any(): Ep[band] = None; Fp[band] = None; continue
                r, c = m['r'], m['c']; rows = m['rows'][cur]; bs_ = rows[::r] // r
                f = F[pi][band][cur]; ilo, ihi = IV[pi][band][0][cur], IV[pi][band][1][cur]
                Dq = self.step(pi, band, Pe) * np.ones(f.shape, np.int64)
                if intra_frame: inter = np.zeros(f.shape, bool); hdx = np.zeros(f.shape, bool)
                else:
                    g = group(band)
                    mdx = np.repeat(np.repeat(mode_e[bs_], r, 0), c, 1); hdx = np.repeat(np.repeat(holdg_e[g][bs_], r, 0), c, 1); pux = np.repeat(np.repeat(PuP[bs_], r, 0), c, 1)
                    llx = np.repeat(np.repeat((ucls == 2)[None, :], f.shape[0], 0), c, 1) if band == 'LL' else np.zeros(f.shape, bool)
                    inter = (mdx == 1) & ~llx & ~hdx
                    if hdx.any():
                        for p_ in np.unique(pux[hdx]): Dq = np.where(hdx & (pux == p_), self.step(pi, band, int(p_)), Dq)
                bs = np.where(inter, Tp[pi][band][rows], 0) if not intra_frame else np.zeros(f.shape, np.int64)
                if band == 'LL':
                    above = Fc[pi]['LL'][bs_[0] - 1] if bs_[0] > 0 else None; pr = np.empty_like(f)
                    for i in range(len(bs_)): pr[i] = self.ll_pred(f[i:i + 1], above)[0]; above = f[i]
                    llctx = np.clip(pr, self.lo, self.hi)
                    pidx = (pr + Dq // 2) // Dq
                    qc = canon_index(f, np.where(inter, bs, Dq * pidx), Dq, ilo, ihi)
                    qc = np.where(hdx, f - pr, qc)
                else:
                    llctx = F[pi]['LL'][bs_ - b0]; qc = canon_index(f, bs, Dq, ilo, ihi)
                chk = np.clip(bs + Dq * qc, ilo, ihi) if band != 'LL' else np.where(hdx, pr + qc, np.clip(np.where(inter, bs, Dq * pidx) + Dq * qc, ilo, ihi))
                if self.legal and not np.array_equal(chk, f):
                    bad = np.argwhere(np.clip(bs + Dq * qc, ilo, ihi) != f)[0]; i, j = bad; u = j // c; bb = bs_[i // r]
                    raise SystemExit('emission fail %s pi%d slice %d P %d Pe %d blk %d unit %d: f=%d bs=%d Dq=%d ivl=(%d,%d) inter=%s hold=%s lane q=%d lane C=%d' % (
                        band, pi, k, P, Pe, bb, u, f[i, j], bs[i, j], Dq[i, j], ilo[i, j], ihi[i, j], inter[i, j], hdx[i, j], res['Q'][pi][band][i, j], res['C'][pi][band][i, j]))
                skip = (Pe == PMAX)
                if skip: qc = np.where(hdx, qc, np.where(inter | (band != 'LL'), 0, qc))   # floor plan: no symbol stream
                Ep[band] = qc; Fp[band] = f
                if band == 'LL': self.llu[pi][bs_] = f
                t0_ = tot; ctxm = self.ctx_rows(pi, band, rows, cx, vc, inter, llctx)
                if band == 'LL':
                    bl = self.ll_bits(pc, qc, inter, hdx, ctxm)
                    tot += bl.sum() if not skip else bl[~inter].sum()
                else:
                    bl = bits_map(self.tabs, pc, band, qc, ctxm) if (not skip or hdx.any()) else None
                    if not skip: tot += bl.sum()
                    elif hdx.any(): tot += bl[hdx].sum()
                if os.environ.get('DBG_SLICE') and k == int(os.environ['DBG_SLICE']) and bl is not None:
                    self._fin_dbg = getattr(self, '_fin_dbg', {}); self._fin_dbg[(pi, band)] = (qc.copy(), ctxm.copy(), inter.copy(), hdx.copy(), bl.copy())
                    self._fin_iv = getattr(self, '_fin_iv', {}); self._fin_iv[(pi, band)] = (ilo.copy(), ihi.copy(), f.copy(), rows.copy())
                self._fin_bb[(pi, band)] = tot - t0_
                if getattr(self, 'dbg_bits', False):
                    bb = self.stats.setdefault('band_bits', {}); key = (pi, band); bb[key] = bb.get(key, 0.0) + (tot - t0_)
                    nz = self.stats.setdefault('band_nz', {}); nz[key] = nz.get(key, 0) + int((qc != 0).sum()); nn = self.stats.setdefault('band_n', {}); nn[key] = nn.get(key, 0) + qc.size
            E.append(Ep); Fo.append(Fp)
        self._flagdbg = {}; t_pre = tot
        if not intra_frame:
            for g in ('ll', 'mid', 'fine'):
                bs = np.where(self.carrier[g] == k)[0]
                if not bs.size: continue
                b1m = (ucls == 1)[None, :].repeat(len(bs), 0); hb = holdg_e[g][bs]
                tot += self.tabs.lenmap(('hold',), 2, hb[b1m].astype(np.int64)).sum() if b1m.any() else 0.0
                # Pu is sent once per unit, with its first held group
                if g == 'll': first = hb & b1m
                elif g == 'mid': first = hb & b1m & ~holdg_e['ll'][bs]
                else: first = hb & b1m & ~holdg_e['ll'][bs] & ~holdg_e['mid'][bs]
                hp = PuP[bs][first]
                if hp.size: tot += eg0_bits(PMAX - hp).sum()
                self._flagdbg[g] = (int(hb.sum()), int(first.sum()), float(eg0_bits(PMAX - hp).sum() if hp.size else 0))
            if nb:
                b1m = (ucls == 1)[None, :].repeat(nb, 0); mb = mode_e[newb]
                tot += self.tabs.lenmap(('mode',), 2, mb[~b1m]).sum() if (~b1m).any() else 0.0
        self.tabs.training = False
        hdr_ = 80.0 + (self.vector_bits(V, k) if not intra_frame else 0.0); fl_ = tot - t_pre
        if abs(tot - (hdr_ + sum(self._fin_bb.values()) + fl_)) > 1e-3 and os.environ.get('DBG_EST'): print('   EMIT hidden term %.1f (tot %.1f hdr %.1f bands %.1f flags %.1f)' % (tot - (hdr_ + sum(self._fin_bb.values()) + fl_), tot, hdr_, sum(self._fin_bb.values()), fl_))
        return dict(bits=float(tot), Pe=Pe, E=E, F=Fo, mode=mode_e, holdg=holdg_e, Pu=Pu_e, flagdbg=dict(self._flagdbg), flags=fl_)
    def vector_bits(self, V, k):
        rows = [k + 1] if k > 0 else [0, 1]; tot = 0.0
        for r in rows:
            if r >= self.nby: continue
            v = V[r]; d = v.copy(); d[1:] = v[1:] - v[:-1]
            for comp, key in ((0, ('mvy',)), (1, ('mvx',))): tot += self.tabs.lenmap(key, 65, np.clip(d[:, comp], -32, 32) + 32).sum()
        return tot
    # ---- frame encode
    def encode(self, src, force_intra=False):
        t = self.t; intra_frame = (self.ref is None) or force_intra; phi = t % self.Nc
        V = search(self.ref[0], self.ref2[0], self.S, self.BWm) if (self.ref is not None and self.ref2 is not None) else np.zeros((self.nby, self.nbx, 2), np.int64)
        ucls, xp, Tp, static = self.prepare(V, intra_frame, phi)
        Ts = [pyr2.analysis(src[pi], self.Lh[pi]) for pi in range(3)]
        MS = self.boundary_masks(Ts) if self.legal else None
        MP = self.boundary_masks(Tp) if (self.legal and not intra_frame) else None
        cx, vc = self.contexts(Tp, V, intra_frame)
        nb, U = self.nblk, self.U; self._static = static
        mode = np.zeros((nb, U), np.int64); Pu = np.full((nb, U), -1, np.int64)
        holdg = {g: np.zeros((nb, U), bool) for g in ('ll', 'mid', 'fine')}
        PuP = self.unit_plan(Tp, np.arange(nb), MP) if not intra_frame else np.full((nb, U), PMAX, np.int64)
        self.llu = [np.zeros((nb, U), np.int64) for _ in range(3)]
        Fc = [{b: np.zeros(Ts[pi][b].shape, np.int64) for b in BANDS(self.Lh[pi])} for pi in range(3)]
        Ec = [{b: np.zeros(Ts[pi][b].shape, np.int64) for b in BANDS(self.Lh[pi])} for pi in range(3)]
        Pk = np.zeros(self.NS, np.int64); Pe = np.zeros(self.NS, np.int64); bits = np.zeros(self.NS); est = np.zeros(self.NS); viaread = np.zeros(self.NS, bool)
        st = dict(Fc=Fc, mode=mode, Pu=Pu, Pk=Pk, MP=MP, PuP=PuP, static=static, holdg=holdg, Pe=Pe)
        self._Pe = Pe; self._PuP = PuP
        credit = 0.0; Fbody = self.F - 32
        for k in range(self.NS):
            budget = Fbody * self.share[k] + credit
            Pst = self.reading_plan(Ts, Tp, k, intra_frame, ucls, holdg, mode, MS)
            chosen = None
            if Pst is not None and Pst > 0:
                res = self.lane(Ts, Tp, k, Pst, intra_frame, ucls, V, st, cx, vc, MS)
                if res['bits'] <= budget: chosen = (Pst, res); viaread[k] = True
                elif os.environ.get('DBG_READ'):
                    print('READ-MISS slice %d Pst %d lane %.1f budget %.1f' % (k, Pst, res['bits'], budget), flush=True)
                    self.reading_plan(Ts, Tp, k, intra_frame, ucls, holdg, mode, MS, explain=True)
                    ref = getattr(self, 'dbg_ref', {}).get(k)
                    if ref:
                        for key in sorted(res['bb']):
                            if abs(res['bb'][key] - ref.get(key, 0)) > 0.5: print('     band', key, 'g2 lane %.1f  g1 emitted %.1f' % (res['bb'][key], ref.get(key, 0)))
                        print('     sum bands g2 lane %.1f g1 emitted %.1f | non-band g2 %.1f' % (sum(res['bb'].values()), sum(ref.values()), res['bits'] - sum(res['bb'].values())))
            elif os.environ.get('DBG_READ'): print('READ-NONE slice %d Pst %s' % (k, Pst), flush=True)
            if chosen is None:
                PL = [NP * o for o in range(12)] + [PMAX]          # 10 octave lanes + the free floor lane
                oct_ = [self.lane(Ts, Tp, k, P_, intra_frame, ucls, V, st, cx, vc, None) for P_ in PL]
                fit = [i for i in range(len(PL)) if oct_[i]['bits'] <= budget]
                if not fit:
                    self.stats['overflow'] = self.stats.get('overflow', 0) + 1; chosen = (PMAX, oct_[-1])
                    if os.environ.get('DBG_EST'): print('OVERFLOW slice %d budget %.1f floor lane %.1f: hdr+vec %.1f bands %s flags %s' % (k, budget, chosen[1]['bits'], chosen[1]['hdr'], {kk: round(v) for kk, v in chosen[1]['bb'].items() if v > 20}, chosen[1]['flagdbg']))
                else:
                    i0 = fit[0]
                    if i0 == 0: chosen = (0, oct_[0])
                    else:
                        fine = [self.lane(Ts, Tp, k, Pf, intra_frame, ucls, V, st, cx, vc, None) for Pf in range(PL[i0 - 1] + 1, PL[i0])]
                        ok = [i for i, r_ in enumerate(fine) if r_['bits'] <= budget]
                        chosen = (PL[i0 - 1] + 1 + ok[0], fine[ok[0]]) if ok else (PL[i0], oct_[i0])
            P, res = chosen; Pk[k] = P
            fin = self.finalize(Ts, Tp, k, P, res, intra_frame, ucls, V, st, cx, vc)
            if fin['bits'] > res['bits'] + 1e-6:
                self.stats['emit_over_est'] = self.stats.get('emit_over_est', 0) + 1
                if os.environ.get('DBG_EST') and self.stats['emit_over_est'] <= 3:
                    for key in sorted(self._fin_bb):
                        if abs(self._fin_bb[key] - res['bb'].get(key, 0)) > 0.5: print('   band', key, 'lane %.1f emitted %.1f' % (res['bb'].get(key, 0), self._fin_bb[key]))
                    print('   sum bands lane %.1f emitted %.1f | hdr+vec lane %.1f | flags lane %.1f emitted %.1f | flagdbg lane %s emit %s' % (sum(res['bb'].values()), sum(self._fin_bb.values()), res['hdr'], res['bits'] - res['hdr'] - sum(res['bb'].values()), fin['bits'] - res['hdr'] - sum(self._fin_bb.values()), res['flagdbg'], fin['flagdbg']))
                    newb_ = np.where(self.carrier['ll'] == k)[0]
                    print('EST-EXCEEDED slice %d P %d Pe %d est %.1f emitted %.1f | mode switches %d | holds emitted %s | viaread %s' % (
                        k, P, fin['Pe'], res['bits'], fin['bits'], int((fin['mode'][newb_] != res['mode'][newb_]).sum()) if newb_.size else 0,
                        {g: int(fin['holdg'][g][np.where(self.carrier[g] == k)[0]].sum()) for g in fin['holdg']}, bool(viaread[k])), flush=True)
            est[k] = res['bits']; bits[k] = fin['bits']; Pe[k] = fin['Pe']; credit = budget - fin['bits']
            if os.environ.get('DBG_SLICE') and k == int(os.environ['DBG_SLICE']): self.dbg_last = (res, fin, {g: v.copy() for g, v in holdg.items()}, mode.copy())
            if os.environ.get('DBG_READ') or os.environ.get('DBG_EST'): self.dbg_fin = getattr(self, 'dbg_fin', {}); self.dbg_fin[k] = dict(self._fin_bb)
            mode[:] = fin['mode']; Pu[:] = fin['Pu']
            for g in holdg: holdg[g][:] = fin['holdg'][g]
            for pi in range(3):
                for band in BANDS(self.Lh[pi]):
                    bs_, rows = self.rows_of(band, k)
                    if bs_.size: Fc[pi][band][rows] = fin['F'][pi][band]; Ec[pi][band][rows] = fin['E'][pi][band]
        rec = []
        for pi in range(3):
            xr, Fw, IVw = pyr2.synthesis(Fc[pi], self.Lh[pi], self.lo, self.hi) if self.legal else synth_clip(Fc[pi], self.Lh[pi], self.lo, self.hi)
            if self.legal:
                for band in BANDS(self.Lh[pi]):
                    if not np.array_equal(Fw[band], Fc[pi][band]): self.stats['final_mismatch'] = self.stats.get('final_mismatch', 0) + int((Fw[band] != Fc[pi][band]).sum())
            rec.append(xr)
        total = 32 + bits.sum(); self.stats['frame_bits'] = float(total); self.stats['est_bits'] = float(32 + est.sum())
        if total > self.F + 1e-6: self.stats['pipe_overflow'] = self.stats.get('pipe_overflow', 0) + 1
        self.last = dict(P=Pk, Pe=Pe, mode=mode.copy(), holdg={g: v.copy() for g, v in holdg.items()}, Pu=Pu.copy(), ucls=ucls, intra=intra_frame,
                         V=V, E=Ec, bits=bits, viaread=int(viaread.sum()), phi=phi)
        self.ref2 = self.ref; self.ref = rec; self.t += 1
        return rec
    # ---- decoder path (from symbols), own references, optional slice loss
    def build_C(self, E, Tp, Pe, mode, holdg, Pu, ucls, intra_frame):
        out = []
        for pi in range(3):
            Lh = self.Lh[pi]; C = {}
            for band in BANDS(Lh):
                r = rows_per_block(band); c = self.ucols(pi, band); q = E[pi][band]; shape = q.shape
                Erow = np.repeat(Pe[self.carrier[group(band)]], r)
                Dq = np.array([self.step(pi, band, int(p)) for p in Erow])[:, None] * np.ones((1, shape[1]), np.int64)
                if band == 'LL':
                    mid = (self.lo + self.hi + 1) // 2; fin = np.zeros(shape, np.int64)
                    inter_ll = ((mode == 1) & ~(ucls == 2)[None, :] & ~holdg['ll']) if not intra_frame else np.zeros(shape, bool)
                    Dl = Dq.copy()
                    if not intra_frame and holdg['ll'].any():
                        for p_ in np.unique(Pu[holdg['ll']]): Dl = np.where(holdg['ll'] & (Pu == p_), self.step(pi, band, int(p_)), Dl)
                    hl = holdg['ll'] if not intra_frame else np.zeros(shape, bool)
                    for b in range(shape[0]):
                        for u in range(shape[1]):
                            pred = fin[b, u - 1] if u > 0 else (fin[b - 1, 0] if b > 0 else mid)
                            if inter_ll[b, u]: fin[b, u] = min(self.hi, max(self.lo, Tp[pi][band][b, u] + Dl[b, u] * q[b, u]))
                            elif hl[b, u]: fin[b, u] = pred + q[b, u]
                            else: fin[b, u] = min(self.hi, max(self.lo, Dl[b, u] * ((pred + Dl[b, u] // 2) // Dl[b, u] + q[b, u])))
                    C[band] = fin; continue
                if intra_frame: C[band] = Dq * q; continue
                mdx = np.repeat(np.repeat(mode, r, 0), c, 1); hdx = np.repeat(np.repeat(holdg[group(band)], r, 0), c, 1); pux = np.repeat(np.repeat(Pu, r, 0), c, 1)
                llx = np.repeat(np.repeat((ucls == 2)[None, :], shape[0], 0), c, 1) if band == 'LL' else np.zeros(shape, bool)
                inter = (mdx == 1) & ~llx & ~hdx
                if hdx.any():
                    for p_ in np.unique(pux[hdx]): Dq = np.where(hdx & (pux == p_), self.step(pi, band, int(p_)), Dq)
                C[band] = np.where(inter, Tp[pi][band], 0) + Dq * q
            out.append(C)
        return out
    def decode(self, last, dref, lost=()):
        intra_frame = last['intra']; V = last['V'].copy(); ucls = last['ucls']; phi = last['phi']
        Pe = last['Pe'].copy(); mode = last['mode'].copy(); holdg = {g: v.copy() for g, v in last['holdg'].items()}; Pu = last['Pu'].copy()
        E = [{b: a.copy() for b, a in e.items()} for e in last['E']]
        for k in lost:
            for r in ([k + 1] if k > 0 else [0, 1]):
                if r < self.nby: V[r] = V[r - 1] if r > 0 else 0
            for b in np.where(self.carrier['ll'] == k)[0]: mode[b] = 1
            for g in holdg:
                for b in np.where(self.carrier[g] == k)[0]: holdg[g][b] = False
            for pi in range(3):
                for band in BANDS(self.Lh[pi]):
                    bs, rows = self.rows_of(band, k)
                    if bs.size: E[pi][band][rows] = 0
        Tp = [None] * 3 if intra_frame else self.prepare(V, intra_frame, phi, ref=dref)[2]
        C = self.build_C(E, Tp, Pe, mode, holdg, Pu, ucls, intra_frame)
        rec = []
        for pi in range(3):
            xr, _, _ = pyr2.synthesis(C[pi], self.Lh[pi], self.lo, self.hi) if self.legal else synth_clip(C[pi], self.Lh[pi], self.lo, self.hi)
            rec.append(xr)
        return rec

def canon_index(f, bs, D, ilo, ihi):
    qc = (f - bs) // D
    upper = (f == ihi) & (bs < ihi); lower = (f == ilo) & (bs > ilo)
    qc = np.where(upper, np.ceil((ihi - bs) / D).astype(np.int64), qc)
    qc = np.where(lower, -np.ceil((bs - ilo) / D).astype(np.int64), qc)
    qc = np.where((f == ihi) & (bs >= ihi), 0, qc); qc = np.where((f == ilo) & (bs <= ilo), 0, qc)
    return qc

def synth_clip(C, Lh, lo, hi, b0=0):
    big = 1 << 20; x, F, IV = pyr2.synthesis(C, Lh, -big, big, b0); return np.clip(x, lo, hi), F, IV
