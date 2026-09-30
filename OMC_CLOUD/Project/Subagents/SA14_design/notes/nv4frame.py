"""Frame driver for NEST v4: slices + IDQ + source-faithful one-pass choice + temporal (transmitted vectors
from decoded frames, rolling refresh by whole slices, exact hold, per band/slice mode) + generation-2 recovery.
Also decodes the open-loop indices with a plain clip (same slice structure) for the toward/away count."""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nv4, common14 as cm, nests
cm.nest = nests

def plan_rule(shape, D0):
    """ONE canonical plan: power-of-two steps from the synthesis-basis energy of each band at scalar D0,
    minimum step 2, coarsest low band 3 octaves finer, horizontal-only levels 3-4 2 octaves finer."""
    sh = cm.shifts_for(2, 3, shape, D0)
    out = {k: max(1, v) for k, v in sh.items()}
    out['top'] = max(1, out['top'] - 3)
    for k in list(out):
        if k != 'top' and k[0] >= 3:
            out[k] = max(1, out[k] - 2)
    return out

BS, RX, RY = 16, 8, 4
def motion(y1, y2):
    H, W = y1.shape; nb = (H // BS, W // BS)
    best = np.full(nb, np.inf); vy = np.zeros(nb, int); vx = np.zeros(nb, int)
    Hc, Wc = nb[0] * BS, nb[1] * BS; a = y1[:Hc, :Wc]
    pad = np.pad(y2, ((RY, RY), (RX, RX)), mode='edge')
    for dy in range(-RY, RY + 1):
        for dx in range(-RX, RX + 1):
            b = pad[RY + dy:RY + dy + Hc, RX + dx:RX + dx + Wc]
            sad = np.abs(a - b).reshape(nb[0], BS, nb[1], BS).sum(axis=(1, 3)) + (abs(dy) + abs(dx))
            m = sad < best; best = np.where(m, sad, best); vy = np.where(m, dy, vy); vx = np.where(m, dx, vx)
    return vy, vx

def expand(v, H, W, sy, sx):
    """block field -> per-pixel field for a plane subsampled by (sy, sx)."""
    by = np.minimum(np.arange(H) * sy // BS, v.shape[0] - 1); bx = np.minimum(np.arange(W) * sx // BS, v.shape[1] - 1)
    return v[by][:, bx]

def mc(ref, vy, vx, sy, sx):
    H, W = ref.shape
    py = expand(vy, H, W, sy, sx) // sy; px = expand(vx, H, W, sy, sx) // sx
    yy = np.clip(np.arange(H)[:, None] + py, 0, H - 1); xx = np.clip(np.arange(W)[None, :] + px, 0, W - 1)
    return ref[yy, xx]

def band_mask(pix, shp):
    H, W = pix.shape; h, w = shp
    return pix[(np.arange(h) * H) // h][:, (np.arange(w) * W) // w]

def cost(q):
    a = np.abs(q); return np.where(a == 0, 0.3, 2.5 + 2 * np.log2(1 + a))

def slices(H, S):
    first = H % S or S
    b = [0, first]
    while b[-1] < H: b.append(b[-1] + S)
    return list(zip(b[:-1], b[1:]))

class PlaneState:
    def __init__(self): self.leaf = {}; self.top = {}; self.srcleaf = {}; self.srctop = {}

def code_plane(X, dep, t, D0, S, st, p, zp, refresh_slices, lo_v, hi_v, gen2=True):
    H, W = X.shape; mid = (lo_v + hi_v) // 2
    sl = slices(H, S); Y = np.empty_like(X); Yc = np.empty_like(X)
    syms = {}; sh = plan_rule((S, W), D0)
    tops = [np.full(W, mid, np.int64), np.full(W // 2, mid, np.int64)]
    topsc = [t_.copy() for t_ in tops]; topsp = [t_.copy() for t_ in tops]
    same = True; tw = np.zeros(2, int)
    for k, (r0, r1) in enumerate(sl):
        Xs = X[r0:r1]; R = r1 - r0
        lo = np.full(Xs.shape, lo_v, np.int64); hi = np.full(Xs.shape, hi_v, np.int64)
        shk = plan_rule((R, W), D0) if R != S else sh
        lv, Ltop, vals = nv4.plain(Xs, tops)
        P = nv4.Params()
        P.sh = shk
        intra = t == 0 or k in refresh_slices
        if intra:
            P.cp = [{n: np.zeros_like(v) for n, v in d.items()} for d in lv]; P.cp_top = None; hold = None; hold_top = None
        else:
            plv, pL, _ = nv4.plain(p[r0:r1], topsp)
            z = zp[r0:r1]
            P.cp = [{n: np.where(band_mask(z, v.shape), st.leaf[k][l][n], plv[l][n]) for n, v in d.items()} for l, d in enumerate(lv)]
            P.cp_top = np.where(band_mask(z, pL.shape), st.top[k], pL)
            hold = [{n: (v == st.srcleaf[k][l][n]) & band_mask(z, v.shape) for n, v in d.items()} for l, d in enumerate(lv)]
            hold_top = (Ltop == st.srctop[k]) & band_mask(z, Ltop.shape)
            # per band mode: intra where its open-loop indices are cheaper
            for l in range(nv4.NL):
                for n in lv[l]:
                    qi = nv4.Qdz(lv[l][n], shk[(l, n)]); qe = nv4.Qdz(lv[l][n] - P.cp[l][n], shk[(l, n)])
                    if cost(qi).sum() < cost(np.where(hold[l][n], 0, qe)).sum():
                        P.cp[l][n] = np.zeros_like(P.cp[l][n]); hold[l][n] = np.zeros_like(hold[l][n])
        q0 = nv4.quantise(lv, Ltop, P, hold)
        qt0 = nv4.quantise_top(Ltop, P, lo, hi, q0, hold_top)
        # clip reference with the same open-loop indices and the same tops
        leaf0 = [{n: P.cp[l][n] + (q0[l][n] << P.sh[(l, n)]) for n in q0[l]} for l in range(nv4.NL)]
        _, (tlo0, thi0) = nv4.windows(nv4.upd(leaf0), lo, hi)
        Pc = nv4.Params(); Pc.sh = P.sh; Pc.cp = P.cp
        Pc.cp_top = np.clip(P.cp_top if P.cp_top is not None else tlo0, tlo0, thi0)
        nv4.CLIP = True
        yc, _, _, _, L1c = nv4.synth(q0, qt0, Pc, lo - (1 << 30), hi + (1 << 30), topsc)
        nv4.CLIP = False
        Yc[r0:r1] = np.clip(yc, lo_v, hi_v)
        ys, q, qt, leaf, L1last = nv4.synth(q0, qt0, P, lo, hi, tops, src=vals, srctop=Ltop)
        Y[r0:r1] = ys
        dn = np.abs(ys - Xs); dc = np.abs(Yc[r0:r1] - Xs); m = ys != Yc[r0:r1]
        tw += [int((m & (dn < dc)).sum()), int((m & (dn > dc + 1)).sum())]
        for l in range(nv4.NL):
            for n in q[l]:
                syms.setdefault((l, n), []).append(q[l][n].ravel())
        syms.setdefault('top', []).append(qt.ravel())
        if gen2:
            q2, qt2 = nv4.recover(ys, P, lo, hi, tops)
            same &= all(np.array_equal(q[l][n], q2[l][n]) for l in range(nv4.NL) for n in q[l]) and np.array_equal(qt, qt2)
        # state for the next frame (hold) and next slice (tops)
        st.leaf[k] = leaf; st.top[k] = nv4.last_top(q, qt, P, lo, hi); st.srcleaf[k] = lv; st.srctop[k] = Ltop
        tops = [ys[-1].copy(), L1last.copy()]
        topsc = [Yc[r1 - 1].copy(), L1c.copy()]
        if p is not None:
            topsp = [p[r1 - 1].copy(), nv4.last_low1(p[r0:r1], topsp)]
    bits = sum(nv4.entropy_bits(np.concatenate(v)) for v in syms.values())
    return Y, Yc, bits, same, tw
