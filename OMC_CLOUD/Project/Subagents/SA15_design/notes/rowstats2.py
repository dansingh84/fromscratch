# per-row-phase error statistics inside the S-row slice (luma rows), per plane, intra (frame 0) and inter (frames 2..);
# slice-edge excess = phase S-1 minus the internal block-edge phases (every 4th row), mean|e| and row step.
import sys, numpy as np, seq2
def main(src,dec,W,H,N,S,fmt=422,depth=10,f0=0):
    sh=seq2.plane_shapes(W,H,fmt); out=[]
    acc={}
    for t in range(N):
        Sfr=seq2.read(src,W,H,f0+t,fmt); Dfr=seq2.read(dec,W,H,t,fmt)
        if t==1: continue
        mode='intra' if t==0 else 'inter'
        for pi in range(3):
            e=Dfr[pi].astype(float)-Sfr[pi]; Sp=S*sh[pi][0]//H
            ae=np.abs(e).mean(1); st=np.abs(np.diff(e,axis=0)).mean(1)
            a=acc.setdefault((mode,pi),np.zeros((4,Sp)))
            for r in range(len(ae)):
                a[0,r%Sp]+=ae[r]; a[1,r%Sp]+=1
                if r+1<len(ae): a[2,r%Sp]+=st[r]; a[3,r%Sp]+=1
    for (mode,pi),a in sorted(acc.items()):
        Sp=a.shape[1]; me=a[0]/a[1]; stp=a[2]/np.maximum(a[3],1); blk=max(1,Sp*4//S)
        for nm,v in (('mean|e|',me),('step',stp)):
            dev=100*(v/v.mean()-1); edges=[p for p in range(blk-1,Sp-1,blk)]
            ex=dev[Sp-1]-(np.mean(dev[edges]) if edges else 0.0)
            out.append(f'{mode:5s} {"Y Cb Cr".split()[pi]:2s} {nm:7s} spread {dev.max()-dev.min():5.1f}%  slice-edge(ph{Sp-1}) {dev[Sp-1]:+5.1f}%  internal block edges {("%+5.1f%%"%np.mean(dev[edges])) if edges else "  n/a "}  excess {ex:+5.1f}%  | '+' '.join(f'{x:+.1f}' for x in dev))
    return '\n'.join(out)
if __name__=='__main__':
    a=sys.argv; kw={}
    for k in ('--fmt','--depth','--f0'):
        if k in a: kw[k[2:]]=int(a[a.index(k)+1])
    print(main(a[1],a[2],int(a[3]),int(a[4]),int(a[5]),int(a[6]),**kw))
