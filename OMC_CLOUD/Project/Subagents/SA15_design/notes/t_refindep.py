# Lattice lock: a decoded picture is reproduced exactly by an encoder with the SAME, a DIFFERENT, or NO reference.
import numpy as np, cpp
from common import *
for cell,W,H in [('dng720',1280,720),('gfx',448,256)]:
    P=read_frame(CELLS[cell][0],W,H,8 if cell=='dng720' else 3); Q=read_frame(CELLS[cell][0],W,H,7 if cell=='dng720' else 2)
    st={'LL':20.0}
    for k in range(5):
        for b in (['LH','HL','HH'] if k<2 else ['H']): st[(b,k)]=20.0
    zi=lambda k,s: np.zeros(s,bool)
    for pi,nm in enumerate(('Y','Cb','Cr')):
        p=P[pi]; mc=Q[pi]
        y,i=cpp.code_plane(p,st,5,2,0,1023,mc=mc,imask=zi,tmode='idx')
        same,_=cpp.code_plane(y,st,5,2,0,1023,mc=mc,imask=zi,tmode='idx')
        other,_=cpp.code_plane(y,st,5,2,0,1023,mc=np.roll(mc,3,0),imask=zi,tmode='idx')
        none,_=cpp.code_plane(y,st,5,2,0,1023,mc=None,tmode='idx')
        print(f'{cell} {nm}: exact with same ref {(same==y).all()}, different ref {(other==y).all()}, no ref {(none==y).all()}, oob {int(((y<0)|(y>1023)).sum())}')
