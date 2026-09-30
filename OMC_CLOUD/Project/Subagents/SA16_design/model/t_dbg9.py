import sys, os, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import omc16, yuv
path, W, H = yuv.CELLS['dng720']
g1 = omc16.Codec(W, H, S=4, bpp=0.5); g2 = omc16.Codec(W, H, S=4, bpp=0.5)
os.environ['DBG_EST'] = '1'
src = yuv.read_frame(path, W, H, 0); r1 = g1.encode(src)
os.environ['DBG_READ'] = '1'; g2.dbg_ref = g1.dbg_fin; r2 = g2.encode(r1); os.environ.pop('DBG_READ')
print('f0 g2 same', all(np.array_equal(r2[p], r1[p]) for p in range(3)))
os.environ['DBG_EST'] = '1'
src = yuv.read_frame(path, W, H, 1); r1 = g1.encode(src)
print('f1 stats', {k: v for k, v in g1.stats.items() if k != 'band_bits'})
