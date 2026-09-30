"""Temporal model on NEST v3 (leaf-reading 5/3 + rails + injective dequantisation), whole-frame transform.
Inter per band in the coefficient domain; band prediction = previous frame's leaves where the block's
vector is zero (exact hold), plain analysis of the motion-compensated prediction elsewhere.
Vectors: derived by the encoder from decoded frames only (backward match y(t-1) -> y(t-2), applied
forward), transmitted.  Rolling refresh: one eighth of the rows intra per frame.
Generation 2 recovers every index from the decoded picture with the same (canonical) parameters."""
import sys, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA14_design/notes')
import nv3, common14 as cm, t_v3_intra as tv
BS, RX, RY = 16, 8, 4

def plane_shapes(shape):
    lv, L = nv3.plain(np.zeros(shape, np.int64))
    return [{n: v.shape for n, v in d.items()} for d in lv], L.shape

def band_mask(pix, shp):
    """nearest-sample a pixel-level bool map onto a band grid."""
    H, W = pix.shape; h, w = shp
    iy = (np.arange(h) * H) // h; ix = (np.arange(w) * W) // w
    return pix[iy][:, ix]

def motion(y1, y2):
    """luma block vectors from decoded frames: block B of y1 best matches y2 at B+v."""
    H, W = y1.shape; nb = (H // BS, W // BS)
    best = np.full(nb, np.inf); vy = np.zeros(nb, int); vx = np.zeros(nb, int)
    Hc, Wc = nb[0] * BS, nb[1] * BS
    a = y1[:Hc, :Wc].astype(np.int64)
    pad = np.pad(y2, ((RY, RY), (RX, RX)), mode='edge').astype(np.int64)
    for dy in range(-RY, RY + 1):
        for dx in range(-RX, RX + 1):
            b = pad[RY + dy:RY + dy + Hc, RX + dx:RX + dx + Wc]
            sad = np.abs(a - b).reshape(nb[0], BS, nb[1], BS).sum(axis=(1, 3)) + (abs(dy) + abs(dx))  # tiny bias to 0
            m = sad < best; best = np.where(m, sad, best); vy = np.where(m, dy, vy); vx = np.where(m, dx, vx)
    return vy, vx

def mc(ref, vy, vx, sx=1):
    H, W = ref.shape; out = np.empty_like(ref)
    pad = np.pad(ref, ((RY, RY), (RX, RX)), mode='edge')
    for by in range(vy.shape[0] + (1 if H % BS else 0)):
        for bx in range(vx.shape[1] + (1 if (W * sx) % BS else 0)):
            iy = min(by, vy.shape[0] - 1); ix = min(bx, vx.shape[1] - 1)
            dy, dx = vy[iy, ix], vx[iy, ix] // sx
            y0, x0 = by * BS, bx * (BS // sx)
            y1_, x1_ = min(H, y0 + BS), min(W, x0 + BS // sx)
            if y0 >= H or x0 >= W:
                continue
            out[y0:y1_, x0:x1_] = pad[RY + y0 + dy:RY + y1_ + dy, RX + x0 + dx:RX + x1_ + dx]
    return out

class Plane:
    def __init__(self, shape, sh, dep, lov, hiv):
        self.sh = sh; self.lo = np.full(shape, lov, np.int64); self.hi = np.full(shape, hiv, np.int64)
        self.prev_leaf = None; self.prev_top = None; self.prev_src = None

def params_for(pl, t, p, zero_pix, shp):
    P = nv3.Params(); P.sh = pl.sh
    bshapes, tshape = shp
    if t == 0 or pl.prev_leaf is None:
        P.cp = [{n: np.zeros(s, np.int64) for n, s in d.items()} for d in bshapes]; P.cp_top = None
        return P
    plv, pL = nv3.plain(p)
    H = zero_pix.shape[0]
    stripe = np.zeros(zero_pix.shape, bool); k = t % 8
    stripe[(k * H) // 8:((k + 1) * H) // 8] = True
    P.cp = []
    for l, d in enumerate(bshapes):
        c = {}
        for n, s in d.items():
            z = band_mask(zero_pix, s); r = band_mask(stripe, s)
            c[n] = np.where(r, 0, np.where(z, pl.prev_leaf[l][n], plv[l][n]))
        P.cp.append(c)
    z = band_mask(zero_pix, tshape); r = band_mask(stripe, tshape)
    P.cp_top = np.where(r, np.iinfo(np.int64).min // 4, np.where(z, pl.prev_top, pL))
    P.top_intra = r
    return P

def top_pred_fix(P):
    return P

def run(cell, D0, nfr=12, still=False, gen2=True, write=None, f0=0):
    path, W, H, fmt, dep = cm.CELLS[cell]
    M = (1 << dep) - 1
    frames = [cm.read_frame(cell, (f0 if still else f0 + t))[0] for t in range(nfr)]
    shapes = [frames[0][i].shape for i in range(3)]
    sx = [1, 2 if fmt == '422' else 1, 2 if fmt == '422' else 1]
    shp = [plane_shapes(s) for s in shapes]
    pls = [Plane(s, tv.shifts(s, D0), dep, 0, M) for s in shapes]
    pls2 = [Plane(s, pls[i].sh, dep, 0, M) for i, s in enumerate(shapes)]
    dec = []; stats = []
    for t in range(nfr):
        if t >= 2:
            vy, vx = motion(dec[t - 1][0], dec[t - 2][0])
        else:
            vy = np.zeros((shapes[0][0] // BS, shapes[0][1] // BS), int); vx = vy.copy()
        mvbits = 0 if t == 0 else nv3.entropy_bits(vy * 64 + vx)
        ys = []; ys2 = []; bits = mvbits; same = True
        for i in range(3):
            X = frames[t][i]; pl = pls[i]
            if t == 0:
                p = np.zeros_like(X); zp = np.zeros(X.shape, bool)
            else:
                p = mc(dec[t - 1][i], vy, vx, sx[i])
                zb = (vy == 0) & (vx == 0)
                zp = np.repeat(np.repeat(zb, BS, 0), BS // sx[i], 1)
                zp = np.pad(zp, ((0, max(0, X.shape[0] - zp.shape[0])), (0, max(0, X.shape[1] - zp.shape[1]))), mode='edge')[:X.shape[0], :X.shape[1]]
            P = params_for(pl, t, p, zp, shp[i])
            global PLAIN_CP
            PLAIN_CP = [{n: v.copy() for n, v in d.items()} for d in P.cp] if t else None
            k = t % 8; stripe = np.zeros(X.shape, bool); stripe[(k * X.shape[0]) // 8:((k + 1) * X.shape[0]) // 8] = True
            zp = zp & ~stripe      # no hold inside the refresh stripe
            hold = None
            if pl.prev_src is not None:
                sl, sL = nv3.plain(X); pv, pL = pl.prev_src
                hold = [{n: (sl[l][n] == pv[l][n]) & band_mask(zp, sl[l][n].shape) for n in sl[l]} for l in range(nv3.NL)]
                hold.append(None); hold = hold[:nv3.NL]
                hold_top = (sL == pL) & band_mask(zp, sL.shape)
                hd = {l: hold[l] for l in range(nv3.NL)}; hd['top'] = hold_top
                hold = hd
            q, qt = nv3.encode3(X, P, pl.lo, pl.hi, hold=hold, z16=Z16)
            if MODES and t > 0:
                P0 = nv3.Params(); P0.sh = P.sh
                P0.cp = [{n: np.zeros_like(v) for n, v in d.items()} for d in P.cp]; P0.cp_top = np.full(P.cp_top.shape, np.iinfo(np.int64).min // 4)
                q0, qt0 = nv3.encode3(X, P0, pl.lo, pl.hi, z16=Z16)
                nch = 0
                for l in range(nv3.NL):
                    for n in q[l]:
                        a = cost(q[l][n]); b = cost(q0[l][n])
                        rows = q[l][n].shape[0]; hs = max(1, (16 * rows) // X.shape[0])
                        for r0 in range(0, rows, hs):
                            if b[r0:r0 + hs].sum() < a[r0:r0 + hs].sum():
                                P.cp[l][n][r0:r0 + hs] = 0; nch += 1
                q, qt = nv3.encode3(X, P, pl.lo, pl.hi, hold=hold, z16=Z16)
            y, leaf = nv3.decode(q, qt, P, pl.lo, pl.hi)
            bits += nv3.bits3(q, qt)
            pl.prev_leaf = leaf; pl.prev_top = top_value(q, qt, P, pl); pl.prev_src = nv3.plain(X)
            ys.append(y)
            if MODECHECK and t >= 2:
                # mode readability: flip each band-stripe's mode, recover, compare the stripe's index cost
                import copy
                nbad = ntot = 0
                for l in range(nv3.NL):
                    for n in q[l]:
                        rows = q[l][n].shape[0]; hs = max(1, (16 * rows) // X.shape[0])
                        for r0 in range(0, rows, hs * 4):
                            if (PLAIN_CP[l][n][r0:r0 + hs] == 0).all(): continue
                            Pf = copy.copy(P); Pf.cp = [{k: v.copy() for k, v in d.items()} for d in P.cp]
                            intra = (P.cp[l][n][r0:r0 + hs] == 0).all()
                            Pf.cp[l][n][r0:r0 + hs] = PLAIN_CP[l][n][r0:r0 + hs] if intra else 0
                            qf, _ = nv3.recover3(y, Pf, pl.lo, pl.hi)
                            ntot += 1; nbad += int(cost(qf[l][n][r0:r0 + hs]).sum() <= cost(q[l][n][r0:r0 + hs]).sum())
                MODESTAT.append((t, i, nbad, ntot))
            if gen2:
                q2, qt2 = nv3.recover3(y, P, pl.lo, pl.hi)
                same &= all(np.array_equal(q[l][n], q2[l][n]) for l in range(nv3.NL) for n in q[l]) and np.array_equal(qt, qt2)
        dec.append(ys)
        ps = [cm.psnr(frames[t][i], ys[i], dep) for i in range(3)]
        oob = sum(int(((y < 0) | (y > M)).sum()) for y in ys)
        chg = sum(int((ys[i] != dec[t - 1][i]).sum()) for i in range(3)) if t else -1
        stats.append((t, bits / (W * H), ps, oob, same, chg))
        print(f"{cell} D0={D0} f{t:2d} bpp(entropy)={bits/(W*H):.4f} PSNR Y/Cb/Cr={ps[0]:.2f}/{ps[1]:.2f}/{ps[2]:.2f} oob={oob} gen2_same={same} changed_vs_prev={chg}", flush=True)
    if write:
        np.concatenate([np.concatenate([p.ravel() for p in f]) for f in dec]).astype('<u2').tofile(write)
    return stats

MODES = 1
MODECHECK = 0
MODESTAT = []
PLAIN_CP = None
import os
Z16 = int(os.environ.get("Z16", "9"))
def cost(q):
    a = np.abs(np.where(np.abs(q) >= nv3.RAIL, 1, q))
    return np.where(a == 0, 0.3, 2.5 + 2 * np.log2(1 + a))

def top_value(q, qt, P, pl):
    """the top leaf value the decoder used (for the next frame's hold prediction)."""
    leaf = nv3.leaves(q, P)
    _, (tlo, thi) = nv3.windows(nv3.upd_values(leaf, nv3.railmask(q)), pl.lo, pl.hi)
    pred = np.clip(P.cp_top if P.cp_top is not None else tlo, tlo, thi)
    return nv3.idq_r(pred, qt, P.sh['top'], tlo, thi)

if __name__ == '__main__':
    cell = sys.argv[1]; D0 = int(sys.argv[2]); nfr = int(sys.argv[3]); still = sys.argv[4] == 'still'
    out = sys.argv[5] if len(sys.argv) > 5 else None
    run(cell, D0, nfr, still, write=out)
