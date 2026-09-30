# D11: real-code-length gain of per-(band, slice) table SELECTION from a small static bank: each trained table p(c|ctx)
# is expanded into variants p_l(c) ∝ p(c) * 2^(-l*c) (l in LAMS: sharper/flatter class distribution); the encoder picks
# the cheapest variant per band-slice and sends its index (log2 T bits). Emitted indices of real encodes, frames 2..N-1.
import numpy as np, sys, yuv, ent, seq, codec
cell, bpp, tabp = sys.argv[1], float(sys.argv[2]), sys.argv[3]; N = int(sys.argv[4]) if len(sys.argv) > 4 else 6
LAMS = [float(v) for v in (sys.argv[5] if len(sys.argv) > 5 else '-0.5,-0.25,0,0.25,0.5,1,1.5,2').split(',')]
p_, W, H = yuv.CELLS[cell]; tabs = ent.Tables(tabp); S = 4 if H == 720 else 8
s = seq.Seq(W, H, bpp, tabs, tilt=0.25, rho=0.35, bx=64, lam=4, refresh=False, still_hold=1, S=S)
L = ent.L
def variant(ln, l):
    p = 2.0 ** (-ln) * 2.0 ** (-l * np.arange(ent.NC))[None, :]; p = p / p.sum(1, keepdims=True)
    f = np.maximum(1, np.round(p * L)); f = f / f.sum(1, keepdims=True) * L       # approx tANS quantisation
    return np.log2(L / np.maximum(f, 1))
base_bits = 0.0; bank_bits = 0.0; side = 0.0; use = np.zeros(len(LAMS))
for f in range(N):
    x = yuv.read_frame(p_, W, H, f); o, b, info = s.encode(x)
    if f < 2: continue
    for p in range(3):
        for bn in codec.BANDSP[p]:
            q = info['Q'][p][bn]; c = ent.cls(q); cc = np.minimum(c, ent.NC - 1)
            cx = s.c.slice_ctx(c, bn, p); rpb = S // codec.ROWDIV[(p, bn)]
            e_s = np.array([s.c.E[info['plans'][k]][(p, bn)] for k in range(len(info['plans']))])
            im = info['im'][p][bn] if info['im'] is not None else None
            for k in range(len(info['plans'])):
                rows = slice(k * rpb, (k + 1) * rpb); eb = int(ent.ebucket(e_s[k]))
                for inter in ((False,) if im is None else (False, True)):
                    m = np.ones(q[rows].shape, bool) if im is None else (im[rows] if inter else ~im[rows])
                    if not m.any(): continue
                    ln = tabs.len.get(ent.table_key(p, bn, inter, eb))
                    if ln is None: continue
                    costs = [variant(ln, l)[cx[rows][m], cc[rows][m]].sum() for l in LAMS]
                    b0 = ln[cx[rows][m], cc[rows][m]].sum(); base_bits += b0
                    j = int(np.argmin(costs)); bank_bits += costs[j]; side += np.log2(len(LAMS)); use[j] += 1
print(cell, bpp, 'class bits: static %.0f  bank-select %.0f + side %.0f  -> %.1f %% of class bits' % (base_bits, bank_bits, side, 100 * (bank_bits + side - base_bits) / base_bits), 'use', use.astype(int).tolist(), flush=True)
