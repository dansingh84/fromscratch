#!/usr/bin/env python3
"""SA12 v2 sequence model: the FINAL legal pyramid (exact sums + sigma, 2/10 H and V, V context from decoded rows
above, 3V x 5H, short last slice) with per-band temporal prediction from ONE reference frame.
 * vectors: canonical, from DECODED frames only: 16x16 luma blocks matched y[t-1] -> y[t-2] (+-8 full pel);
   constant-motion projection; zero preferred unless the match is better by > 1 code/pixel; frame 1: zero.
 * alpha = 1 on inter slices; refresh: slice k intra when (k - t) mod 8 == 0 (t >= 1); frame 0 all intra.
 * steps FIXED per sequence (Qf) -> identical lattices frame to frame (the still-area fixed point, S5.335).
 * inter dead zone: rounding offset TH/16 on inter slices (encoder freedom; lattice points still forced).
Not modelled: CBR packets (fixed Qf instead), half-pel, OBMC, alpha field, refresh barrier.
usage: seq.py src W H f0 nfr sh Qf tag [--still] [--th 4] [--gen2]"""
import sys, os, math, json, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hf
from hf import fd, hsplit, vsplit, hmerge, vmerge, pred, vpred, dint, Coder, _cur, _slice0, _sig, SUM
kH, kV, L, NV = 's10', 's10a', 5, 3
BELOW = int(os.environ.get('SEQ_BELOW', '1'))
READ = int(os.environ.get('SEQ_READ', '0'))
ABOVE_REF = int(os.environ.get('SEQ_ABOVE_REF', '0'))   # inter slices: context ABOVE also from the MC reference
CONT = int(os.environ.get('SEQ_CONT', '0')); CW = float(os.environ.get('SEQ_CW', '1'))
SSCALE = float(os.environ.get('SEQ_SSCALE', '1'))
SELFREAD = int(os.environ.get('SEQ_SELFREAD', '0'))   # gen 1: emit intra for a slice whenever intra coding of its reconstruction reproduces it   # fine global step multiplier (rate matching)
CLEAN = int(os.environ.get('SEQ_CLEAN', '0'))
CL_VEC = int(os.environ.get('SEQ_CL_VEC', '1')); CL_OBMC = int(os.environ.get('SEQ_CL_OBMC', '1')); CL_ROWS = int(os.environ.get('SEQ_CL_ROWS', '1'))   # decomposition toggles   # clean-region (barrier) rules for mid-stream convergence; implies sweep
CRESHAPE = int(os.environ.get('SEQ_CRESHAPE', '0'))   # intra slices: chroma level-1 step x sqrt2 + encoder offset 11/16
SWEEP = int(os.environ.get('SEQ_SWEEP', '0')); ZEROMV = int(os.environ.get('SEQ_ZEROMV', '0')); CBW = int(os.environ.get('SEQ_CBW', '16'))   # encoder-only error continuation   # joining encoder: intra iff intra reproduces the input slice; no own schedule

HIST = []; LASTBITS = [None]; HASHES = {}; INTRA_FLAGS = {}
def ref_pyr(M, nv):
    out = {}; A = M
    for lev in range(1, L + 1):
        _cur[:] = [lev, 'H']; Lc, dH = hsplit(A)
        if lev <= nv:
            _cur[:] = [lev, 'V']; LL, dL = vsplit(Lc)
            _cur[:] = [lev, 'H']; e = dH - pred(Lc, kH)
            _cur[:] = [lev, 'V']; HL, dE = vsplit(e)
            out[lev] = dict(LL=LL, dL=dL, HL=HL, dE=dE); A = LL
        else:
            _cur[:] = [lev, 'H']; e = dH - pred(Lc, kH); out[lev] = dict(e=e); A = Lc
    out[L + 1] = dict(LL=A); return out

def rec_t(C, lev, nv, A, Alo, Ahi, ctx, R):
    if lev > L:
        p = R[L + 1]['LL'] if R else 0
        return C.qc((lev, 'LL'), A - p, Alo - p, Ahi - p) + p
    _cur[:] = [lev, 'H']; Lc_s, dH_s = hsplit(A); Llo, _ = hsplit(Alo); Lhi, _ = hsplit(Ahi)
    r = R[lev] if R else None
    if lev <= nv:
        _cur[:] = [lev, 'V']; LL_s, dL_s = vsplit(Lc_s); LLlo, _ = vsplit(Llo); LLhi, _ = vsplit(Lhi)
        LL = rec_t(C, lev + 1, nv, LL_s, LLlo, LLhi, ctx, R)
        _cur[:] = [lev, 'V']
        bl = R['below'][lev] if (R and R.get('below')) else None
        p = vpred(LL, kV, ctx[lev][0] if ctx else None, bl[0] if bl else None)
        if r: p = p + (r['dL'] - vpred(r['LL'], kV, R['ctx'][lev][0] if R.get('ctx') else None, bl[0] if bl else None))
        lo, hi = dint(LL, Llo[:, 0::2], Lhi[:, 0::2], Llo[:, 1::2], Lhi[:, 1::2], _sig(LL.shape) if SUM else 0)
        dL = C.qc((lev, 'LH'), dL_s - p, lo - p, hi - p) + p
        Lc = vmerge(LL, dL)
    else:
        Lc = rec_t(C, lev + 1, nv, Lc_s, Llo, Lhi, ctx, R)
    _cur[:] = [lev, 'H']; pH = pred(Lc, kH)
    hlo, hhi = dint(Lc, Alo[..., 0::2], Ahi[..., 0::2], Alo[..., 1::2], Ahi[..., 1::2], _sig(Lc.shape) if SUM else 0)
    elo, ehi = hlo - pH, hhi - pH; e_s = dH_s - pH
    if lev <= nv:
        _cur[:] = [lev, 'V']; HL_s, dE_s = vsplit(e_s); HLlo, _ = vsplit(elo); HLhi, _ = vsplit(ehi)
        ph = r['HL'] if r else 0
        HL = C.qc((lev, 'HL'), HL_s - ph, HLlo - ph, HLhi - ph) + ph
        p2 = vpred(HL, kV, ctx[lev][1] if ctx else None, bl[1] if bl else None)
        if r: p2 = p2 + (r['dE'] - vpred(r['HL'], kV, R['ctx'][lev][1] if R.get('ctx') else None, bl[1] if bl else None))
        lo2, hi2 = dint(HL, elo[:, 0::2], ehi[:, 0::2], elo[:, 1::2], ehi[:, 1::2], _sig(HL.shape) if SUM else 0)
        dE = C.qc((lev, 'HH'), dE_s - p2, lo2 - p2, hi2 - p2) + p2
        e = vmerge(HL, dE)
    else:
        pe = r['e'] if r else 0
        e = C.qc((lev, 'H'), e_s - pe, elo - pe, ehi - pe) + pe
    _cur[:] = [lev, 'H']; return hmerge(Lc, e + pH)

def vectors(y1, y2, bs=16, R=8, ylim=None):
    H, W = y1.shape; nby, nbx = H // bs, W // bs
    A = y1[:nby * bs, :nbx * bs].astype(np.int64)
    best = None; V = np.zeros((nby, nbx, 2), np.int64); z = None
    for dy in range(-R, R + 1):
        for dx in range(-R, R + 1):
            ys = np.clip(np.arange(nby * bs) + dy, 0, (H if ylim is None else ylim) - 1); xs = np.clip(np.arange(nbx * bs) + dx, 0, W - 1)
            sad = np.abs(A - y2[ys][:, xs]).reshape(nby, bs, nbx, bs).sum((1, 3))
            if dy == 0 and dx == 0: z = sad
            if best is None: best = sad.copy(); V[:] = (dy, dx); continue
            m = sad < best; best[m] = sad[m]; V[m] = (dy, dx)
    V[z <= best + bs * bs] = 0            # prefer zero unless better by > 1 code / pixel
    return V

OBMC = int(os.environ.get('SEQ_OBMC', '1'))
def mc_obmc(ref, V, bs, cx, ylim=None):
    """overlapped-block MC: each sample = bilinear blend (weights in 1/256, integer) of the predictions made with the
    vectors of the 4 nearest block centres.  Weights sum to 256 -> a flat field is reproduced exactly."""
    H, W = ref.shape; nby, nbx = V.shape[:2]; bw = bs // cx
    yc = (np.arange(H) + 0.5) / bs - 0.5; xc = (np.arange(W) + 0.5) / bw - 0.5
    y0 = np.clip(np.floor(yc).astype(int), 0, nby - 1); x0 = np.clip(np.floor(xc).astype(int), 0, nbx - 1)
    y1 = np.clip(y0 + 1, 0, nby - 1); x1 = np.clip(x0 + 1, 0, nbx - 1)
    fy = np.clip(np.rint((yc - np.floor(yc)) * 16), 0, 16).astype(np.int64); fx = np.clip(np.rint((xc - np.floor(xc)) * 16), 0, 16).astype(np.int64)
    fy[yc < 0] = 0; fx[xc < 0] = 0; fy[yc > nby - 1] = 16; fx[xc > nbx - 1] = 16
    Y, X = np.meshgrid(np.arange(H), np.arange(W), indexing='ij')
    acc = np.zeros((H, W), np.int64)
    for (by, wy) in ((y0, 16 - fy), (y1, fy)):
        for (bx, wx) in ((x0, 16 - fx), (x1, fx)):
            v = V[by[:, None], bx[None, :]]
            ys = np.clip(Y + v[..., 0], 0, (H if ylim is None else ylim) - 1)
            if cx == 1:
                p = ref[ys, np.clip(X + v[..., 1], 0, W - 1)]
            else:
                dx = v[..., 1]; xa = np.clip(X + np.floor_divide(dx, 2), 0, W - 1); xb = np.clip(xa + (dx % 2), 0, W - 1)
                p = (ref[ys, xa] + ref[ys, xb] + 1) >> 1
            acc += (wy[:, None] * wx[None, :]) * p
    return (acc + 128) >> 8
def mc(ref, V, bs, cx, ylim=None):
    if OBMC: return mc_obmc(ref, V, bs, cx, ylim)
    return mc_block(ref, V, bs, cx)
def mc_block(ref, V, bs, cx):
    """ref plane; V luma vectors (full pel); cx = horizontal subsampling. Half-sample chroma: rounded average."""
    H, W = ref.shape; out = np.empty_like(ref); bw = bs // cx
    for by in range(V.shape[0]):
        for bx in range(V.shape[1]):
            dy, dx = int(V[by, bx, 0]), int(V[by, bx, 1])
            y0, x0 = by * bs, bx * bw
            ys = np.clip(np.arange(y0, min(y0 + bs, H)) + dy, 0, H - 1)
            if cx == 1 or dx % 2 == 0:
                xs = np.clip(np.arange(x0, min(x0 + bw, W)) + dx // cx, 0, W - 1); out[y0:y0 + bs, x0:x0 + bw] = ref[ys][:, xs]
            else:
                xa = np.clip(np.arange(x0, min(x0 + bw, W)) + (dx - 1) // 2, 0, W - 1); xb = np.clip(xa + 1, 0, W - 1)
                out[y0:y0 + bs, x0:x0 + bw] = (ref[ys][:, xa] + ref[ys][:, xb] + 1) >> 1
    # rows/cols beyond whole blocks: zero motion
    nb_y, nb_x = V.shape[0] * bs, V.shape[1] * bw
    out[nb_y:, :] = ref[nb_y:, :]; out[:, nb_x:] = ref[:, nb_x:]
    return out

def code_frame(planes, refs, V, t, sh, steps_by_plane, lo, hi, th, Qin=None, phase=None, Vc=None):
    recs, Qs, bits = [], [], {}
    for pi, P in enumerate(planes):
        H, W = P.shape; cx = planes[0].shape[1] // W
        M = mc(refs[pi], V, 16, cx) if refs is not None else None
        ns_ = -(-H // sh); G = -(-ns_ // 8); Mc = None
        if CLEAN and refs is not None and phase is not None and phase > 0:
            Vm = Vc if CL_OBMC else np.where((np.arange(V.shape[0]) * 16 // sh // G < phase)[:, None, None], Vc, V)
            Mc = mc(refs[pi], Vm, 16, cx, ylim=(phase * G * sh) if CL_ROWS else None)     # clean slices: clean data only
        rec = np.zeros((H, W), np.int64); Qp = []
        ns = -(-H // sh)
        for k in range(ns):
            r0 = k * sh; rows = min(sh, H - r0); nv = min(NV, int(math.log2(rows)))
            X = P[r0:r0 + rows][None].astype(np.int64); LO = np.full(X.shape, lo, np.int64); HI = np.full(X.shape, hi, np.int64)
            if CONT and k > 0 and Qin is None:
                # encoder-only: continue the previous slice's LOW-FREQUENCY error into this slice's top rows (fading),
                # so the error field has no step at the slice edge.  Zero when the input reproduces (generation >= 2).
                e = (rec[r0 - 2:r0] - P[r0 - 2:r0]).astype(float).mean(0)
                kern = np.ones(CBW // (planes[0].shape[1] // W)) ; kern /= kern.sum()
                elf = np.convolve(np.pad(e, (len(kern) // 2, len(kern) - 1 - len(kern) // 2), mode='edge'), kern, mode='valid')
                wr = CW * np.clip((CONT - np.arange(rows)) / (CONT + 1.0), 0, None)[:, None]
                X = X + np.rint(wr * elf[None, :]).astype(np.int64)[None]
            if k > 0: _slice0[0] = k - 1; ctx = hf.ctx_of(rec[r0 - sh:r0][None], L, nv, kH)
            else: ctx = None
            _slice0[0] = k
            pt = (t % 8) if phase is None else phase
            clean = CLEAN and Mc is not None and (k // -(-ns // 8)) < pt
            if SWEEP or CLEAN: sched = (k // -(-ns // 8)) == pt          # contiguous top-down sweep, cycle 8
            else: sched = (k - t) % 8 == 0
            intra = (refs is None) or ((not READ) and sched)
            if READ and refs is not None and Qin is None:
                Ci = Coder('enc', steps_by_plane[pi][rows], th=7)
                Zi = rec_t(Ci, 1, nv, X, np.full(X.shape, lo, np.int64), np.full(X.shape, hi, np.int64), ctx, None)
                intra = bool(np.array_equal(Zi, X))
            if pi == 0: INTRA_FLAGS[(t, k)] = intra
            R = None
            if not intra:
                if clean: M, Msave = Mc, M
                R = ref_pyr(M[r0:r0 + rows][None], nv)
                if k > 0:                      # the reference's own context rows (same rule as the current slice)
                    _slice0[0] = k - 1; R['ctx'] = hf.ctx_of(M[r0 - sh:r0][None].astype(np.int64), L, nv, kH)
                if ABOVE_REF and k > 0: ctx = R['ctx']          # both sides of the boundary predict from the shared reference
                if BELOW and r0 + rows + sh <= H:   # context BELOW the slice: the MC reference's rows below
                    _slice0[0] = k + 1; R['below'] = hf.ctx_below(M[r0 + rows:r0 + rows + sh][None].astype(np.int64), L, nv, kH)
                if clean: M = Msave
                _slice0[0] = k
            st = steps_by_plane[pi][rows]
            hf.THMAP.clear()
            if CRESHAPE and intra and pi > 0:
                st = {kk: (max(1, int(round(v * 2 ** 0.5))) if kk[0] == 1 else v) for kk, v in st.items()}
                hf.THMAP[1] = 11
            C = Coder('enc', st, th=7 if intra else th) if Qin is None else Coder('dec', st, Qin[pi][k], th=7 if intra else th)
            rec[r0:r0 + rows] = rec_t(C, 1, nv, X if Qin is None else 0 * X, LO, HI, ctx, R)[0]
            if SELFREAD and not READ and not intra and Qin is None:
                hf.THMAP.clear(); Zr = rec[r0:r0 + rows][None].copy()
                Cs = Coder('enc', steps_by_plane[pi][rows], th=7)
                Zs = rec_t(Cs, 1, nv, Zr, np.full(Zr.shape, lo, np.int64), np.full(Zr.shape, hi, np.int64), ctx, None)
                if np.array_equal(Zs, Zr):
                    intra = True; C = Cs
                    if pi == 0: INTRA_FLAGS[(t, k)] = True
            Qp.append(C.Q)
            import hashlib
            HASHES.setdefault(t, {})[(pi, k)] = hashlib.md5(b''.join([str(kk).encode() + np.ascontiguousarray(C.Q[kk], dtype=np.int32).tobytes() for kk in sorted(C.Q)]) + (b'I' if intra else b'P')).hexdigest()
            for kk, v in C.Q.items(): bits.setdefault((pi, intra, rows, kk), []).append(v.ravel())
        recs.append(rec); Qs.append(Qp)
    nb = sum(hf.ent(np.concatenate(v)) for v in bits.values())
    LASTBITS[0] = bits
    return recs, Qs, nb

def load_seq(path, W, H, f0, n, still):
    return [hf.load(path, W, H, f0 if still else f0 + i, '422') for i in range(n)]

def steps_for(W, sh, Qf, H):
    out = {}
    for rows in {sh, H % sh or sh}:
        nv = min(NV, int(math.log2(rows)))
        w = hf.weights(rows, W, L, nv, kH, kV); ks = hf.keys(L, nv); w[ks[-1]] *= 4.0
        out[rows] = {k: max(1, int(round(SSCALE * 2.0 ** round(Qf - 0.5 * math.log2(w[k]))))) for k in ks}
    return out

def run(frames, sh, Qf, th, lo=0, hi=1023):
    W = frames[0][0].shape[1]; H = frames[0][0].shape[0]
    spp = [steps_for(p.shape[1], sh, Qf, p.shape[0]) for p in frames[0]]
    recs, bpf, allQ, Vs = [], [], [], []
    ns = -(-H // sh); G = -(-ns // 8); phase_of = {}
    for t, F in enumerate(frames):
        if t == 0: V = None
        elif t == 1: V = np.zeros(((H // 16), (W // 16), 2), np.int64)
        else: V = vectors(recs[-1][0], recs[-2][0]) if not ZEROMV else np.zeros(((H // 16), (W // 16), 2), np.int64)
        if CLEAN and V is not None and t >= 2 and not ZEROMV:
            pw = (t % 8) if not READ else (((phase_of[t - 1] + 1) % 8) if (t - 1) in phase_of else None)
            if pw == 0 and CL_VEC:      # cycle wrap: frame t-2 had not yet refreshed the last group -> do not read those rows
                ylim2 = 7 * G * sh
                Vw = vectors(recs[-1][0], recs[-2][0], ylim=ylim2)
                for by in range(V.shape[0]):
                    V[by] = Vw[by] if (by + 1) * 16 <= ylim2 else 0
        # phase: own count (gen 1) or learned from the previous frame's detected refresh group (joining encoder)
        if not READ: p = t % 8
        else: p = ((phase_of[t - 1] + 1) % 8) if (t - 1) in phase_of else None
        Vc = None
        if CLEAN and V is not None and p is not None and p > 0 and not ZEROMV and t >= 2:
            Vc = np.zeros_like(V); bpr = sh // 16 if sh >= 16 else 1
            V2 = vectors(recs[-1][0], recs[-2][0], ylim=max(1, (p - 1) * G * sh)) if p >= 2 else None
            for by in range(V.shape[0]):
                g = (by * 16 // sh) // G
                if g <= p - 2 and V2 is not None: Vc[by] = V2[by]       # both t-1 and t-2 clean there
                # g == p-1 (refreshed at t-1): zero; blocks outside the clean region: zero (canonical)
        elif CLEAN and V is not None and p is not None and p > 0: Vc = np.zeros_like(V)
        if CLEAN and not CL_VEC and V is not None and p is not None and p > 0: Vc = V.copy()
        if CLEAN and Vc is not None and V is not None:          # clean blocks use Vc in the frame's own V (transmitted)
            for by in range(V.shape[0]):
                if ((by * 16 // sh) // G) < p: V[by] = Vc[by]
        R, Q, nb = code_frame(F, recs[-1] if t else None, V, t, sh, spp, lo, hi, th, phase=p, Vc=Vc)
        if READ and t > 0:
            full = [g for g in range(8) if all(INTRA_FLAGS.get((t, k), False) for k in range(g * G, min(ns, (g + 1) * G)))]
            if full:
                want = ((phase_of[t - 1] + 1) % 8) if (t - 1) in phase_of else None
                phase_of[t] = want if want in full else full[0]
        recs.append(R); bpf.append(nb / (W * H)); allQ.append(Q); Vs.append(V)
        HIST.append({str(kk): np.unique(np.concatenate(v), return_counts=True) for kk, v in LASTBITS[0].items()})
        print('  frame', t, 'bpp %.3f' % bpf[-1], flush=True)
    return recs, bpf, allQ, Vs

if __name__ == '__main__':
    a = sys.argv[1:]; still = '--still' in a; g2 = '--gen2' in a
    th = int(a[a.index('--th') + 1]) if '--th' in a else 4
    src, W, H, f0, n, sh, Qf, tag = a[0], int(a[1]), int(a[2]), int(a[3]), int(a[4]), int(a[5]), float(a[6]), a[7]
    frames = load_seq(src, W, H, f0, n, still)
    recs, bpf, Q, Vs = run(frames, sh, Qf, th)
    SCR = os.environ.get('SCR', '/tmp')
    dp = os.path.join(SCR, tag + '.dec.yuv'); sp = os.path.join(SCR, tag + '.src.yuv')
    np.concatenate([np.concatenate([p.astype('<u2').ravel() for p in R]) for R in recs]).tofile(dp)
    np.concatenate([np.concatenate([p.astype('<u2').ravel() for p in F]) for F in frames]).tofile(sp)
    oor = sum(int(((p < 0) | (p > 1023)).sum()) for R in recs for p in R)
    json.dump({str(t): {'%d_%d' % pk: h for pk, h in d.items()} for t, d in HASHES.items()}, open(tag + '.hash.json', 'w'))
    ps = [[(lambda m: 99.0 if m == 0 else 10 * math.log10(1023 ** 2 / m))(float(((R[i] - F[i]) ** 2).mean())) for i in range(3)] for R, F in zip(recs, frames)]
    chg = [[float((recs[t][i] != recs[t - 1][i]).mean()) for i in range(3)] for t in range(1, len(recs))]
    res = dict(tag=tag, Qf=Qf, th=th, bpp=bpf, psnr=ps, changed=chg, oor=oor)
    if g2:
        recs2, _, Q2, V2 = run([[p.astype(np.int64) for p in R] for R in recs], sh, Qf, th)
        same = all(np.array_equal(a_, b_) for R1, R2 in zip(recs, recs2) for a_, b_ in zip(R1, R2))
        sameQ = all(np.array_equal(Q[t][pi][k][kk], Q2[t][pi][k][kk]) for t in range(len(Q)) for pi in range(3)
                    for k in range(len(Q[t][pi])) for kk in Q[t][pi][k])
        sameV = all((a_ is None and b_ is None) or np.array_equal(a_, b_) for a_, b_ in zip(Vs, V2))
        res['gen2'] = dict(picture=same, indices=sameQ, vectors=sameV)
    import pickle; pickle.dump(HIST[:len(recs)], open(tag + '.hist.pkl', 'wb'))
    json.dump({str(t): {'%d_%d' % pk: h for pk, h in d.items()} for t, d in HASHES.items()}, open(tag + '.hash.json', 'w'))
    json.dump(res, open(tag + '.seq.json', 'w'))
    print(json.dumps({k: v for k, v in res.items() if k in ('tag', 'Qf', 'oor', 'gen2')}), 'mean bpp f2+ %.3f' % np.mean(bpf[2:]))
