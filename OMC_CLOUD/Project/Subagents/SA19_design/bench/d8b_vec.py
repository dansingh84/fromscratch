# D8b: forward-projected history vectors (exact: derived from decoded history only):
#  proj1: V(b) = Vh(block at centre(b) + Vh(b))   (constant velocity of the content that ARRIVES at b)
#  proj2: second fixed-point step
import numpy as np, sys, yuv, motion
DEC = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA17_design/out/dec/final_%s_b0.5.d.yuv'
motion.BX = 64
def project(V, bx=64, by=8):
    nby, nbx = V.shape[:2]; cy = (np.arange(nby) + 0.5) * by; cx = (np.arange(nbx) + 0.5) * bx
    ty = np.clip(((cy[:, None] + V[..., 0]) // by).astype(int), 0, nby - 1); tx = np.clip(((cx[None, :] + V[..., 1]) // bx).astype(int), 0, nbx - 1)
    return V[ty, tx]
for cell in sys.argv[1].split(','):
    p_, W, H = yuv.CELLS[cell]; acc = {}
    for f in range(4, 10):
        S0 = yuv.read_frame(p_, W, H, f); D1 = yuv.read_frame(DEC % cell, W, H, f - 1); D2 = yuv.read_frame(DEC % cell, W, H, f - 2)
        Vh = motion.derive(D1[0], D2[0], bx=64, lam=4); Vs = motion.derive(S0[0], D1[0], bx=64, lam=4)
        P1 = project(Vh); P2 = project(Vh) ; P2 = Vh[np.clip(((np.arange(Vh.shape[0])[:, None] + 0.5) * 8 + P1[..., 0]) // 8, 0, Vh.shape[0] - 1).astype(int), np.clip(((np.arange(Vh.shape[1])[None, :] + 0.5) * 64 + P1[..., 1]) // 64, 0, Vh.shape[1] - 1).astype(int)]
        for k, V in (('hist', Vh), ('proj1', P1), ('proj2', P2), ('src', Vs)):
            mse = [np.mean((motion.predict(D1[i], V, 1 if i == 0 else 2) - S0[i]) ** 2.0) for i in range(3)]
            a = acc.setdefault(k, [np.zeros(3), 0.0]); a[0] += mse; a[1] += float((np.abs(V - Vs).sum(-1) == 0).mean())
    for k, (m, ag) in acc.items():
        print('%-7s %-6s pred PSNR %.2f/%.2f/%.2f  agree-with-src %.1f%%' % (cell, k, *(10 * np.log10(1023 ** 2 / (m / 6))), 100 * ag / 6), flush=True)
