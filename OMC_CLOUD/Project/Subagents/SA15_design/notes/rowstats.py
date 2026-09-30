# per-row-phase error statistics inside the S-row slice, Y/Cb/Cr, intra (frame 0 + refresh slices) and inter
import sys, numpy as np
from common import read_frame
def main(src,dec,W,H,N,SH=16,first=2):
    nsl=H//SH
    acc={}  # (mode,plane) -> [sum|e| per phase, sum e, sum step, count, stepcount]
    def add(mode,pi,e,rows):
        a=acc.setdefault((mode,pi),np.zeros((5,SH)))
        ae=np.abs(e).mean(1); se=e.mean(1); st=np.abs(np.diff(e,axis=0)).mean(1)
        for r in rows:
            ph=r%SH; a[0,ph]+=ae[r]; a[1,ph]+=se[r]; a[3,ph]+=1
            if r+1<e.shape[0]: a[2,ph]+=st[r]; a[4,ph]+=1
    for t in range(N):
        S=read_frame(src,W,H,t); Dd=read_frame(dec,W,H,t)
        for pi in range(3):
            e=Dd[pi].astype(float)-S[pi]
            if t==0: add('intra0',pi,e,range(H)); continue
            if t<first: continue
            s=(t-1)%nsl; r0,r1=SH*s,SH*(s+1)
            add('refresh',pi,e,range(r0,r1))
            add('inter',pi,e,[r for r in range(H) if not (r0-SH<=r<r1+8)])
    out=[]
    for mode in ('intra0','inter','refresh'):
        for pi,nm in enumerate(('Y','Cb','Cr')):
            a=acc.get((mode,pi))
            if a is None: continue
            mae=a[0]/np.maximum(a[3],1); bias=a[1]/np.maximum(a[3],1); stp=a[2]/np.maximum(a[4],1)
            dev=100*(mae/mae.mean()-1); sdev=100*(stp/stp.mean()-1)
            out.append(f'{mode:7s} {nm:2s} mean|e| {mae.mean():6.3f}  phase dev% '+' '.join(f'{v:+5.1f}' for v in dev)+f'  spread {dev.max()-dev.min():4.1f}%')
            out.append(f'{mode:7s} {nm:2s} step    {stp.mean():6.3f}  phase dev% '+' '.join(f'{v:+5.1f}' for v in sdev)+f'  spread {sdev.max()-sdev.min():4.1f}%  (phase {SH-1} = slice boundary)')
            out.append(f'{mode:7s} {nm:2s} bias    '+' '.join(f'{v:+5.2f}' for v in bias))
    return '\n'.join(out)
if __name__=='__main__':
    a=sys.argv; print(main(a[1],a[2],int(a[3]),int(a[4]),int(a[5]),int(a[6]) if len(a)>6 else 16))
