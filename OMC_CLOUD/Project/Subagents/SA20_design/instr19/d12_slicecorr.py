# D12: how much of the source-vector gain does a PER-SLICE parametric correction of the history field recover?
# candidates per slice (8-row block row at 1080p): offset (dy,dx) in [-2..2]^2, and scale s in {0.75,..,1.5} of the
# history vectors; chosen by source SAD over the slice (oracle choice; the exact reading is designed separately).
import numpy as np, sys, yuv, motion
DEC = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA17_design/out/dec/final_%s_b0.5.d.yuv'
motion.BX = 64
for cell in sys.argv[1].split(','):
    p_, W, H = yuv.CELLS[cell]; acc = {}
    for f in range(4, 8):
        S0 = yuv.read_frame(p_, W, H, f); D1 = yuv.read_frame(DEC % cell, W, H, f - 1); D2 = yuv.read_frame(DEC % cell, W, H, f - 2)
        Vh = motion.derive(D1[0], D2[0], bx=64, lam=4); Vs = motion.derive(S0[0], D1[0], bx=64, lam=4)
        nby = Vh.shape[0]
        cands = [('off', dy, dx) for dy in range(-2, 3) for dx in range(-2, 3)] + [('scl', s, 0) for s in (0.75, 0.875, 1.125, 1.25, 1.5)]
        preds = {}
        for c in cands:
            if c[0] == 'off': V = Vh + np.array([c[1], c[2]])
            else: V = np.round(Vh * c[1]).astype(np.int64)
            preds[c] = motion.predict(D1[0], V)
        err = {c: np.abs(preds[c] - S0[0]).reshape(nby, 8, -1).sum(axis=(1, 2)) for c in cands}
        best = [min(cands, key=lambda c: err[c][r]) for r in range(nby)]
        Vc = np.zeros_like(Vh)
        for r, c in enumerate(best):
            Vc[r] = Vh[r] + np.array([c[1], c[2]]) if c[0] == 'off' else np.round(Vh[r] * c[1]).astype(np.int64)
        for k, V in (('hist', Vh), ('slicecorr', Vc), ('src', Vs)):
            mse = [np.mean((motion.predict(D1[i], V, 1 if i == 0 else 2) - S0[i]) ** 2.0) for i in range(3)]
            acc.setdefault(k, np.zeros(3)); acc[k] += mse
    for k, m in acc.items():
        print('%-7s %-9s pred PSNR %.2f/%.2f/%.2f' % (cell, k, *(10 * np.log10(1023 ** 2 / (m / 4)))), flush=True)
