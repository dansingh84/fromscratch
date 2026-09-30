# SA17 sequence codec model: intra frame 0, then inter frames with value-domain coefficient prediction
# (leaf = T(P) leaf + q*step), history-derived transmitted vectors, OBMC, column-band refresh with guard,
# clean-region barrier (reference fetch + vector derivation + OBMC block choice), exact CBR per slice.
import numpy as np, codec, motion, pyr, ent

UNIT = 64          # luma columns per refresh unit (chroma LL column = one unit in 4:2:2)

class Seq:
    def __init__(self, W, H, bpp, tabs, S=8, backend='pair', refresh=True, clean=True, cycle=8, rho_still=None,
                 bx=32, lam=0, still_hold=0, ry=4, ztol=2, l1k=0.0, **kw):
        self.ry = ry; self.l1k = l1k; motion.ZTOL = ztol
        self.rho_still = rho_still; self.lam = lam; motion.BX = bx
        self.universal = False; self.lock = None; self.still_hold = bool(still_hold); self.thr = None       # (t_own, phi) once the refresh phase is read from the input
        self.c = codec.Codec(W, H, S=S, backend=backend, tabs=tabs, **kw)
        if still_hold == 2: self.c.hold_mode = 2
        self.W, self.H, self.S, self.bpp = W, H, S, bpp
        self.nU = W // UNIT; self.Bw = -(-self.nU // cycle); self.cycle = -(-self.nU // self.Bw)
        self.refresh, self.clean = refresh, clean
        self.hist = []; self.t = 0
        self.sx = [1, 2, 2]

    def unit_cols(self, p, b, units):
        """bool column mask of band b of plane p for the given unit list"""
        lvl = codec.LEVEL[b]; w = (self.W if p == 0 else self.c.cw) >> lvl
        per = (UNIT if p == 0 else UNIT * self.c.cw // self.W) >> lvl
        m = np.zeros(w, bool)
        for u in units: m[u * per:(u + 1) * per] = True
        return m

    def encode(self, src, force_intra=False, phase=None, read=False, lost=(), heal=None):
        """read=True: generation-N encoder -- src is a decoded picture, the stream is its canonical reading.
        lost: slices whose indices are lost (the local decoder then conceals: indices 0 there)."""
        c = self.c; t = self.t
        nS = self.H // self.S
        if t == 0 or force_intra:
            if read:
                plans, Q, bits = c.read(src, None, None); out = c.decode(Q, plans, None, None)
                info = dict(plans=plans, over=0, Q=Q)
            else:
                c.universal = self.universal
                out, bits, info = c.code_frame(src, bpp=self.bpp, umap=self.umap() if self.universal else None)
            info['V'] = None; info['intra'] = True; info['base'] = None; info['im'] = None; self.thr = None
        else:
            if phase is not None: phi = phase
            elif self.universal:
                if self.lock is None: self.detect_phase(src)
                phi = ((t - self.lock[0] + self.lock[1]) % self.cycle) if self.lock is not None else (t % self.cycle)
            else: phi = t % self.cycle
            if len(self.hist) >= 2: V = self.derive(phi)
            else: V = np.zeros((self.H // motion.BY, self.W // motion.BX, 2), np.int64)
            if self.l1k:
                c.set_l1(self.l1k * float((np.abs(V).sum(-1) > 0).mean()))
            base, im, keep, zero, band = self.prepare(self.hist[-1], V, phi, heal)
            vb = self.vec_bits_per_slice(V)
            rho_map = None
            if self.rho_still is not None and len(self.hist) >= 2:
                rho_map = []
                for p in range(3):
                    rm = {}
                    for b in codec.BANDS:
                        zb = self.zero_mask(zero, p, b, base[p][b].shape)
                        rm[b] = np.where(zb & im[p][b], self.rho_still, c.rho)
                    rho_map.append(rm)
            if read:
                plans, Q, bits = c.read(src, base, im, vb); out = c.decode(Q, plans, base, im)
                info = dict(plans=plans, over=0, Q=Q)
            else:
                c.universal = self.universal
                hold = None
                if self.still_hold:
                    hold = []
                    for p in range(3):
                        hd = {}
                        for b in codec.BANDS:
                            zb = self.zero_mask(zero, p, b, base[p][b].shape) & im[p][b]
                            if c.hold_mode == 2:
                                sr = self.thr[p][b] if self.thr is not None else np.full(base[p][b].shape, 1e9)
                                hd[b] = np.where(zb, sr, 1e9)
                            else:
                                thr = self.thr[p][b] if self.thr is not None else np.zeros(base[p][b].shape)
                                hd[b] = np.where(zb, thr, -1.0)
                        hold.append(hd)
                out, bits, info = c.code_frame(src, base=base, inter_mask=im, bpp=self.bpp, hdr_bits=vb, keep=keep,
                                               rho_map=rho_map, umap=self.umap() if self.universal else None, hold=hold)
                if self.still_hold:
                    # encoder-only state: a still coefficient that has had its one refinement is held until the
                    # source really changes by more than 3/4 of the step it was refined at
                    nt = []
                    for p in range(3):
                        td = {}
                        for b in codec.BANDS:
                            zb = self.zero_mask(zero, p, b, base[p][b].shape) & im[p][b]
                            st = (1 << c.expmap2(info['plans'], p, b)).astype(float)
                            if c.hold_mode == 2:
                                old = self.thr[p][b] if self.thr is not None else np.full(st.shape, 1e9)
                                td[b] = np.where(zb, np.where(st * 2 <= old, st, old), 1e9)
                            else:
                                old = self.thr[p][b] if self.thr is not None else np.zeros(st.shape)
                                td[b] = np.where(zb, np.maximum(old, 0.75 * st), 0.0)
                        nt.append(td)
                    self.thr = nt
            info['V'] = V; info['intra'] = False; info['band'] = band; info['base'] = base; info['im'] = im; info['phi'] = phi; info['heal'] = heal
        self.hist.append(out); self.hist = self.hist[-2:]; self.t += 1
        return out, bits, info

    def prepare(self, ref, V, phi, heal=None):
        """prediction state for an inter frame -- identical in the encoder, every re-encoder and the decoder
        (the decoder gets V and phi from the stream and uses its own reference)."""
        c = self.c
        band = list(range(phi * self.Bw, min(self.nU, (phi + 1) * self.Bw))) if self.refresh else []
        guard = [u for u in (band[-1] + 1,) if u < self.nU] if band else []
        llg = [u for u in (band[-1] + 2,) if u < self.nU] if band else []
        cprev = phi * self.Bw * UNIT        # clean region of t-1 (luma columns) during this cycle
        base = []; im = []; keep = []
        zero = (np.abs(V).sum(-1) == 0)
        for p in range(3):
            P = motion.predict(ref[p], V, self.sx[p])
            Tp = c.ana(P)
            if self.clean and self.refresh and cprev > 0:
                xm = cprev // self.sx[p]
                Pc = motion.predict(ref[p], V, self.sx[p], xmax=xm, bmax=cprev // motion.BX)
                Tc = c.ana(Pc)
                cu = list(range(0, phi * self.Bw))
                for b in codec.BANDS:
                    m = self.unit_cols(p, b, cu); Tp[b] = np.where(m[None, :], Tc[b], Tp[b])
            bp = {}; mp = {}; kp = {}
            Td = c.ana(ref[p]) if self.refresh else None
            for b in codec.BANDS:
                intra_u = band + guard + (llg if b == 'LL' else [])
                m = ~self.unit_cols(p, b, intra_u)
                mp[b] = np.broadcast_to(m[None, :], Tp[b].shape).copy()
                if heal is not None:
                    # on-demand heal: whole luma rows [r0, r1) coded intra (slice-aligned), inside the fixed CBR budget
                    d = 2 if codec.LEVEL[b] == 1 else 4
                    mp[b][heal[0] // d:-(-heal[1] // d)] = False
                bp[b] = np.where(mp[b], Tp[b], 0)
                if self.refresh:
                    zb = self.zero_mask(zero, p, b, Tp[b].shape)
                    kp[b] = (Td[b], (~mp[b]) & zb)
            base.append(bp); im.append(mp); keep.append(kp)
        return base, im, keep, zero, band

    def umap(self):
        um = []
        for p in range(3):
            d = {}
            for b in codec.BANDS:
                lvl = codec.LEVEL[b]; w = (self.W if p == 0 else self.c.cw) >> lvl
                per = max(1, (UNIT if p == 0 else UNIT * self.c.cw // self.W) >> lvl)
                d[b] = np.minimum(np.arange(w) // per, self.nU - 1)
            um.append(d)
        return um

    def detect_phase(self, src):
        """read the refresh phase from the picture: the unit columns that read exactly as intra at a plan >= 1.
        Camera input (and fully still input) yields no confident phase: the encoder keeps its own counter."""
        c = self.c; Ts = [c.ana(x) for x in src]
        RD = c.readability(Ts, None, None, self.umap())
        ku = RD['ku']; score = (ku >= self.c.K // 4).mean(axis=0)   # per unit: reads as an intra picture
        best = None; bs = -1; second = -1
        for phi in range(self.cycle):
            us = list(range(phi * self.Bw, min(self.nU, (phi + 1) * self.Bw)))
            if not us: continue
            sc = min(score[u] for u in us)
            if sc > bs: second = bs; bs = sc; best = phi
            elif sc > second: second = sc
        if bs >= 0.8 and second < 0.5:
            self.lock = (self.t, best)

    def zero_mask(self, zero, p, b, shape):
        ys = (np.arange(shape[0]) * zero.shape[0]) // shape[0]; xs = (np.arange(shape[1]) * zero.shape[1]) // shape[1]
        return zero[ys][:, xs]

    def derive(self, phi):
        d1, d2 = self.hist[-1][0], self.hist[-2][0]
        V = motion.derive(d1, d2, bx=motion.BX, lam=self.lam, ry=self.ry)
        if self.clean and self.refresh and phi > 0:
            # clean-region rule for the derivation: a clean block's vector may only depend on data clean at t-1 AND
            # t-2. Blocks whose search window stays left of c2 (clean at t-2) keep their derived vector; the others
            # (the band refreshed at t-1, and the rim of c2) take the vector of the nearest such block to their
            # left in the same row (spatial extension, canonical), or zero at the cycle start.
            c1 = phi * self.Bw * UNIT; c2 = (phi - 1) * self.Bw * UNIT
            nb1 = -(-c1 // motion.BX) + 1
            okc = max(0, (c2 - motion.RX) // motion.BX - 1)       # block columns [0, okc) have fully clean windows
            for j in range(okc, min(nb1, V.shape[1])):
                V[:, j] = V[:, okc - 1] if okc > 0 else 0
        return V

    def vec_bits_per_slice(self, V):
        nby = V.shape[0]; per = self.S // motion.BY if self.S >= motion.BY else 1
        rows = np.array_split(np.arange(nby), self.H // self.S) if self.S < motion.BY else [np.arange(k * per, (k + 1) * per) for k in range(self.H // self.S)]
        return np.array([motion.vec_bits(V[r]) if len(r) else 0 for r in rows], float)


class Decoder:
    """a receiving decoder with its own reference; reads Q, plans, V, phi from the stream"""
    def __init__(self, enc):
        self.e = enc; self.hist = []
    def decode(self, info, lost=()):
        c = self.e.c; Q = info['Q']
        if lost:
            Q = [{b: v.copy() for b, v in Qp.items()} for Qp in Q]
            for k in lost:
                for p in range(3):
                    for b in codec.BANDS: Q[p][b][c.rows(b, k)] = 0
        if info['intra']:
            out = c.decode(Q, info['plans'], None, None)
        else:
            if not self.hist:          # joined mid-stream with nothing: mid-grey reference
                self.hist = [[np.full(s, c.mid, np.int64) for s in c.shapes]]
            base, im, _, _, _ = self.e.prepare(self.hist[-1], info['V'], info['phi'], info.get('heal'))
            out = c.decode(Q, info['plans'], base, im)
        self.hist.append(out); self.hist = self.hist[-2:]
        return out
