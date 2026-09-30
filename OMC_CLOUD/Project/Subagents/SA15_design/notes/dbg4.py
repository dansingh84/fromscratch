import os; os.environ['RESC']='0'
import numpy as np, seq2
tabs=seq2.Tables(); A='/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1280x720_422_10.yuv'
B=0.5*1280*4; c=seq2.Codec(1280,720,S=4,tabs=tabs)
for t in range(3):
    c.encode(seq2.read(A,1280,720,t),B); fi=c.frame_info; dev=np.array(fi['dev'])
    rf=fi['refresh']; rs=set(range(rf[0]//4,(rf[1]+3)//4))
    big=np.argsort(-np.abs(dev))[:6]
    print('t',t,'refresh',rf,'dev sum',dev.sum().round(),'top',[(int(k),round(dev[k]),k in rs) for k in big],'nonrefresh max',max(abs(dev[k]) for k in range(len(dev)) if k not in rs))
