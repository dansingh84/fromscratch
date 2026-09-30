"""NEST v4 temporal model, CONTINUOUS vertical transform (no slice boundary in the transform; slices are only
rate/packet units), leaf-reading 5/3, IDQ over the full window (no rails), source-faithful choice in one
decision pass + the decoder pass.  Per plane: inter per band in the coefficient domain, band prediction =
previous frame's leaves where the block vector is zero (exact hold) else plain analysis of the MC prediction;
vectors from decoded frames (encoder), transmitted; per band x 16-row stripe mode by cost; rolling refresh:
one band of rows per frame, overlapping the previous band by OVL rows, clean-region vectors clamped (vy <= 0).
Supports 4:2:2 and 4:2:0.  Records per-plane stats; the stream is kept for a separate loss (A5) decode."""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nv4, nv4frame as F, common14 as cm
OVL = 20

def read_frames(cell, nfr, f0=0, still=False, fmt420=False, grade=False):
    out = []
    for t in range(nfr):
        p, dep = cm.read_frame(cell, f0 if still else f0 + t)
        if grade:
            p = [np.clip((x - 200) * 5 // 2, 0, 1023) if i == 0 else np.clip(512 + (x - 512) * 2, 0, 1023) for i, x in enumerate(p)]
        if fmt420:
            p = [p[0]] + [(c[0::2] + c[1::2] + 1) >> 1 for c in p[1:]]
        out.append(p)
    return out, dep

def band_rows(shape, H, r0, r1):
    """bool mask over a band grid for coefficients whose pixel row lies in [r0, r1)."""
    h = shape[0]; rows = (np.arange(h) * H) // h
    return np.repeat(((rows >= r0) & (rows < r1))[:, None], shape[1], 1)

class St:
    def __init__(s): s.leaf = None; s.top = None; s.srcleaf = None; s.srctop = None

def code_frame(frames_t, dec_prev, dec_prev2, t, D0, states, dep, fmt420, stream, gen2=True):
    M = (1 << dep) - 1
    H0, W0 = frames_t[0].shape
    if t >= 2:
        vy, vx = F.motion(dec_prev[0], dec_prev2[0])
    else:
        vy = np.zeros((H0 // F.BS, W0 // F.BS), int); vx = vy.copy()
    # rolling refresh band (luma rows) and clean-region clamp
    band_h = -(-H0 // 8); a = (t % 8) * band_h
    rb0, rb1 = max(0, a - OVL), min(H0, a + band_h)
    blk_row = np.arange(vy.shape[0])[:, None] * F.BS
    if t >= 1:
        vy = np.where(blk_row < rb0, np.minimum(vy, 0), vy)
    mvbits = 0 if t == 0 else nv4.entropy_bits(vy * 64 + vx)
    ys = []; bits = mvbits; same = True; tw = []; recs = []
    for i, X in enumerate(frames_t):
        H, W = X.shape; sy = 2 if (fmt420 and i > 0) else 1; sx = 2 if i > 0 else 1
        st = states[i]
        lo = np.zeros(X.shape, np.int64); hi = np.full(X.shape, M, np.int64); mid = M // 2
        tops = [np.full(W, mid, np.int64), np.full(W // 2, mid, np.int64)]
        sh = F.plan_rule(X.shape, D0)
        lv, Ltop, vals = nv4.plain(X, tops)
        P = nv4.Params(); P.sh = sh
        hold = None; hold_top = None
        if t == 0:
            P.cp = [{n: np.zeros_like(v) for n, v in d.items()} for d in lv]; P.cp_top = None
        else:
            p = F.mc(dec_prev[i], vy, vx, sy, sx)
            zb = (vy == 0) & (vx == 0)
            z = F.expand(zb.astype(int), H, W, sy, sx).astype(bool)
            plv, pL, _ = nv4.plain(p, tops)
            r0, r1 = rb0 // sy, -(-rb1 // sy)
            P.cp = []; hold = []
            for l, d in enumerate(lv):
                c = {}; hd = {}
                for n, v in d.items():
                    zm = F.band_mask(z, v.shape); rm = band_rows(v.shape, H, r0, r1)
                    c[n] = np.where(rm, 0, np.where(zm, st.leaf[l][n], plv[l][n]))
                    hd[n] = (v == st.srcleaf[l][n]) & zm & ~rm
                P.cp.append(c); hold.append(hd)
            zm = F.band_mask(z, pL.shape); rm = band_rows(pL.shape, H, r0, r1)
            P.cp_top = np.where(rm, np.iinfo(np.int64).min // 4, np.where(zm, st.top, pL))
            hold_top = (Ltop == st.srctop) & zm & ~rm
            # per band x 16-row stripe mode (intra where cheaper)
            for l, d in enumerate(lv):
                for n, v in d.items():
                    qi = F.cost(nv4.Qdz(v, sh[(l, n)])); qe = F.cost(np.where(hold[l][n], 0, nv4.Qdz(v - P.cp[l][n], sh[(l, n)])))
                    hs = max(1, (16 * v.shape[0]) // H)
                    for s0 in range(0, v.shape[0], hs):
                        if qi[s0:s0 + hs].sum() < qe[s0:s0 + hs].sum():
                            P.cp[l][n][s0:s0 + hs] = 0; hold[l][n][s0:s0 + hs] = False
        P.fixed = hold; P.fixed_top = hold_top
        q0 = nv4.quantise(lv, Ltop, P, hold)
        qt0 = nv4.quantise_top(Ltop, P, lo, hi, q0, hold_top)
        # plain-clip reference with the same open-loop indices
        leaf0 = [{n: P.cp[l][n] + (q0[l][n] << P.sh[(l, n)]) for n in q0[l]} for l in range(nv4.NL)]
        _, (tlo0, thi0) = nv4.windows(nv4.upd(leaf0), lo, hi)
        Pc = nv4.Params(); Pc.sh = P.sh; Pc.cp = P.cp; Pc.cp_top = np.clip(P.cp_top if P.cp_top is not None else tlo0, tlo0, thi0)
        nv4.CLIP = True; yc, _, _, _, _ = nv4.synth(q0, qt0, Pc, lo - (1 << 30), hi + (1 << 30), tops); nv4.CLIP = False
        yc = np.clip(yc, 0, M)
        y, q, qt, leaf, _ = nv4.synth(q0, qt0, P, lo, hi, tops, src=vals, srctop=Ltop)
        dn = np.abs(y - X); dc = np.abs(yc - X); m = y != yc
        tw.append((int((m & (dn < dc)).sum()), int((m & (dn > dc + 1)).sum())))
        bits += sum(nv4.entropy_bits(q[l][n]) for l in range(nv4.NL) for n in q[l]) + nv4.entropy_bits(qt)
        if gen2:
            q2, qt2 = nv4.recover(y, P, lo, hi, tops)
            same &= all(np.array_equal(q[l][n], q2[l][n]) for l in range(nv4.NL) for n in q[l]) and np.array_equal(qt, qt2)
        st.leaf = leaf; st.top = nv4.last_top(q, qt, P, lo, hi); st.srcleaf = lv; st.srctop = Ltop
        stream.append((i, q, qt, P, (vy.copy(), vx.copy()), (rb0, rb1)))
        ys.append(y); recs.append(yc)
    return ys, bits, same, tw

def run(cell, D0, nfr=12, still=False, fmt420=False, grade=False, write=None, verbose=True, gen2=True):
    frames, dep = read_frames(cell, nfr, still=still, fmt420=fmt420, grade=grade)
    states = [St() for _ in range(3)]
    dec = []; rows = []; streams = []
    for t in range(nfr):
        stream = []
        ys, bits, same, tw = code_frame(frames[t], dec[t - 1] if t else None, dec[t - 2] if t >= 2 else None, t, D0, states, dep, fmt420, stream, gen2)
        streams.append(stream); dec.append(ys)
        W, H = frames[t][0].shape[1], frames[t][0].shape[0]
        ps = [cm.psnr(frames[t][i], ys[i], dep) for i in range(3)]
        oob = sum(int(((y < 0) | (y > (1 << dep) - 1)).sum()) for y in ys)
        chg = [int((ys[i] != dec[t - 1][i]).sum()) for i in range(3)] if t else None
        rows.append({'t': t, 'bpp': bits / (W * H), 'psnr': ps, 'oob': oob, 'g2': same, 'toward_away': tw, 'changed': chg})
        if verbose:
            print(f"{cell}{' 420' if fmt420 else ''} D0={D0} f{t:2d} bpp={bits/(W*H):.4f} PSNR Y/Cb/Cr={ps[0]:.2f}/{ps[1]:.2f}/{ps[2]:.2f} oob={oob} g2={same} "
                  f"toward/away>1 Y{tw[0]} Cb{tw[1]} Cr{tw[2]} changed={chg}", flush=True)
    if write:
        with open(write, 'wb') as f:
            for fr in dec:
                for p in fr: p.astype('<u2').tofile(f)
    return rows, dec, streams, frames, dep
