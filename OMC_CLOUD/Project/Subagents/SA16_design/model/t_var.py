import sys, os, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import omc16, yuv
path, W, H = yuv.CELLS['dng720']; today = yuv.TODAY['dng720'] % '0.5'
cod = omc16.Codec(W, H, S=4, bpp=0.5, tabs=omc16.Tables('../out/tables/tables_p2.pkl'))
for t in range(3):
    src = yuv.read_frame(path, W, H, t); r = cod.encode(src)
    print('%s f%d PSNR %.2f/%.2f/%.2f Pe med %d' % (sys.argv[1], t, *[10*np.log10(1023**2/np.mean((r[p]-src[p])**2.0)) for p in range(3)], np.median(cod.last['Pe'])), flush=True)
