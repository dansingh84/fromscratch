import sys, time, cProfile, pstats, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import omc16, yuv
path, W, H = yuv.CELLS['dng720']
cod = omc16.Codec(W, H, S=4, bpp=0.5)
cod.encode(yuv.read_frame(path, W, H, 0))
print('f0 pass2', cod.last['info'].get('pass2_exact'), cod.stats, flush=True)
src = yuv.read_frame(path, W, H, 1)
pr = cProfile.Profile(); pr.enable(); rec = cod.encode(src); pr.disable()
print('f1 pass2', cod.last['info'].get('pass2_exact'), cod.last['info']['pass2_changed'], cod.stats, flush=True)
pstats.Stats(pr).sort_stats('cumulative').print_stats(18)
