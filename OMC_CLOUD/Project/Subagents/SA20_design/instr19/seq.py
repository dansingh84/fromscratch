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
            c.stillmask = None
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
            if getattr(self, 'oracle_src', False) and len(self.hist) >= 1:
                V = motion.derive(src[0], self.hist[-1][0], bx=motion.BX, lam=self.lam, ry=self.ry)   # D4 ORACLE: source-searched (not exact)
            elif len(self.hist) >= 2: V = self.derive(phi)
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
                    for b in codec.BANDSP[p]:
                        zb = self.zero_mask(zero, p, b, base[p][b].shape)
                        rm[b] = np.where(zb & im[p][b], self.rho_still, c.rho)
                    rho_map.append(rm)
            c.stillmask = {(p, b): (self.zero_mask(zero, p, b, base[p][b].shape) & im[p][b]).astype(np.int64) for p in range(3) for b in codec.BANDSP[p]}
            if read and getattr(self, 'ccv', 0) and len(self.hist) >= 2:
                Vc, mix, zof, still, vbc = self.ccv_state(src[0], V, base, zero, im, phi, heal)
                c.stillmask = still
                plans, dd, exps, Q, bits = c.read2(src, mix, im, vb + vbc); out = c.decode(Q, plans, mix, im, exps, c.recoff)
                info = dict(plans=plans, over=0, Q=Q, exps=exps, l1d=dd, Vc=Vc); base = mix
            elif read:
                plans, Q, bits = c.read(src, base, im, vb); out = c.decode(Q, plans, base, im)
                info = dict(plans=plans, over=0, Q=Q)
            else:
                c.universal = self.universal
                hold = None
                zof = lambda p, b: self.zero_mask(zero, p, b, base[p][b].shape)
                ev = self.t in getattr(self, 'events', ())         # SA18 refinement event: hold lifted for one frame
                if self.still_hold and not ev:
                    hold = self.build_hold(zof, base, im)
                self.set_evcap(zof, im)
                if False:
                    for p in range(3):
                        hd = {}
                        for b in codec.BANDSP[p]:
                            zb = self.zero_mask(zero, p, b, base[p][b].shape) & im[p][b]
                            if c.hold_mode == 2:
                                sr = self.thr[p][b] if self.thr is not None else np.full(base[p][b].shape, 1e9)
                                hd[b] = np.where(zb, sr, 1e9)
                            else:
                                thr = self.thr[p][b] if self.thr is not None else np.zeros(base[p][b].shape)
                                hd[b] = np.where(zb, thr, -1.0)
                        hold.append(hd)
                c.stillmask = {(p, b): (self.zero_mask(zero, p, b, base[p][b].shape) & im[p][b]).astype(np.int64) for p in range(3) for b in codec.BANDSP[p]}
                A = (0.025 * self.bpp * self.W * self.S) if (getattr(self, 'ccv', False) and len(self.hist) >= 2) else 0.0   # SA18: V_c delta allowance
                er = c.emit_reading
                if A > 0: c.emit_reading = False      # pass 1 is internal under coarse-first: its plan must be the ENCODER's plan
                out, bits, info = c.code_frame(src, base=base, inter_mask=im, bpp=self.bpp, hdr_bits=vb + A, keep=keep,
                                               rho_map=rho_map, umap=self.umap() if self.universal else None, hold=hold)
                c.emit_reading = er
                if getattr(self, 'ccv', False) and len(self.hist) >= 2:
                    self._p1 = [o.copy() for o in out]; self._i1 = info
                    Vc, base, zof, still, vbc = self.ccv_state(out[0], V, base, zero, im, phi, heal)
                    hold = self.build_hold(zof, base, im) if (self.still_hold and not ev) else None
                    self.set_evcap(zof, im)
                    c.stillmask = still
                    out, bits, info = c.code_frame(src, base=base, inter_mask=im, bpp=self.bpp, hdr_bits=vb + vbc, keep=keep,
                                                   hold=hold, l1_plans=info['plans'], l1_alloc=info['chosen'])
                    exps_enc = info['exps']
                    if c.emit_reading:
                        # generation 1 emits exactly what the canonical reading of its own picture returns
                        plans_r, dd, exps_r, Qr, bits_r = c.read2(out, base, im, vb + vbc)
                        chk = c.decode(Qr, plans_r, base, im, exps_r, c.recoff)
                        assert all(np.array_equal(a, b) for a, b in zip(chk, out)), 'reading does not reproduce'
                        cum = np.cumsum(bits_r); lim = self.bpp * self.W * self.S * np.arange(1, len(bits_r) + 1)
                        info.update(plans=plans_r, l1d=dd, Q=Qr, exps_emit=exps_r, over=int((cum > lim + 1e-6).sum())); bits = bits_r
                    info['exps'] = exps_enc
                    info['Vc'] = Vc
                if self.still_hold:
                    # encoder-only state: a still coefficient that has had its one refinement is held until the
                    # source really changes by more than 3/4 of the step it was refined at
                    nt = []; na = {}
                    for p in range(3):
                        td = {}
                        for b in codec.BANDSP[p]:
                            zb = zof(p, b) & im[p][b]
                            em = np.repeat(info['exps'][(p, b)], self.S // codec.ROWDIV[(p, b)])[:, None] * np.ones((1, base[p][b].shape[1]), np.int64)
                            st = (1 << em).astype(float)
                            if c.hold_mode == 2:
                                old = self.thr[p][b] if self.thr is not None else np.full(st.shape, 1e9)
                                td[b] = np.where(zb, np.where(st * 2 <= old, st, old), 1e9)
                            else:
                                old = self.thr[p][b] if self.thr is not None else np.zeros(st.shape)
                                evm = self.event_mask(p, b, zb)
                                td[b] = np.where(zb, np.where(evm, 0.75 * st, (0.75 * st) if ev else np.maximum(old, 0.75 * st)), 0.0)
                                ag = self.ages[p][b] if getattr(self, 'ages', None) is not None else np.zeros(zb.shape, np.int64)
                                na.setdefault(p, {})[b] = np.where(zb, ag + 1, 0)
                        nt.append(td)
                    self.thr = nt; self.ages = [na.get(p, {}) for p in range(3)]
                    if getattr(self, 'noise_k', 0.0):
                        # SA18 noise gate: per (block, band) running mean of |source leaf - prediction leaf| on still cells
                        nz = []
                        for p in range(3):
                            Ts = c.ana(src[p], p); nd = {}
                            for b in codec.BANDSP[p]:
                                zb = zof(p, b) & im[p][b]; a = np.abs(Ts[b] - base[p][b]).astype(float)
                                h, w = a.shape; nby, nbx = V.shape[:2]
                                cid = ((np.arange(h) * nby) // h)[:, None] * nbx + ((np.arange(w) * nbx) // w)[None, :]
                                sm = np.bincount(cid.ravel(), (a * zb).ravel(), nby * nbx); ct = np.bincount(cid.ravel(), zb.ravel().astype(float), nby * nbx)
                                cm = np.where(ct > 0, sm / np.maximum(ct, 1), 0.0)[cid]
                                old = self.noise[p][b] if getattr(self, 'noise', None) is not None else cm
                                nd[b] = np.where(zb, old + (cm - old) / 4, 0.0)
                            nz.append(nd)
                        self.noise = nz
            info['V'] = V; info['intra'] = False; info['band'] = band; info['base'] = base; info['im'] = im; info['phi'] = phi; info['heal'] = heal
        self.hist.append(out); self.hist = self.hist[-2:]; self.t += 1
        return out, bits, info

    def ccv_state(self, ll_src, V, base, zero, im, phi, heal):
        """SA18 coarse-first state from a picture whose coarse bands are final (the encoder's pass-1 output, or a
        re-encoder's input): V_c, the mixed base, the context still masks, the extra vector bits."""
        c = self.c
        A = 0.025 * self.bpp * self.W * self.S
        if self.ccv == 2:
            c.fine_max = 2
            Vc = motion.ccv_ll2(self.hist[-1][0], pyr.analysis(ll_src, 2, 2)['LL'], V, R=2, bx=motion.BX)
        else:
            c.fine_max = 1
            Vc = motion.ccv2r(self.hist[-1][0], self.hist[-2][0], pyr.analysis(ll_src, 1, 1)['LL'], V, bx=motion.BX)
        Vc = motion.cap_delta(Vc, V, self.S, motion.BY, A)
        base_c, _, _, zero_c, _ = self.prepare(self.hist[-1], Vc, phi, heal)
        mix = [{b: (base_c[p][b] if codec.LEVEL[b] <= c.fine_max else base[p][b]) for b in codec.BANDSP[p]} for p in range(3)]
        zof = lambda p, b: self.zero_mask(zero_c if codec.LEVEL[b] <= c.fine_max else zero, p, b, mix[p][b].shape)
        still = {(p, b): (zof(p, b) & im[p][b]).astype(np.int64) for p in range(3) for b in codec.BANDSP[p]}
        return Vc, mix, zof, still, self.vec_bits_per_slice(Vc - V)

    def build_hold(self, zof, base, im):
        c = self.c; hold = []
        for p in range(3):
            hd = {}
            for b in codec.BANDSP[p]:
                zb = zof(p, b) & im[p][b]
                if c.hold_mode == 2:
                    sr = self.thr[p][b] if self.thr is not None else np.full(base[p][b].shape, 1e9)
                    hd[b] = np.where(zb, sr, 1e9)
                elif getattr(self, 'hold_abs', 0.0):
                    # SA18 error-driven still rule (owner direction): a still coefficient is re-coded only while the
                    # decoded value differs from the source by more than a FIXED threshold (pixel-domain level t_pix,
                    # gain-normalised per band) or than k x the cell's temporal noise; otherwise it is held. No schedule.
                    g = c.G[0 if p == 0 else 1][b]
                    thr = np.full(base[p][b].shape, self.hold_abs / np.sqrt(g))
                    if getattr(self, 'noise', None) is not None and getattr(self, 'noise_k', 0.0):
                        thr = np.maximum(thr, self.noise_k * self.noise[p][b])
                    hd[b] = np.where(zb, thr, -1.0)
                else:
                    thr = self.thr[p][b] if self.thr is not None else np.zeros(base[p][b].shape)
                    evm = self.event_mask(p, b, zb)
                    kn = getattr(self, 'noise_k', 0.0)
                    ethr = (kn * self.noise[p][b]) if (kn and getattr(self, 'noise', None) is not None) else -1.0
                    hd[b] = np.where(zb & ~evm, thr, np.where(evm, ethr, -1.0))
            hold.append(hd)
        return hold

    def set_evcap(self, zof, im):
        c = self.c
        if not getattr(self, 'ev_cap', False) or self.thr is None: c.evcap = None; return
        ec = []
        for p in range(3):
            d = {}
            for b in codec.BANDSP[p]:
                zb = zof(p, b) & im[p][b]; evm = self.event_mask(p, b, zb); th = self.thr[p][b]
                d[b] = np.where(evm & (th > 0), th / 0.75 / 2, -1.0)
            ec.append(d)
        c.evcap = ec

    def event_mask(self, p, b, zb):
        """SA18 still-age refinement events: a still coefficient is re-quantised once more when its still age (frames
        it has been still) reaches one of event_ages; otherwise held. Encoder-only state."""
        ea = getattr(self, 'event_ages', ())
        if not ea or getattr(self, 'ages', None) is None: return np.zeros_like(zb)
        return zb & np.isin(self.ages[p][b], ea)

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
            Tp = c.ana(P, p)
            if self.clean and self.refresh and cprev > 0:
                xm = cprev // self.sx[p]
                Pc = motion.predict(ref[p], V, self.sx[p], xmax=xm, bmax=cprev // motion.BX)
                Tc = c.ana(Pc, p)
                cu = list(range(0, phi * self.Bw))
                for b in codec.BANDSP[p]:
                    m = self.unit_cols(p, b, cu); Tp[b] = np.where(m[None, :], Tc[b], Tp[b])
            bp = {}; mp = {}; kp = {}
            Td = c.ana(ref[p], p) if self.refresh else None
            for b in codec.BANDSP[p]:
                intra_u = band + guard + (llg if b == 'LL' else [])
                m = ~self.unit_cols(p, b, intra_u)
                mp[b] = np.broadcast_to(m[None, :], Tp[b].shape).copy()
                if heal is not None:
                    # on-demand heal: whole luma rows [r0, r1) coded intra (slice-aligned), inside the fixed CBR budget
                    d = codec.ROWDIV[(p, b)]
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
            for b in codec.BANDSP[p]:
                lvl = codec.LEVEL[b]; w = (self.W if p == 0 else self.c.cw) >> lvl
                per = max(1, (UNIT if p == 0 else UNIT * self.c.cw // self.W) >> lvl)
                d[b] = np.minimum(np.arange(w) // per, self.nU - 1)
            um.append(d)
        return um

    def detect_phase(self, src):
        """read the refresh phase from the picture: the unit columns that read exactly as intra at a plan >= 1.
        Camera input (and fully still input) yields no confident phase: the encoder keeps its own counter."""
        c = self.c; Ts = [c.ana(x, i) for i, x in enumerate(src)]
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
                    for b in codec.BANDSP[p]: Q[p][b][c.rows(b, k, p)] = 0
        if info['intra']:
            out = c.decode(Q, info['plans'], None, None)
        else:
            if not self.hist:          # joined mid-stream with nothing: mid-grey reference
                self.hist = [[np.full(s, c.mid, np.int64) for s in c.shapes]]
            base, im, _, _, _ = self.e.prepare(self.hist[-1], info['V'], info['phi'], info.get('heal'))
            if info.get('Vc') is not None:
                # SA18: level <= fine_max bands predicted with the TRANSMITTED coarse-first field
                bc, _, _, _, _ = self.e.prepare(self.hist[-1], info['Vc'], info['phi'], info.get('heal'))
                base = [{b: (bc[p][b] if codec.LEVEL[b] <= c.fine_max else base[p][b]) for b in codec.BANDSP[p]} for p in range(3)]
            out = c.decode(Q, info['plans'], base, im, info.get('exps_emit'), c.recoff if info.get('Vc') is not None else 0)
        self.hist.append(out); self.hist = self.hist[-2:]
        return out
