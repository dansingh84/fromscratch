import sys, os, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import omc16, yuv
path, W, H = yuv.CELLS['dng720']
g1 = omc16.Codec(W, H, S=4, bpp=0.5, tabs=omc16.Tables('../out/tables/tables_p1.pkl'))
g1.encode(yuv.read_frame(path, W, H, 0))
os.environ['DBG_EST'] = '1'; g1.encode(yuv.read_frame(path, W, H, 1))
print('f1 stats', g1.stats)
