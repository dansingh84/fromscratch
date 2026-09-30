# SA19 TPP ("two-past pyramid") sequence model. Own sequence layer; per-frame coding uses the codec.Codec
# component (continuous pair pyramid, leaf-interval legality, plan ladder, per-slice exact CBR, canonical emission).
# Temporal: value-domain coefficient prediction with BAND-SPLIT references:
#   coarse bands (LEVEL > FINE) predicted from P1 = OBMC(D(t-1), V1)
#   fine bands   (LEVEL <= FINE) predicted from F  = (w*P1 + (16-w)*P2 + 8) >> 4, P2 = OBMC(D(t-2), V2)
#   w: per-pixel continuous field from the TRANSMITTED vectors only: 16 where the OBMC block vector is zero (still ->
#   exact hold keeps working), WF elsewhere, bilinear across block centres (no block step).
# V1: history field D(t-1) vs D(t-2) (every encoder derives it; transmitted). V2 = 2*V1 (constant velocity, no bits)
# or refined on decoded data (v2mode).
import numpy as np, codec, motion, pyr

class TPP:
    def __init__(self, W, H, bpp, tabs, S=8, fuse=0, wf=8, fine=2, v2mode='cv', still='hold1', bx=64, lam=4, ztol=2,
                 wk=0.0, catchpad=0.25, fusec=None, split=0.0, ecsq=0.0, cheap=0, ro=0, auto=0, **kw):
        motion.BX = bx; motion.ZTOL = ztol; self.lam = lam
        self.c = codec.Codec(W, H, S=S, tabs=tabs, **kw)
        self.auto = auto
        self.c.ecsq = ecsq; self.c.read_cheapest = bool(cheap); self.c.ro_inter = ro
        if ro: self.c.fine_max = 2
        self.W, self.H, self.S, self.bpp = W, H, S, bpp
        self.fuse, self.wf, self.fine, self.v2mode, self.still = fuse, wf, fine, v2mode, still
        self.hist = []; self.t = 0; self.thr = None; self.sx = [1, 2, 2]
        self.split = split; self.c_ecsq = ecsq; self.prevsl = None; self.log = []; self.fusec = (wk == 0) if fusec is None else bool(fusec); self.wk = wk; self.catchpad = catchpad; self.pexp = []; self.cstate = None; self.lastpad = 0.0

    # ---------------- prediction state (identical at encoder, re-encoder, decoder) ----------------
    def wfield(self, V, H, W, sx):
        """per-pixel weight of P1 (0..16): 16 on still blocks, wf on moving ones, bilinear between block centres"""
        nby, nbx = V.shape[:2]; bx = motion.BX // sx; by = motion.BY
        blk = np.where(np.abs(V).sum(-1) == 0, 16, self.wf).astype(np.int64)
        cy = (np.arange(H) + 0.5) / by - 0.5; cx = (np.arange(W) + 0.5) / bx - 0.5
        iy0 = np.clip(np.floor(cy).astype(int), 0, nby - 1); iy1 = np.clip(iy0 + 1, 0, nby - 1)
        ix0 = np.clip(np.floor(cx).astype(int), 0, nbx - 1); ix1 = np.clip(ix0 + 1, 0, nbx - 1)
        wy = np.round((cy - np.floor(cy)) * 16).astype(np.int64); wy = np.where((cy < 0) | (cy > nby - 1), 0, wy)
        wx = np.round((cx - np.floor(cx)) * 16).astype(np.int64); wx = np.where((cx < 0) | (cx > nbx - 1), 0, wx)
        out = np.zeros((H, W), np.int64)
        for IY, WY in ((iy0, 16 - wy), (iy1, wy)):
            for IX, WX in ((ix0, 16 - wx), (ix1, wx)):
                out += WY[:, None] * WX[None, :] * blk[IY][:, IX]
        # a pixel is fully single-reference only if ALL contributing blocks are still (exact hold)
        allstill = np.ones((H, W), bool)
        for IY in (iy0, iy1):
            for IX in (ix0, ix1):
                allstill &= (blk[IY][:, IX] == 16)
        w = (out + 128) >> 8
        return np.where(allstill, 16, np.minimum(w, 15) if self.wf < 16 else w)

    def prepare(self, V1, V2, twopast):
        c = self.c; base = []; im = []; zero = (np.abs(V1).sum(-1) == 0)
        for p in range(3):
            P1 = motion.predict(self.hist[-1][p], V1, self.sx[p]); T1 = c.ana(P1, p)
            tp = twopast and (p == 0 or self.fusec)     # luma-only fusion keeps DDR at ~25 bit/sample
            if tp:
                P2 = motion.predict(self.hist[-2][p], V2, self.sx[p])
                w = self.wfield(V1, *P1.shape, self.sx[p])
                if self.wk > 0: w = np.maximum(w, self.wiener(P1, P2, p))
                F = (w * P1 + (16 - w) * P2 + 8) >> 4
                TF = c.ana(F, p)
            bp = {}; mp = {}
            for b in codec.BANDSP[p]:
                bp[b] = TF[b] if (tp and codec.LEVEL[b] <= self.fine) else T1[b]
                mp[b] = np.ones(bp[b].shape, bool)
            base.append(bp); im.append(mp)
        return base, im, zero

    def wiener(self, P1, P2, p):
        """per-pixel weight of P1 (8..16) from decoded data only: w2 = s2 / (s2 + wk * M2), M2 = 8x8 box mean of (P1-P2)^2,
        s2 = quantisation-noise variance of the two references from their emitted level-1 steps (per slice row);
        block values bilinearly interpolated (continuous field)."""
        H, W = P1.shape; by, bx = 8, (8 if p == 0 else 4)
        d = (P1 - P2).astype(np.float64) ** 2
        M2 = d.reshape(H // by, by, W // bx, bx).mean(axis=(1, 3))
        e1 = np.repeat(self.pexp[-1][p], self.S)[:H]; e2 = np.repeat(self.pexp[-2][p], self.S)[:H]
        s2r = ((2.0 ** e1) ** 2 + (2.0 ** e2) ** 2) / 12.0
        s2 = s2r.reshape(H // by, by).mean(axis=1)[:, None]
        w2 = s2 / (s2 + self.wk * M2 + 1e-9)
        wb = np.clip(np.round(16 * (1 - np.minimum(w2, 0.5))), 8, 16)
        # bilinear up-sampling of block values (continuous, integer weights as in the OBMC)
        nby, nbx = wb.shape
        cy = (np.arange(H) + 0.5) / by - 0.5; cx = (np.arange(W) + 0.5) / bx - 0.5
        iy0 = np.clip(np.floor(cy).astype(int), 0, nby - 1); iy1 = np.clip(iy0 + 1, 0, nby - 1)
        ix0 = np.clip(np.floor(cx).astype(int), 0, nbx - 1); ix1 = np.clip(ix0 + 1, 0, nbx - 1)
        fy = np.clip(cy - np.floor(cy), 0, 1); fx = np.clip(cx - np.floor(cx), 0, 1)
        out = ((1 - fy)[:, None] * ((1 - fx)[None, :] * wb[iy0][:, ix0] + fx[None, :] * wb[iy0][:, ix1]) +
               fy[:, None] * ((1 - fx)[None, :] * wb[iy1][:, ix0] + fx[None, :] * wb[iy1][:, ix1]))
        return np.round(out).astype(np.int64)

    def zero_mask(self, zero, shape):
        ys = (np.arange(shape[0]) * zero.shape[0]) // shape[0]; xs = (np.arange(shape[1]) * zero.shape[1]) // shape[1]
        return zero[ys][:, xs]

    def vectors(self):
        d1, d2 = self.hist[-1][0], self.hist[-2][0]
        V1 = motion.derive(d1, d2, bx=motion.BX, lam=self.lam)
        if self.v2mode == 'chain':
            # V1 is the history field u (D(t-1)(x) ~ D(t-2)(x+u)); P1 reads D(t-1) at x+V1, so the matching D(t-2) content
            # sits at x + V1 + u(landing block of x+V1): chained, no constant-velocity assumption, no bits
            nby, nbx = V1.shape[:2]; by, bx = motion.BY, motion.BX
            cy = (np.arange(nby) * by + by // 2)[:, None] + V1[..., 0]; cx = (np.arange(nbx) * bx + bx // 2)[None, :] + V1[..., 1]
            ly = np.clip(cy // by, 0, nby - 1); lx = np.clip(cx // bx, 0, nbx - 1)
            V2 = V1 + V1[ly, lx]
        else:
            V2 = 2 * V1
        return V1, V2

    # ---------------- one frame ----------------
    def encode(self, src, read=False):
        c = self.c
        if self.t == 0:
            c.stillmask = None
            r = self.try_read(src, None, None, 0.0) if (self.auto and not read) else None
            if read:
                plans, Q, bits = c.read(src, None, None); out = c.decode(Q, plans, None, None); info = dict(plans=plans, over=0, Q=Q)
            elif r is not None:
                plans, Q, bits = r; out = c.decode(Q, plans, None, None); info = dict(plans=plans, over=0, Q=Q, hop=True)
            else:
                out, bits, info = c.code_frame(src, bpp=self.bpp)
            info['intra'] = True
        else:
            if len(self.hist) >= 2: V1, V2 = self.vectors()
            else:
                V1 = np.zeros((self.H // motion.BY, self.W // motion.BX, 2), np.int64); V2 = V1
            twopast = bool(self.fuse) and len(self.hist) >= 2
            base, im, zero = self.prepare(V1, V2, twopast)
            vb = self.vec_bits(V1)
            c.stillmask = {(p, b): self.zero_mask(zero, base[p][b].shape).astype(np.int64) for p in range(3) for b in codec.BANDSP[p]}
            r = self.try_read(src, base, im, vb) if (self.auto and not read) else None
            if read:
                plans, Q, bits = c.read(src, base, im, vb); out = c.decode(Q, plans, base, im, ro=c.ro_inter); info = dict(plans=plans, over=0, Q=Q)
            elif r is not None:
                plans, Q, bits = r; out = c.decode(Q, plans, base, im, ro=c.ro_inter); info = dict(plans=plans, over=0, Q=Q, hop=True)
                if self.still in ('hold1', 'catch'): info['exps'] = {pb: np.array([c.E[k][pb] for k in plans]) for pb in c.al.pb}; self.update_hold(zero, base, info)
            else:
                hold = self.build_hold(zero, base) if self.still in ('hold1', 'catch') else None
                catch = self.build_catch(zero, base) if self.still == 'catch' else None
                c.catch = catch
                if self.split > 0 and self.prevsl is not None:
                    sh = self.prevsl / self.prevsl.sum(); c.alloc = (1 - self.split) / len(sh) + self.split * sh
                out, bits, info = c.code_frame(src, base=base, inter_mask=im, bpp=self.bpp, hdr_bits=vb, hold=hold)
                c.catch = None; c.alloc = None
                if self.still in ('hold1', 'catch'): self.update_hold(zero, base, info, catch)
                info['catchframe'] = catch is not None
            info['intra'] = False; info['V1'] = V1; info['V2'] = V2; info['twopast'] = twopast
        # emitted level-1 exponent per slice and plane (the decoder knows it from the stream) -> noise scale for fusion
        pl = info['plans']; self.pexp.append([np.array([c.E[k][(p, 'HL1')] for k in pl]) for p in range(3)]); self.pexp = self.pexp[-2:]
        B = self.bpp * self.W * self.H; self.lastpad = max(0.0, 1.0 - float(np.sum(bits)) / B)
        info['pad'] = self.lastpad
        if not info.get('intra'): self.prevsl = np.asarray(bits, float).copy()
        self.hist.append(out); self.hist = self.hist[-2:]; self.t += 1
        return out, bits, info

    def build_hold(self, zero, base):
        hold = []
        for p in range(3):
            hd = {}
            for b in codec.BANDSP[p]:
                zb = self.zero_mask(zero, base[p][b].shape)
                thr = self.thr[p][b] if self.thr is not None else np.zeros(base[p][b].shape)
                hd[b] = np.where(zb, thr, -1.0)
            hold.append(hd)
        return hold

    def try_read(self, src, base, im, vb):
        """SA19 hop rule (encoder, one predetermined choice per frame): if the input reads canonically at plans whose every
        band step is >= 2 (only a decoded picture does; camera input has odd leaves) and the reading fits the prefix bound,
        emit the reading (the picture is reproduced exactly); otherwise encode normally. [SA19 22:50: the 'all steps >= 2' test was
        dropped: gen 1 legitimately uses step 1 on some bands at fine plans; camera input only reads losslessly and never fits]"""
        c = self.c
        try:
            plans, Q, bits = c.read(src, base, im, vb)
        except AssertionError:
            return None
        B = self.bpp * self.W * self.S
        if (np.cumsum(bits) > B * np.arange(1, len(bits) + 1) + 1e-6).any(): return None
        return plans, Q, bits

    def build_catch(self, zero, base):
        """SA19 still rule, part 2 (encoder-only): ONE catch-up of the whole still set. Fires in a frame when the previous
        frame left >= catchpad of the pipe as padding (free budget exists) and still coefficients exist that were refined
        once but never caught up. In that frame every such coefficient may be re-coded, but only if the slice's step is at
        least one octave finer than the step it was refined at (otherwise it stays held and waits); after the frame it is
        marked caught. A caught coefficient changes again only if the source moves by more than 3/4 of its step."""
        if self.thr is None or self.lastpad < self.catchpad: return None
        out = []; anyc = False
        for p in range(3):
            d = {}
            for b in codec.BANDSP[p]:
                zb = self.zero_mask(zero, base[p][b].shape)
                st = self.thr[p][b] / 0.75                      # step it was refined at (0 = never)
                cs = self.cstate[p][b] if self.cstate is not None else np.zeros(st.shape, bool)
                m = zb & (st > 0) & ~cs
                d[b] = np.where(m, st, 0.0); anyc |= bool(m.any())
            out.append(d)
        return out if anyc else None

    def update_hold(self, zero, base, info, catch=None):
        """encoder-only still state (element from SA17 hold1, used as the first TPP still rule): a still coefficient that
        has been refined once is held until the source moves by more than 3/4 of the step it was refined at"""
        nt = []; ncs = {}
        for p in range(3):
            td = {}
            for b in codec.BANDSP[p]:
                zb = self.zero_mask(zero, base[p][b].shape)
                em = np.repeat(info['exps'][(p, b)], self.S // codec.ROWDIV[(p, b)])[:, None] * np.ones((1, base[p][b].shape[1]), np.int64)
                st = (1 << em).astype(float)
                old = self.thr[p][b] if self.thr is not None else np.zeros(st.shape)
                if catch is not None:
                    # coefficients that were offered the catch-up and whose slice step was >= 1 octave finer took it
                    took = (catch[p][b] > 0) & (st * 2 <= catch[p][b])
                    td[b] = np.where(zb, np.where(took, 0.75 * st, np.maximum(old, 0.75 * st)), 0.0)
                    cs = self.cstate[p][b] if self.cstate is not None else np.zeros(st.shape, bool)
                    ncs.setdefault(p, {})[b] = zb & (cs | took)
                else:
                    td[b] = np.where(zb, np.maximum(old, 0.75 * st), 0.0)
                    if self.cstate is not None: ncs.setdefault(p, {})[b] = zb & self.cstate[p][b]
            nt.append(td)
        self.thr = nt
        if ncs: self.cstate = [ncs[p] for p in range(3)]

    def vec_bits(self, V):
        nby = V.shape[0]; per = max(1, self.S // motion.BY)
        return np.array([motion.vec_bits(V[k * per:(k + 1) * per]) for k in range(self.H // self.S)], float)
