# D8: why do history vectors lose? MC prediction error (MSE per plane vs source t) under vector fields:
#  hist   = derive(D(t-1), D(t-2))            (SA17, exact by construction)
#  src    = derive(S(t), D(t-1))              (oracle, not exact)
#  stale  = derive(S(t-1), S(t-2))            (staleness only, no coding noise; not realisable)
#  histlp = derive(lp(D(t-1)), lp(D(t-2)))    (noise-robust history: 3x3 binomial lowpass before matching)
# D = SA17's real decodes @0.5 (final_*). Frames 4..9. OBMC 64x8 blocks, lam 4, same as SA17.
import numpy as np, sys, yuv, motion
DEC = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA17_design/out/dec/final_%s_b0.5.d.yuv'
motion.BX = 64
def lp(a):
    a = a.astype(np.int64); p = np.pad(a, 1, mode='edge')
    h = p[:, :-2] + 2 * p[:, 1:-1] + p[:, 2:]; v = h[:-2] + 2 * h[1:-1] + h[2:]
    return (v + 8) >> 4
for cell in sys.argv[1].split(','):
    p_, W, H = yuv.CELLS[cell]; acc = {}
    for f in range(4, 10):
        S0 = yuv.read_frame(p_, W, H, f); S1 = yuv.read_frame(p_, W, H, f - 1); S2 = yuv.read_frame(p_, W, H, f - 2)
        D1 = yuv.read_frame(DEC % cell, W, H, f - 1); D2 = yuv.read_frame(DEC % cell, W, H, f - 2)
        F = {'hist': motion.derive(D1[0], D2[0], bx=64, lam=4), 'src': motion.derive(S0[0], D1[0], bx=64, lam=4),
             'stale': motion.derive(S1[0], S2[0], bx=64, lam=4), 'histlp': motion.derive(lp(D1[0]), lp(D2[0]), bx=64, lam=4),
             'zero': np.zeros_like(motion.derive(D1[0], D2[0], bx=64, lam=4))}
        for k, V in F.items():
            mse = [np.mean((motion.predict(D1[i], V, 1 if i == 0 else 2) - S0[i]) ** 2.0) for i in range(3)]
            a = acc.setdefault(k, [np.zeros(3), 0, 0.0]); a[0] += mse; a[1] += motion.vec_bits(V)
            a[2] += float((np.abs(V - F['src']).sum(-1) == 0).mean())
    for k, (m, vb, ag) in acc.items():
        print('%-7s %-6s pred PSNR %.2f/%.2f/%.2f  vec bits/frame %d  agree-with-src %.1f%%' % (cell, k, *(10 * np.log10(1023 ** 2 / (m / 6))), vb // 6, 100 * ag / 6), flush=True)
