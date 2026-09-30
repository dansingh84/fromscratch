import sys, os, types, numpy as np
os.chdir('/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design'); sys.path.insert(0, 'bench')
sys.argv = ['rcl_cbr.py', 'train', 'cm1_zb2_hy0.75_sg_keep_rs_ng_nf5_cu0']
src = open('bench/rcl_cbr.py').read(); src = src[:src.index("if TEST == 'train': sys.exit(0)")]
ns = {'__file__': os.path.abspath('bench/rcl_cbr.py')}; exec(compile(src, 'rcl_cbr', 'exec'), ns); R = types.SimpleNamespace(**ns)
X = [R.read(R.A + 'cine_nfrozen2_1280x720_422_10.yuv', 1280, 720, f) for f in range(3)]
sy, y0 = R.code_frame(X[0], None, 32.0); st = R.upd(None, y0, None, 32.0)
stl = R.still_blocks(X[1], X[0]); cu = R.cu_mask(st, 26.91, stl)
sy, y1 = R.code_frame(X[1], y0, 26.91, st, X[0]); st = R.upd(st, y1, y0, 26.91, stl, cu); ns['CAUGHT'][0] = (ns['CAUGHT'][0] | cu) & stl
print('sigma-hat luma median', np.median(ns['SIG'][0]))
sy, y2 = R.code_frame(X[2], y1, 9.51, st, X[1])
print('changed Y f1->f2', (y2[0] != y1[0]).mean())
for key0, SY, AC in sy[:1]:
    for key, q in SY: print(key, q.shape, 'nonzero %.4f' % (q != 0).mean())
print('QL luma median', np.median(st[0][0]), 'FL', np.median(st[0][1]), 'caught share', ns['CAUGHT'][0].mean(), 'still share', R.still_blocks(X[2], X[1]).mean())
