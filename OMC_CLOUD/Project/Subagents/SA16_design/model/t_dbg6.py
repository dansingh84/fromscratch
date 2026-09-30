import sys, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import omc16, yuv, pyr2
from pyr2 import BANDS
path, W, H = yuv.CELLS['dng720']
cod = omc16.Codec(W, H, S=4, bpp=0.5, tabs=omc16.Tables('../out/tables/tables_p1.pkl'))
src = yuv.read_frame(path, W, H, 0); rec = cod.encode(src)
print('Pe stats', cod.last['Pe'].min(), np.median(cod.last['Pe']), cod.last['Pe'].max(), 'bits', cod.stats['frame_bits'])
for pi in range(3):
    Ts = pyr2.analysis(src[pi], cod.Lh[pi]); Tr = pyr2.analysis(rec[pi], cod.Lh[pi])
    print('plane', pi, 'PSNR %.2f' % (10*np.log10(1023**2/np.mean((rec[pi]-src[pi])**2.0))))
    for b in BANDS(cod.Lh[pi]):
        e = (Tr[b] - Ts[b]).astype(float); Pm = int(np.median(cod.last['Pe'])); D = cod.step(pi, b, Pm)
        print('   %-4s D(median P)=%4d  rms err %7.2f  mean err %+7.2f  rms src %8.2f  frac zero idx %.2f' % (b, D, np.sqrt((e**2).mean()), e.mean(), np.sqrt((Ts[b].astype(float)**2).mean()), (cod.last['E'][pi][b] == 0).mean()))
