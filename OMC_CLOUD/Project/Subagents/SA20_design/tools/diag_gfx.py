import sys, os, types, numpy as np
os.chdir('/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design'); sys.path.insert(0, 'bench')
sys.argv = ['rcl_cbr.py', 'train', 'cm1_zb2_hy0.75_sg_s16']
src = open('bench/rcl_cbr.py').read(); src = src[:src.index("if TEST == 'train': sys.exit(0)")]
ns = {'__file__': os.path.abspath('bench/rcl_cbr.py')}; exec(compile(src, 'rcl_cbr', 'exec'), ns); R = types.SimpleNamespace(**ns)
from dp_screen_core import motion, apply
X = [R.read(R.A + 'gfx444_B001C001_1280x720_422_10.yuv', 1280, 720, f) for f in range(3)]
ps = lambda a, b: 10 * np.log10(1023 ** 2 / max(((a - b).astype(float) ** 2).mean(), 1e-9))
for Q in (4.757, 8.0, 16.0):
    sy, y0 = R.code_frame(X[0], None, Q)
    syi, yi = R.code_frame(X[1], None, Q); bi = R.fcost(syi, Q)
    sye, ye = R.code_frame(X[1], y0, Q, None, X[0]); be = R.fcost(sye, Q) + 10 * R.NBLK
    print('Q %.2f f1 INTRA %.3f bpp Y %.2f | INTER %.3f bpp Y %.2f' % (Q, bi / 921600, ps(yi[0], X[1][0]), be / 921600, ps(ye[0], X[1][0])), flush=True)
    for nm, B, Z in (('16x16 Z2', 16, 2.0), ('16x16 Z0', 16, 0.0), ('8x8 Z0', 8, 0.0)):
        V = motion(X[1][0], y0[0], B=B, Z=Z); P = apply(y0[0], V, B, 1)
        print('   MC pred %s: Y PSNR %.2f (ref recon itself vs src f1: %.2f)' % (nm, ps(P, X[1][0]), ps(y0[0], X[1][0])), flush=True)
