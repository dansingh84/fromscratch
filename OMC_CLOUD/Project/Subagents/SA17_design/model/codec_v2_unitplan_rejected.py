# SA17 codec model (numpy). Intra + inter (value-domain coefficient prediction), per-slice plan, exact CBR,
# REAL code lengths from static tables. Backends: 'pair' (legal by construction) or '53' (C1 comparison only).
import numpy as np, pyr, xf, ent

BANDS = pyr.bands(2, 5)
LEVEL = {'LL': 5, 'H5': 5, 'H4': 4, 'H3': 3, 'HL2': 2, 'LH2': 2, 'HH2': 2, 'HL1': 1, 'LH1': 1, 'HH1': 1}
ROWDIV = {b: (4 if LEVEL[b] >= 2 else 2) for b in BANDS}      # band rows per slice = S / ROWDIV
COLDIV = {b: 2 ** LEVEL[b] for b in BANDS}

def gains(backend, shape):
    A = 1 << 12
    if backend == 'pair':
        T0 = pyr.analysis(np.zeros(shape, np.int64))
        G = {}
        for b in T0:
            T = {k: np.zeros_like(v) for k, v in T0.items()}; h, w = T[b].shape; T[b][h // 2, w // 2] = A
            y, _, _ = pyr.synthesis(T, -10 ** 9, 10 ** 9, legal=False); G[b] = float((y.astype(float) ** 2).sum()) / A ** 2
        return G
    return xf.gains(shape, 2, 5, '53', '53')

class Alloc:
    """plan ladder: plan k -> exponent e[p][b]; k=0 finest. nested dyadic lattices (one band coarsens per step)."""
    def __init__(self, G_y, G_c, tilt=0.0, chroma=0.0, M_order=None):
        self.pb = [(p, b) for p in range(3) for b in BANDS]
        ob = {}
        for p, b in self.pb:
            G = G_y if p == 0 else G_c
            ob[(p, b)] = -0.5 * np.log2(G[b]) - tilt * (LEVEL[b] - 1) + (chroma if p else 0.0)
        ref = max(ob.values())
        self.ob = {k: int(np.round(v - ref)) for k, v in ob.items()}      # <= 0
        frac = {k: (v - ref) - np.round(v - ref) for k, v in ob.items()}
        self.rank = {k: i for i, k in enumerate(sorted(self.pb, key=lambda k: (-self.ob[k] - frac[k], k[0] == 0)))}
        self.M = len(self.pb)
    def e(self, k):
        return {pb: min(15, max(0, self.ob[pb] + (k + self.M - 1 - self.rank[pb]) // self.M)) for pb in self.pb}

def quant(r, step, rho):
    return (np.sign(r) * np.floor(np.abs(r) / step + rho)).astype(np.int64)

class Codec:
    def __init__(self, W, H, fmt=422, depth=10, S=8, lo=4, hi=1019, backend='pair', tabs=None,
                 tilt=0.0, chroma=0.0, rho=0.42, Kmax=None):
        self.W, self.H, self.S, self.lo, self.hi, self.backend = W, H, S, lo, hi, backend
        self.cw = W // 2 if fmt == 422 else W
        self.shapes = [(H, W), (H, self.cw), (H, self.cw)]
        self.tabs = tabs or ent.Tables()
        self.G = [gains(backend, self.shapes[0]), gains(backend, self.shapes[1])]
        self.al = Alloc(self.G[0], self.G[1], tilt, chroma)
        self.rho = rho; self.mid = 1 << (depth - 1)
        self.K = Kmax or 16 * self.al.M
        self.E = [self.al.e(k) for k in range(self.K)]
        self.collect = False; self.emit_reading = True; self.universal = False
        self.Emat = np.array([[self.E[k][pb] for pb in self.al.pb] for k in range(self.K)])
        self.UNIT = 64; self.nU = W // self.UNIT
        self.umap = []
        for p in range(3):
            d = {}
            for b in BANDS:
                w = (W if p == 0 else self.cw) >> LEVEL[b]
                per = max(1, (self.UNIT if p == 0 else self.UNIT * self.cw // W) >> LEVEL[b])
                d[b] = np.minimum(np.arange(w) // per, self.nU - 1)
            self.umap.append(d)

    # ---- transform backend ----
    def ana(self, x):
        if self.backend == 'pair': return pyr.analysis(x)
        return xf.analysis(x - self.mid, 2, 5, '53', '53')
    def syn(self, V):
        if self.backend == 'pair':
            y, F, IV = pyr.synthesis(V, self.lo, self.hi); return y, F, IV
        y = np.clip(xf.synthesis(V, 2, 5, '53', '53') + self.mid, self.lo, self.hi); return y, V, None

    def rows(self, b, k):
        r = self.S // ROWDIV[b]; return slice(k * r, (k + 1) * r)

    # ---- one frame ----
    def slice_ctx(self, c, b):
        """context with the 'above' neighbour cut at every slice top (packet independence)"""
        left = np.zeros_like(c); left[:, 1:] = c[:, :-1]
        up = np.zeros_like(c); up[1:] = c[:-1]
        r = self.S // ROWDIV[b]; up[::r] = 0
        return np.minimum(ent.NCTX - 1, (left + up + 1) // 2)

    def row_bits(self, p, b, q, im=None, collect=False):
        c = ent.cls(q); cx = self.slice_ctx(c, b); cc = np.minimum(c, ent.NC - 1)
        extra = np.maximum(c - 1, 0) + (c > 0)
        out = np.zeros(q.shape)
        for inter in ((False,) if im is None else (False, True)):
            key = ent.table_key(p, b, inter)
            ln = self.tabs.len.get(key)
            if ln is None: ln = np.full((ent.NCTX, ent.NC), np.log2(ent.NC))
            m = np.ones(q.shape, bool) if im is None else (im if inter else ~im)
            out = np.where(m, ln[cx, cc] + extra, out)
            if collect and m.any(): self.tabs.add(key, cc[m], cx[m])
        return out.sum(axis=1)

    def per_slice(self, rowbits, b):
        r = self.S // ROWDIV[b]; return rowbits.reshape(-1, r).sum(axis=1)

    def code_frame(self, src, base=None, inter_mask=None, bpp=0.5, hdr_bits=0.0, keep=None, rho_map=None, umap=None):
        """src: 3 planes. base: per plane dict band->base leaf values (None = intra everywhere).
        inter_mask: per plane dict band->bool (True where base applies). keep: optional per plane dict band ->
        (target values, bool mask) for re-description of held values (encoder-only choice).
        hdr_bits: per-slice side bits (vectors, modes). Returns decoded planes, per-slice bits, info."""
        nS = self.H // self.S; B = bpp * self.W * self.S
        hdr = np.broadcast_to(np.asarray(hdr_bits, float), (nS,)) + 8 + 36
        Ts = [self.ana(x) for x in src]
        C = {}; Qe = {}; LLx = {}
        RD = self.readability(Ts, base, inter_mask, umap) if (self.universal and self.backend == 'pair') else None
        for p in range(3):
            for b in BANDS:
                im = inter_mask[p][b] if inter_mask is not None else None
                ce = np.zeros((16, nS)); qe = []
                if b == 'LL':
                    bll = base[p]['LL'] if base is not None else None
                    kt = keep[p].get('LL') if keep is not None else None
                    qs, fs, bs = self.ll_loop(Ts[p]['LL'], bll, im, kt); LLx[p] = (fs, bs)
                    for e in range(16): ce[e] = self.per_slice(self.row_bits(p, b, qs[e], im), b)
                    Qe[(p, b)] = qs
                else:
                    r = Ts[p][b] - (base[p][b] if base is not None else 0)
                    kt = keep[p].get(b) if keep is not None else None
                    rh = rho_map[p][b] if rho_map is not None else self.rho
                    for e in range(16):
                        q = quant(r, 1 << e, rh)
                        if kt is not None:
                            tv, km = kt; st = 1 << e
                            kq = np.round((tv - (base[p][b] if base is not None else 0)) / st).astype(np.int64)
                            okk = km & ((kq * st) == (tv - (base[p][b] if base is not None else 0))) & (np.abs(r - kq * st) <= 0.75 * st)
                            q = np.where(okk, kq, q)
                        qe.append(q); ce[e] = self.per_slice(self.row_bits(p, b, q, im), b)
                    Qe[(p, b)] = qe
                C[(p, b)] = ce
        # rate control: one decision per slice (finest plan that fits), exact CBR with carried credit.
        # A unit whose input already reads exactly at a plan >= the slice's plan keeps that reading (re-encoder).
        plans = np.zeros(nS, np.int64); credit = 0.0; forced = np.zeros(nS, int)
        P2 = np.zeros((nS, self.nU), np.int64); hold = np.zeros((nS, self.nU), bool)
        Emat = np.array([[self.E[k][pb] for pb in self.al.pb] for k in range(self.K)])     # K x M
        for k in range(nS):
            tot = np.zeros(self.K)
            for j, pb in enumerate(self.al.pb): tot += C[pb][Emat[:, j], k]
            budget = B + credit - hdr[k]
            fit = np.nonzero(tot <= budget)[0]
            pk = fit[0] if fit.size else self.K - 1
            P2[k] = pk; cost = tot[pk]
            if RD is not None:
                ku = RD['ku'][k]; rd = ku >= pk
                if rd.any():
                    row = np.where(rd, ku, pk)
                    c1 = self.slice_cost(k, row, Ts, base, inter_mask, LLx, Qe, RD, None) + self.pbits(row)
                    if c1 <= budget: P2[k] = row; cost = c1; forced[k] = 1
                    else:
                        c2 = self.slice_cost(k, row, Ts, base, inter_mask, LLx, Qe, RD, ~rd) + self.pbits(row)
                        if c2 <= budget: P2[k] = row; hold[k] = ~rd; cost = c2; forced[k] = 2
                        else: forced[k] = -1
            plans[k] = pk; credit = max(0.0, budget - cost)
        out = []; bits = hdr.copy(); Qf = []; Q0 = []; V0 = []
        for p in range(3):
            V = {}; ST = {}; Q = {}
            for b in BANDS:
                em = self.expmap(P2, p, b); ST[b] = 1 << em
                if b == 'LL':
                    Q[b], V[b], llbase = self.ll_final(Ts[p]['LL'], base[p]['LL'] if base is not None else None,
                                                     inter_mask[p]['LL'] if inter_mask is not None else None, em,
                                                     keep[p].get('LL') if keep is not None else None)
                else:
                    qa = np.stack(Qe[(p, b)]); Q[b] = np.take_along_axis(qa, em[None], 0)[0]
                    if hold.any():
                        Q[b] = np.where(self.unitmask(hold, p, b), 0, Q[b])
                    V[b] = Q[b] * ST[b] + (base[p][b] if base is not None else 0)
            Q0p = {b: Q[b].copy() for b in BANDS}; V0p = {b: V[b].copy() for b in BANDS}
            y, F, IV = self.syn(V)
            if self.backend == 'pair':
                for b in BANDS:
                    bs_ = llbase if b == 'LL' else (base[p][b] if base is not None else 0)
                    qc, ok = pyr.canon_index(F[b], bs_, ST[b], IV[b]); assert ok.all(), b
                    Q[b] = qc
            out.append(y); Qf.append(Q); Q0.append(Q0p); V0.append(V0p)
            for b in BANDS:
                im = inter_mask[p][b] if inter_mask is not None else None
                bits += self.per_slice(self.row_bits(p, b, Q[b], im, collect=self.collect), b)
        bits += np.array([self.pbits(P2[k]) for k in range(nS)])
        if self.backend == 'pair' and self.emit_reading:
            # generation 1 emits exactly what the canonical reading of its own picture returns
            rp, Qr, rbits = self.read(out, base, inter_mask, hdr_bits)
            assert (rp >= P2).all()
            P2, Qf, bits = rp, Qr, rbits
        cum = np.cumsum(bits); lim = B * np.arange(1, nS + 1)
        over = int((cum > lim + 1e-6).sum())
        return out, bits, dict(plans=P2, over=over, Q=Qf, Q0=Q0, V0=V0, forced=forced)

    # ---- per-unit plan helpers ----
    def pbits(self, row):
        # slice plan (9 bits) + per-unit plans as signed Exp-Golomb differences to the left unit
        d = np.diff(row); z = np.where(d > 0, 2 * d - 1, -2 * d)
        return 9 + float((2 * np.floor(np.log2(z + 1)) + 1).sum())
    def unitmask(self, M2, p, b):
        """(nS, nU) bool -> band-shaped bool"""
        r = self.S // ROWDIV[b]; return np.repeat(M2, r, axis=0)[:, self.umap[p][b]]
    def expmap(self, P2, p, b):
        j = self.al.pb.index((p, b)); Emat = self.Emat
        r = self.S // ROWDIV[b]; return np.repeat(Emat[P2, j], r, axis=0)[:, self.umap[p][b]]
    def ll_final(self, src_ll, bll, im, em, kt=None):
        h, w = src_ll.shape; st = 1 << em
        q = np.zeros((h, w), np.int64); f = np.zeros((h, w), np.int64); bu = np.zeros((h, w), np.int64)
        left = np.full(h, self.mid if self.backend == 'pair' else 0, np.int64)
        lo_, hi_ = (self.lo, self.hi) if self.backend == 'pair' else (-10 ** 9, 10 ** 9)
        for j in range(w):
            bj = left if im is None else np.where(im[:, j], bll[:, j], left)
            qq = quant(src_ll[:, j] - bj, st[:, j], self.rho)
            if kt is not None:
                tv, km = kt; d = tv[:, j] - bj; kq = np.round(d / st[:, j]).astype(np.int64)
                okk = km[:, j] & (kq * st[:, j] == d) & (np.abs(src_ll[:, j] - tv[:, j]) <= 0.75 * st[:, j])
                qq = np.where(okk, kq, qq)
            v = np.clip(bj + qq * st[:, j], lo_, hi_)
            q[:, j] = qq; f[:, j] = v; bu[:, j] = bj; left = v
        return q, f, bu
    def slice_cost(self, k, row, Ts, base, inter_mask, LLx, Qe, RD, holdrow):
        tot = 0.0; P2 = np.zeros((self.H // self.S, self.nU), np.int64); P2[k] = row
        for p in range(3):
            for b in BANDS:
                rs = self.rows(b, k); em = self.expmap(P2, p, b)[rs]
                im = inter_mask[p][b][rs] if inter_mask is not None else None
                if b == 'LL':
                    q, _, _ = self.ll_final(Ts[p]['LL'][rs], base[p]['LL'][rs] if base is not None else None, im, em)
                else:
                    qa = np.stack(Qe[(p, b)])[:, rs]; q = np.take_along_axis(qa, em[None], 0)[0]
                    if holdrow is not None:
                        H2 = np.zeros_like(P2, bool); H2[k] = holdrow; q = np.where(self.unitmask(H2, p, b)[rs], 0, q)
                tot += self.row_bits(p, b, q, im).sum()
        return tot

    def decode(self, Q, P2, base, inter_mask):
        """the decoder: indices + per-unit plans + prediction state -> picture (legal for ANY indices)"""
        out = []
        for p in range(3):
            V = {}
            for b in BANDS:
                em = self.expmap(P2, p, b); st = 1 << em
                im = inter_mask[p][b] if inter_mask is not None else None
                if b == 'LL':
                    h, w = Q[p][b].shape; f = np.zeros((h, w), np.int64)
                    left = np.full(h, self.mid if self.backend == 'pair' else 0, np.int64)
                    lo_, hi_ = (self.lo, self.hi) if self.backend == 'pair' else (-10 ** 9, 10 ** 9)
                    for j in range(w):
                        bj = left if im is None else np.where(im[:, j], base[p]['LL'][:, j], left)
                        f[:, j] = np.clip(bj + Q[p][b][:, j] * st[:, j], lo_, hi_); left = f[:, j]
                    V[b] = f
                else:
                    V[b] = Q[p][b] * st + (base[p][b] if base is not None else 0)
            y, _, _ = self.syn(V); out.append(y)
        return out

    def unit_read(self, F, base, inter_mask):
        """per (slice, unit) coarsest plan under which every leaf of the unit reproduces (F: final leaves per plane)."""
        nS = self.H // self.S; emax = {}; BS = []
        for p in range(3):
            bs = {}
            for b in BANDS:
                im = inter_mask[p][b] if inter_mask is not None else None
                bs[b] = self.ll_base(F[p][0]['LL'], base[p]['LL'] if base is not None else None, im) if b == 'LL' else \
                    (base[p][b] if base is not None else np.zeros_like(F[p][0][b]))
                em = np.full((nS, self.nU), -1); r = self.S // ROWDIV[b]; u = self.umap[p][b]
                starts = np.searchsorted(u, np.arange(self.nU))
                for e in range(16):
                    q, ok = pyr.canon_index(F[p][0][b], bs[b], 1 << e, F[p][1][b])
                    cell = np.logical_and.reduceat(ok.reshape(nS, r, -1).all(axis=1), starts, axis=1)
                    em = np.where(cell & (em == e - 1), e, em)
                emax[(p, b)] = em
            BS.append(bs)
        EM = np.stack([emax[pb] for pb in self.al.pb])              # M x nS x nU
        ku = np.full((nS, self.nU), -1, np.int64)
        for k in range(self.K):
            good = (self.Emat[k][:, None, None] <= EM).all(axis=0); ku = np.where(good, k, ku)
        return ku, BS

    def readability(self, Ts, base, inter_mask, umap):
        F = []
        for p in range(3):
            y, F2, IV = self.syn(Ts[p]); F.append((F2, IV))
        ku, _ = self.unit_read(F, base, inter_mask)
        return dict(ku=ku, C0={})

    def ll_base(self, Fll, base_ll, im):
        left = np.concatenate([np.full((Fll.shape[0], 1), self.mid, np.int64), Fll[:, :-1]], 1)
        return left if im is None else np.where(im, base_ll, left)

    def read(self, D, base, inter_mask, hdr_bits=0.0):
        """canonical reading of a decoded picture D given the prediction state: per (slice, unit) the COARSEST plan
        under which every leaf is reproduced, with the smallest-magnitude indices. Returns P2, Q, per-slice bits."""
        nS = self.H // self.S
        hdr = np.broadcast_to(np.asarray(hdr_bits, float), (nS,)) + 8 + 36
        F = []
        for p in range(3):
            T = self.ana(D[p]); y, F2, IV = self.syn(T)
            assert np.array_equal(y, D[p]), 'picture is not a fixed point of analysis/synthesis'
            F.append((F2, IV))
        P2, BS = self.unit_read(F, base, inter_mask)
        assert (P2 >= 0).all(), 'no consistent plan'
        bits = hdr.copy() + np.array([self.pbits(P2[k]) for k in range(nS)]); Qf = []
        for p in range(3):
            Q = {}
            for b in BANDS:
                st = 1 << self.expmap(P2, p, b)
                Q[b], ok = pyr.canon_index(F[p][0][b], BS[p][b], st, F[p][1][b]); assert ok.all()
                im = inter_mask[p][b] if inter_mask is not None else None
                bits += self.per_slice(self.row_bits(p, b, Q[b], im), b)
            Qf.append(Q)
        return P2, Qf, bits

    def ll_loop(self, src_ll, bll, im, kt=None):
        """closed-loop LL: intra units predicted from the final left neighbour (mid at column 0), inter units
        from the motion base. vectorised over the 16 exponents. returns q[e], final[e], base_used[e]."""
        h, w = src_ll.shape; E = 16
        st = (1 << np.arange(E))[:, None]
        q = np.zeros((E, h, w), np.int64); f = np.zeros((E, h, w), np.int64); bu = np.zeros((E, h, w), np.int64)
        left = np.full((E, h), self.mid if self.backend == 'pair' else 0, np.int64)
        lo_, hi_ = (self.lo, self.hi) if self.backend == 'pair' else (-10 ** 9, 10 ** 9)
        for j in range(w):
            if im is not None:
                bj = np.where(im[:, j][None, :], bll[:, j][None, :], left)
            else:
                bj = left
            qq = quant(src_ll[:, j][None, :] - bj, st, self.rho)
            if kt is not None:
                tv, km = kt; d = tv[:, j][None, :] - bj; kq = np.round(d / st).astype(np.int64)
                okk = km[:, j][None, :] & (kq * st == d) & (np.abs(src_ll[:, j][None, :] - tv[:, j][None, :]) <= 0.75 * st)
                qq = np.where(okk, kq, qq)
            v = np.clip(bj + qq * st, lo_, hi_)
            q[:, :, j] = qq; f[:, :, j] = v; bu[:, :, j] = bj; left = v
        return q, f, bu

    def bits_of(self, p, b, q, im=None, collect=False):
        if im is None or not im.any():
            key = ent.table_key(p, b, False)
            if collect: self.tabs.add(key, ent.cls(q), ent.ctx(ent.cls(q)))
            return self.tabs.bits(key, q)
        c = ent.cls(q); cx = ent.ctx(c); tot = 0.0
        for inter in (False, True):
            key = ent.table_key(p, b, inter); msk = im if inter else ~im
            if not msk.any(): continue
            ln = self.tabs.len.get(key)
            if ln is None: ln = np.full((ent.NCTX, ent.NC), np.log2(ent.NC))
            bb = ln[cx, np.minimum(c, ent.NC - 1)] + np.maximum(c - 1, 0) + (c > 0)
            tot += bb[msk].sum()
            if collect: self.tabs.add(key, c[msk], cx[msk])
        return tot
