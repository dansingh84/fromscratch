import sys, os, math, numpy as np
os.environ['HF_FAST']='1'; os.environ['HF_VK']='s10a'; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
import grid, hf
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from permit import hp, per
for c,path in (('hwy','/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/long/highwaydriveL_1920x1080_422_10.yuv'),('dng','/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1920x1080_422_10.yuv'),('spot','/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/long/spotrobotL_1920x1080_422_10.yuv')):
    src=hf.load(path,1920,1080,8,'422')
    for Qf in (5.0,6.0,7.0):
        rh_,b=grid.hf_decode([p.astype(np.int64) for p in src],16,Qf)
        print(c,Qf,'RND=%d bpp %.3f'%(hf.RND,b),'mean err %s'%' '.join('%+.3f'%float((r-s).mean()) for r,s in zip(rh_,src)),
              'psnr %s'%' '.join('%.2f'%(10*math.log10(1023**2/float(((r-s)**2).mean()))) for r,s in zip(rh_,src)),
              'PER %s'%' '.join('%.2f'%(per(hp(r.astype(float)))/per(hp(s.astype(float)))) for r,s in zip(rh_,src)),flush=True)
