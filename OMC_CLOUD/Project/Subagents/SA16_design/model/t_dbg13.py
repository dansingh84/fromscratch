import sys, os, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import omc16, yuv
path, W, H = yuv.CELLS['dng720']
g1 = omc16.Codec(W, H, S=4, bpp=0.5); g2 = omc16.Codec(W, H, S=4, bpp=0.5)
r = [g1.encode(yuv.read_frame(path, W, H, t)) for t in range(2)]
for t in range(2): g2.encode(r[t])
os.environ['DBG_EST'] = '1'; r2 = g1.encode(yuv.read_frame(path, W, H, 2)); os.environ.pop('DBG_EST')
print('f2 g1 stats', {k: v for k, v in g1.stats.items()})
os.environ['DBG_READ'] = '1'; g2.dbg_ref = g1.dbg_fin if hasattr(g1, 'dbg_fin') else {}; x = g2.encode(r2); os.environ.pop('DBG_READ')
print('f2 g2 same', all(np.array_equal(x[p], r2[p]) for p in range(3)))
