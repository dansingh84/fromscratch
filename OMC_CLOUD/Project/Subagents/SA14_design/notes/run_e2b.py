import sys, numpy as np
sys.path.insert(0,'.')
import nest2 as nest, enc2, common14 as cm
cm.nest = nest
n2d,n1d=2,3
out=[]
def run(name,X,dep,D0,lov=None,hiv=None):
    M=(1<<dep)-1; lov=0 if lov is None else lov; hiv=M if hiv is None else hiv
    lo=np.full(X.shape,lov,np.int64); hi=np.full(X.shape,hiv,np.int64)
    loI=np.full(X.shape,-nest.INF); hiI=np.full(X.shape,nest.INF)
    sh=cm.shifts_for(n2d,n1d,X.shape,D0)
    ql,top,rec,st=enc2.encode(X,lo,hi,n2d,n1d,sh)
    desc,bl,be=enc2.read(ql,top)
    y1=enc2.decode(desc,lo,hi,n2d,n1d)
    q2,t2=enc2.canonical(y1,lo,hi,n2d,n1d); d2,_,_=enc2.read(q2,t2); y2=enc2.decode(d2,lo,hi,n2d,n1d)
    # clip reference: same quantisation, plain synthesis + clip (no boundary machinery)
    lev,(L,_,_)=nest.analysis(X,loI,hiI,n2d,n1d)
    q0=[{n:{'val':nest.R(nest.Q(d['val'],sh[(i,n)]),sh[(i,n)]),'esc':np.zeros(d['val'].shape,np.int8),'uesc':0*d['val']} for n,d in l.items() if n!='win'} for i,l in enumerate(lev)]
    t0={'val':nest.R(nest.Q(L,sh['top']),sh['top']),'esc':np.zeros(L.shape,np.int8)}
    r0,_,_=nest.synthesis(t0,q0,loI,hiI,n2d,n1d); clip=np.clip(r0,lov,hiv)
    b0=sum(nest.entropy_bits(np.asarray(d['val']>>sh[(i,n)])) for i,l in enumerate(q0) for n,d in l.items())+nest.entropy_bits(t0['val']>>sh['top'])
    nesc=sum(int((d['esc']!=0).sum()) for l in ql for d in l.values())
    eN=np.abs(rec-X); eK=np.abs(clip-X)
    line=(f"{name:12s} D0={D0:4d} bits: nest={(bl+be)/X.size:.4f} (esc part {be/X.size:.4f}) clipref={b0/X.size:.4f} | psnr nest={cm.psnr(X,rec,dep):.3f} clip={cm.psnr(X,clip,dep):.3f} | "
          f"maxerr nest={int(eN.max())} clip={int(eK.max())} | oob={int(((y1<lov)|(y1>hiv)).sum())} rounds={st['rounds']} conv={st['converted']} bsamples={nesc} "
          f"y1==rec {bool((y1==rec).all())} gen2_desc_same={enc2.same_desc(desc,d2)} gen2_moved={int((y2!=y1).sum())}")
    print(line,flush=True); out.append(line)
if __name__=='__main__':
    for D0 in (32,128,256):
        for cell in ('dng1080','spot','floor','gfx'):
            planes,dep=cm.read_frame(cell,8)
            for pn,X in zip('Y',planes[:1]):
                run(f"{cell}-{pn}",X,dep,D0)
        planes,dep=cm.read_frame('spot',8)
        run('spot-Cb',planes[1],dep,D0)
        run('rails10',cm.synth_rails(dep=10),10,D0)
        run('railslim',np.clip(cm.synth_rails(dep=10),4,1019),10,D0,4,1019)
    open('../out/e2b.txt','w').write('\n'.join(out)+'\n')
