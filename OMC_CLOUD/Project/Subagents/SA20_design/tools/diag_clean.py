# per-frame luma PSNR of a decode against the CLEAN frozen picture (cine_frozen10 frame 0), for the noisy-frozen synthetics
import sys, numpy as np
sys.path.insert(0, __file__.rsplit('/', 2)[0] + '/bench')
W, H = 1280, 720
A = '/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/'
def rd(fn, f):
    n = W * H + 2 * (W // 2) * H
    a = np.fromfile(fn, np.uint16, n, offset=f * n * 2).astype(float); return a[:W * H].reshape(H, W)
clean = rd(sys.argv[1], 0)
for fn in sys.argv[2:]:
    ps = []
    for f in range(10):
        e = np.mean((rd(fn, f) - clean) ** 2); ps.append(10 * np.log10(1023 ** 2 / e))
    print(fn.rsplit('/', 1)[-1], ' '.join('%.2f' % p for p in ps))
