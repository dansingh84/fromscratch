"""VMAF-NEG + per-plane PSNR: NEST (legal-by-construction, demotion closure) vs the same quantised
transform with a plain output clip (the illegal/inexact reference).  One frame, 4:2:2 10-bit, all planes."""
import sys, os, subprocess, numpy as np
sys.path.insert(0,'.')
import nests as nest, enc3s as enc3, common14 as cm
cm.nest = nest
SCR=sys.argv[1]; n2d,n1d=2,3
T='/home/user/fromscratch/OMC_CLOUD/Project/Subagents/shared_tools'
def code_plane(X,dep,D0):
    M=(1<<dep)-1; lo=np.zeros(X.shape,np.int64); hi=np.full(X.shape,M,np.int64)
    loI=np.full(X.shape,-nest.INF); hiI=np.full(X.shape,nest.INF)
    sh=cm.shifts_for(n2d,n1d,X.shape,D0)
    ql,top,rec,st=enc3.encode(X,lo,hi,n2d,n1d,sh)
    desc,bits=nest.read_description(ql,top)
    lev,(L,_,_)=nest.analysis(X,loI,hiI,n2d,n1d)
    q0=[{n:{'val':nest.R(nest.Q(d['val'],sh[(i,n)]),sh[(i,n)]),'esc':np.zeros(d['val'].shape,np.int8)} for n,d in l.items() if n!='win'} for i,l in enumerate(lev)]
    t0={'val':nest.R(nest.Q(L,sh['top']),sh['top']),'esc':np.zeros(L.shape,np.int8)}
    r0,_,_=nest.synthesis(t0,q0,loI,hiI,n2d,n1d)
    b0=sum(nest.entropy_bits(d['val']>>sh[(i,n)]) for i,l in enumerate(q0) for n,d in l.items())+nest.entropy_bits(t0['val']>>sh['top'])
    return rec, np.clip(r0,0,M), bits, b0
for cell in ('dng1080','spot'):
    planes,dep=cm.read_frame(cell,8); path,W,H,fmt,_=cm.CELLS[cell]
    ref=os.path.join(SCR,f'{cell}_src.yuv'); np.concatenate([p.ravel() for p in planes]).astype('<u2').tofile(ref)
    for D0 in (48,128):
        outs={'nest':[], 'clip':[]}; bits={'nest':0,'clip':0}
        for X in planes:
            r,c,b,b0=code_plane(X,dep,D0)
            outs['nest'].append(r); outs['clip'].append(c); bits['nest']+=b; bits['clip']+=b0
        for k in outs:
            f=os.path.join(SCR,f'{cell}_{D0}_{k}.yuv'); np.concatenate([p.ravel() for p in outs[k]]).astype('<u2').tofile(f)
            v=subprocess.run(['bash',T+'/negscore.sh',ref,f,str(W),str(H),fmt,str(dep),'1'],capture_output=True,text=True)
            ps=[cm.psnr(planes[i],outs[k][i],dep) for i in range(3)]
            print(f"{cell} D0={D0} {k:4s} bits/lumapx={bits[k]/(W*H):.4f} VMAF-NEG={v.stdout.strip().splitlines()[-1] if v.stdout.strip() else v.stderr[-200:]} PSNR Y/Cb/Cr={ps[0]:.3f}/{ps[1]:.3f}/{ps[2]:.3f} oob={sum(int(((p<0)|(p>1023)).sum()) for p in outs[k])}",flush=True)
            if k=='nest':
                d=[np.abs(outs['nest'][i]-outs['clip'][i]) for i in range(3)]
                print(f"   |nest-clip| px differing Y/Cb/Cr={[int((x>0).sum()) for x in d]} max={[int(x.max()) for x in d]}")
        for k in outs:
            os.remove(os.path.join(SCR,f'{cell}_{D0}_{k}.yuv'))
    os.remove(ref)
