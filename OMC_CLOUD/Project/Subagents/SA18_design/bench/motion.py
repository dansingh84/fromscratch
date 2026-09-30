# SA17 motion: canonical vectors from DECODED history (every encoder derives the same field from D(t-1), D(t-2);
# the field is transmitted, the decoder only reads it). Integer luma vectors, per BX x BY block.
# OBMC: bilinear block-centre weights (integer, shift 8) so no block edge exists in the prediction.
import numpy as np

BX, BY = 32, 8
ZTOL = 2
RX, RY = 16, 4

def derive(d1, d2, bx=BX, by=BY, rx=RX, ry=RY, zero_bias=1.02, lam=0):
    if lam > 0: return derive_reg(d1, d2, bx, by, rx, ry, lam)
    """d1 = D(t-1) luma, d2 = D(t-2) luma. For each block of d1 find u with d1(x) ~ d2(x+u); constant velocity
    => predict D(t)(x) from D(t-1)(x+u). ties / near ties go to the zero vector (still areas stay still)."""
    H, W = d1.shape; nby, nbx = H // by, W // bx
    a = d1.astype(np.int64)
    pad = np.pad(d2.astype(np.int64), ((ry, ry), (rx, rx)), mode='edge')
    best = np.full((nby, nbx), np.iinfo(np.int64).max); V = np.zeros((nby, nbx, 2), np.int64)
    blk = lambda z: z.reshape(nby, by, nbx, bx).sum(axis=(1, 3))
    sad0 = blk(np.abs(a - d2.astype(np.int64)))
    for dy in range(-ry, ry + 1):
        for dx in range(-rx, rx + 1):
            s = blk(np.abs(a - pad[ry + dy:ry + dy + H, rx + dx:rx + dx + W]))
            take = s < best
            best = np.where(take, s, best); V[take] = (dy, dx)
    still = sad0 * 100 <= best * int(zero_bias * 100)
    V[still] = 0
    return V

def vec_bits(V):
    """Exp-Golomb of the difference to the left neighbour (row-wise), both components."""
    d = V.copy(); d[:, 1:] -= V[:, :-1]
    z = np.where(d > 0, 2 * d - 1, -2 * d)
    return int((2 * np.floor(np.log2(z + 1)) + 1).sum())

def _shift(ref, dy, dx):
    H, W = ref.shape
    ys = np.clip(np.arange(H) + dy, 0, H - 1); xs = np.clip(np.arange(W) + dx, 0, W - 1)
    return ref[ys][:, xs]

def predict(ref, V, sx=1, xmax=None, bmax=None):
    """OBMC prediction of one plane. sx=2 for 4:2:2 chroma (vectors halved: half-sample by 2-tap average).
    xmax: clean-region barrier -- reference columns are clamped to < xmax (per pixel, all contributions)."""
    H, W = ref.shape; nby, nbx = V.shape[:2]
    bx = BX // sx; by = BY
    r = ref.astype(np.int64)
    # weights: pixel -> the two nearest block centres in each axis
    cy = (np.arange(H) + 0.5) / by - 0.5; cx = (np.arange(W) + 0.5) / bx - 0.5
    iy0 = np.clip(np.floor(cy).astype(int), 0, nby - 1); iy1 = np.clip(iy0 + 1, 0, nby - 1)
    ix0 = np.clip(np.floor(cx).astype(int), 0, nbx - 1); ix1 = np.clip(ix0 + 1, 0, nbx - 1)
    if bmax is not None and bmax > 0:
        ix0 = np.minimum(ix0, bmax - 1); ix1 = np.minimum(ix1, bmax - 1)
    wy = np.round((cy - np.floor(cy)) * 16).astype(np.int64); wy = np.where(cy < 0, 0, np.where(cy > nby - 1, 0, wy))
    wx = np.round((cx - np.floor(cx)) * 16).astype(np.int64); wx = np.where(cx < 0, 0, np.where(cx > nbx - 1, 0, wx))
    out = np.zeros((H, W), np.int64)
    Y = np.arange(H)[:, None]; X = np.arange(W)[None, :]
    for (IY, WY) in ((iy0, 16 - wy), (iy1, wy)):
        for (IX, WX) in ((ix0, 16 - wx), (ix1, wx)):
            vy = V[IY][:, IX, 0]; vx = V[IY][:, IX, 1]
            w = WY[:, None] * WX[None, :]
            yy = np.clip(Y + vy, 0, H - 1)
            xl = W - 1 if xmax is None else xmax - 1
            if sx == 1:
                g = r[yy, np.clip(X + vx, 0, xl)]
            else:
                xa = np.clip(X + np.floor_divide(vx, 2), 0, xl); xb = np.clip(X + np.floor_divide(vx + 1, 2), 0, xl)
                g = (r[yy, xa] + r[yy, xb] + 1) >> 1
            out += w * g
    return (out + 128) >> 8


def derive_reg(d1, d2, bx, by, rx, ry, lam):
    """regularised canonical derivation: per block row, left to right, cost = SAD + lam*(|dy-dy_left|+|dx-dx_left|)*bx*by/64
    (the left vector is the one already chosen; zero at the row start). Deterministic, same in every encoder."""
    H, W = d1.shape; nby, nbx = H // by, W // bx
    a = d1.astype(np.int64); pad = np.pad(d2.astype(np.int64), ((ry, ry), (rx, rx)), mode='edge')
    cands = [(dy, dx) for dy in range(-ry, ry + 1) for dx in range(-rx, rx + 1)]
    S = np.zeros((len(cands), nby, nbx), np.int64)
    for i, (dy, dx) in enumerate(cands):
        S[i] = np.abs(a - pad[ry + dy:ry + dy + H, rx + dx:rx + dx + W]).reshape(nby, by, nbx, bx).sum(axis=(1, 3))
    C = np.array(cands); V = np.zeros((nby, nbx, 2), np.int64); left = np.zeros((nby, 2), np.int64)
    w = lam * bx * by // 64
    for j in range(nbx):
        pen = (np.abs(C[:, None, 0] - left[None, :, 0]) + np.abs(C[:, None, 1] - left[None, :, 1])) * w
        tot = S[:, :, j] + pen
        k = np.argmin(tot, axis=0)
        # zero-vector preference on (near) ties: still areas stay still
        # zero-vector preference: a block is still unless motion explains it better by more than one code per pixel
        # (decoded history differs by refinement noise even when the scene is still)
        z = cands.index((0, 0)); k = np.where(S[z, :, j] <= S[k, np.arange(nby), j] + bx * by * ZTOL, z, k)
        V[:, j] = C[k]; left = V[:, j]
    return V


def ccv2r(d1, d2, ll1cur, Vh, bx=64, by=8, lam=4):
    """SA18 coarse-first vectors: per block, among C = {Vh + d, Vc2 + d : d in {-1,0,1}^2} (Vc2 = search of the CURRENT
    decoded level-1 LL (ll1cur, half resolution) against the reference's level-1 LL, x2), the candidate whose OBMC
    prediction's level-1 LL best matches ll1cur (SAD per block). Every candidate is evaluated as a uniform field
    (no block coupling); ties go to the earlier candidate. Inputs are data every encoder and re-encoder has exactly."""
    import pyr
    H, W = d1.shape; nby, nbx = H // by, W // bx
    ref1 = pyr.analysis(d1, 1, 1)['LL']
    Vc2 = derive(ll1cur, ref1, bx=bx // 2, by=max(1, by // 2), rx=RX // 2, ry=max(1, RY // 2), lam=lam) * 2
    best = np.full((nby, nbx), np.iinfo(np.int64).max); Vb = Vh.copy()
    for base in (Vh, Vc2):
        for dy in (0, -1, 1):
            for dx in (0, -1, 1):
                V = base + np.array([dy, dx])
                P = predict(d1, V); l1 = pyr.analysis(P, 1, 1)['LL']
                e = np.abs(l1 - ll1cur).reshape(nby, by // 2, nbx, bx // 2).sum(axis=(1, 3))
                take = e < best; best = np.where(take, e, best); Vb[take] = V[take]
    return Vb


def cap_delta(Vc, Vh, S, by, allow):
    """SA18: per slice (block rows of S rows), the delta Vc - Vh is coded in raster order; once the slice's delta bits
    would exceed `allow`, the remaining blocks take Vh (delta 0). Deterministic: every encoder applies the same rule."""
    V = Vc.copy(); nby = V.shape[0]; per = max(1, S // by)
    for r0 in range(0, nby, per):
        rows = slice(r0, r0 + per); D = (Vc[rows] - Vh[rows]).reshape(-1, 2); used = 0.0
        flat = V[rows].reshape(-1, 2); hflat = Vh[rows].reshape(-1, 2); prev = np.zeros(2, np.int64)
        for i in range(D.shape[0]):
            d = D[i] - prev; z = np.where(d > 0, 2 * d - 1, -2 * d); b = float((2 * np.floor(np.log2(z + 1)) + 1).sum())
            if used + b > allow: flat[i] = hflat[i]; D[i] = 0; d = -prev; z = np.where(d > 0, 2 * d - 1, -2 * d); b = float((2 * np.floor(np.log2(z + 1)) + 1).sum())
            used += b; prev = D[i]
        V[rows] = flat.reshape(V[rows].shape)
    return V


def ccv_ll2(d1, ll2cur, Vh, R=2, bx=64, by=8):
    """SA18 coarse-first vectors, stage LL2: per block, among {Vh + d : d in [-R, R]^2} (order: 0 first, then growing
    |d|), the candidate whose BLOCK-shifted reference's level-2 LL best matches the CURRENT decoded LL2 (SAD per block).
    Deterministic, uniform-field scoring (no coupling); inputs every encoder and re-encoder has exactly."""
    import pyr
    H, W = d1.shape; nby, nbx = H // by, W // bx
    best = np.full((nby, nbx), np.iinfo(np.int64).max); Vb = Vh.copy()
    order = [0] + [v for k in range(1, R + 1) for v in (-k, k)]
    for dy in order:
        for dx in order:
            V = Vh + np.array([dy, dx])
            ys = np.clip(np.arange(H)[:, None] + np.repeat(V[..., 0], by, 0).repeat(bx, 1), 0, H - 1)
            xs = np.clip(np.arange(W)[None, :] + np.repeat(V[..., 1], by, 0).repeat(bx, 1), 0, W - 1)
            l2 = pyr.analysis(d1[ys, xs], 2, 2)['LL']
            e = np.abs(l2 - ll2cur).reshape(nby, by // 4, nbx, bx // 4).sum(axis=(1, 3))
            take = e < best; best = np.where(take, e, best); Vb[take] = V[take]
    return Vb
