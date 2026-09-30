import sys, os, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design/bench')
os.chdir('/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA20_design')
sys.argv = ['rcl_cbr.py', 'train', 'cm1_zb2_hy0.75_sg_keep_rs']
import types
src = open('bench/rcl_cbr.py').read(); src = src[:src.index("if TEST == 'train': sys.exit(0)")]
R = types.SimpleNamespace(); ns = {'__file__': os.path.abspath('bench/rcl_cbr.py')}; exec(compile(src, 'rcl_cbr', 'exec'), ns); R.__dict__.update(ns)
from dp_screen_core import motion
X = [R.read(R.A + 'cine_frozen10_1280x720_422_10.yuv', 1280, 720, f) for f in range(3)]
sy, y0 = R.code_frame(X[0], None, 32.0); st = R.upd(None, y0, None, 32.0)
V = motion(X[1][0], y0[0], Z=2.0); nzv = (V != 0).any(-1)
sy, y1 = R.code_frame(X[1], y0, 9.514, st, X[0])
ch = y1[0] != y0[0]; print('changed luma samples', int(ch.sum()), 'nonzero-vector blocks', int(nzv.sum()))
ii, jj = np.nonzero(ch); bi, bj = ii // 16, jj // 16
print('changed samples inside nonzero-vector blocks', int(nzv[bi, bj].sum()))
print('changed at rails (y0 at 0 or 1023)', int(((y0[0] == 0) | (y0[0] == 1023))[ch].sum()), ' src at rail', int(((X[1][0] <= 4) | (X[1][0] >= 1019))[ch].sum()))
print('|y1-y0| on changed', np.bincount(np.abs(y1[0] - y0[0])[ch].astype(int))[:10])
print('row/col of changed (first 10)', list(zip(ii[:10], jj[:10])))
