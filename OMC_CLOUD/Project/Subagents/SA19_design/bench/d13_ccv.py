# D13 (partner idea a): vectors searched on the CURRENT frame's DECODED coarse band vs the reference's coarse band.
# decoded coarse(t) approximated by the 4x4 (LL2) / 2x2 (LL1) means of SA17's real decode of frame t (coarse bands are
# finely quantised). Search at coarse resolution with the same block geometry (64x8 full res), then scale.
# Also 'ccv+r': coarse vector refined by +-1..2 full-res pel using HISTORY SAD (exact, no current full-res data).
import numpy as np, sys, yuv, motion
DEC = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA17_design/out/dec/final_%s_b0.5.d.yuv'
def mean(a, k):
    h, w = a.shape; return a[:h // k * k, :w // k * k].reshape(h // k, k, w // k, k).mean(axis=(1, 3))
def cv(Pt, D1, k):
    a = np.round(mean(Pt, k) * 16).astype(np.int64); b = np.round(mean(D1, k) * 16).astype(np.int64)
    V = motion.derive(a, b, bx=64 // k, by=max(1, 8 // k), rx=16 // k, ry=max(1, 4 // k), lam=4)
    return V * k
for cell in sys.argv[1].split(','):
    p_, W, H = yuv.CELLS[cell]; acc = {}
    for f in range(4, 8):
        S0 = yuv.read_frame(p_, W, H, f); Pt = yuv.read_frame(DEC % cell, W, H, f)[0]
        D1 = yuv.read_frame(DEC % cell, W, H, f - 1); D2 = yuv.read_frame(DEC % cell, W, H, f - 2)
        motion.BX = 64
        F = {'hist': motion.derive(D1[0], D2[0], bx=64, lam=4), 'src': motion.derive(S0[0], D1[0], bx=64, lam=4),
             'ccv2': cv(Pt, D1[0], 2), 'ccv4': cv(Pt, D1[0], 4), 'dec-full': motion.derive(Pt, D1[0], bx=64, lam=4)}
        for k, V in F.items():
            V = V.reshape(H // 8, W // 64, 2)
            mse = [np.mean((motion.predict(D1[i], V, 1 if i == 0 else 2) - S0[i]) ** 2.0) for i in range(3)]
            acc.setdefault(k, np.zeros(3)); acc[k] += mse
    for k, m in acc.items():
        print('%-7s %-9s pred PSNR %.2f/%.2f/%.2f' % (cell, k, *(10 * np.log10(1023 ** 2 / (m / 4)))), flush=True)
