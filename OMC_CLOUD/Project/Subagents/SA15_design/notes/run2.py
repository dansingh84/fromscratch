# round-2 driver: gen-1 with exact-CBR rate control + gen-2 check; writes decode for NEG/tools
import os, sys, time, numpy as np, argparse
import seq2
from common import psnr
ap=argparse.ArgumentParser()
ap.add_argument('src'); ap.add_argument('W',type=int); ap.add_argument('H',type=int); ap.add_argument('bpp',type=float)
ap.add_argument('N',type=int); ap.add_argument('tag')
ap.add_argument('--fmt',type=int,default=422); ap.add_argument('--depth',type=int,default=10)
ap.add_argument('--rng',default=None); ap.add_argument('--S',type=int,default=8); ap.add_argument('--hp',type=int,default=0)
ap.add_argument('--f0',type=int,default=0); ap.add_argument('--frames',default=None)   # comma list of (file:frame) for cut/mixed
ap.add_argument('--gen2',type=int,default=1); ap.add_argument('--tag_dummy',type=int,default=0); ap.add_argument('--refresh',type=int,default=1)
a=ap.parse_args()
OUT='/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA15_design/out/r2/'; os.makedirs(OUT,exist_ok=True)
rng=None
if a.rng: v=[int(x) for x in a.rng.split(',')]; rng=[(v[0],v[1]),(v[2],v[3]),(v[2],v[3])]
tabs=seq2.Tables()
assert tabs.ok, 'no tables'
def src_frame(t):
    return seq2.read(a.src,a.W,a.H,a.f0+t,a.fmt)
frames=[src_frame(t) for t in range(a.N)] if a.frames is None else None
if a.frames is not None:
    import importlib; mk=importlib.import_module(a.frames); frames=mk.make(a)
B=a.bpp*a.W*a.S
def run(inputs,label,ref=None):
    cod=seq2.Codec(a.W,a.H,fmt=a.fmt,depth=a.depth,rng=rng,S=a.S,hp=bool(a.hp),tabs=tabs,refresh=bool(a.refresh))
    dec=[]; log=[]
    for t,fr in enumerate(inputs):
        t0=time.time(); y=cod.encode(fr,B); fi=cod.frame_info
        bits=fi['bits'].sum()+fi['vbits']; dev=np.array(fi['dev'])
        lane=np.array([l[1] for l in fi['lane']]); jumps=np.array([l[3] for l in fi['lane']])
        oob=sum(int(((p<cod.rng[i][0])|(p>cod.rng[i][1])).sum()) for i,p in enumerate(y))
        ps=[psnr(s_,d_,peak=(1<<a.depth)-1) for s_,d_ in zip(fr,y)]
        cmp_=('' if ref is None else ' g2_vs_g1: '+('identical' if all((u==v).all() for u,v in zip(y,ref[t])) else f'{sum(int((u!=v).sum()) for u,v in zip(y,ref[t]))} differing samples'))
        line=(f'{label} t={t} bpp={bits/(a.W*a.H):.4f} psnr_vs_input={ps[0]:.2f}/{ps[1]:.2f}/{ps[2]:.2f}{cmp_} kap[min/med/max]={min(fi["kap"])}/{int(np.median(fi["kap"]))}/{max(fi["kap"])} '
              f'jump>+8:{int((jumps>8).sum())} jump<0:{int((jumps<0).sum())} overflow={cod.overflow} reading_fixes={cod.selfread} unresolved_frames={cod.selfread_fail} credit={cod.credit:.0f} pot={cod.pot:.0f} '
              f'dev(actual-lane) sum={dev.sum():.0f} max={dev.max() if len(dev) else 0:.0f} refresh={fi["refresh"]} hfslices={sum(fi["hfslice"])} oob={oob} {time.time()-t0:.0f}s')
        s_=np.cumsum([0]); 
        print(line,flush=True); log.append((None,bits)); cod.frame_info={k:v for k,v in fi.items() if k in ('kap','V')}
        dec.append([p.copy() for p in y])
    return dec,log
d1,l1=run(frames,'g1')
seq2.write(OUT+a.tag+'.yuv',d1)
if a.gen2:
    d2,l2=run(d1,'g2',ref=d1)
    nd=sum(int((x!=y).sum()) for f1,f2 in zip(d1,d2) for x,y in zip(f1,f2))
    nb=[round(b2/b1,4) for (_,b1),(_,b2) in zip(l1,l2)]
    print(f'{a.tag} GEN2 differing samples={nd} per-frame bits g2/g1={nb}',flush=True)
