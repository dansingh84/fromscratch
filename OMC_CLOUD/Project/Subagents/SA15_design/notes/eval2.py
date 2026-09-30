# steady-state evaluation (frames 2..N-1) of a CPP decode vs today's real decode: NEG mean+worst frame (per-frame
# libvmaf, same model/pixfmt as shared_tools/vmafneg.sh), PSNR mean+worst per plane, owner tools on frame 8.
import sys, os, subprocess, numpy as np, seq2
from negf import negframes
from common import psnr
T='/home/user/fromscratch/OMC_CLOUD/Project/Subagents/shared_tools/'
OUT='/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA15_design/out/r2/eval/'
def cut(src,dst,W,H,f0,f1,fmt=422):
    n=sum(a*b for a,b in seq2.plane_shapes(W,H,fmt))*2
    with open(src,'rb') as a, open(dst,'wb') as b: a.seek(n*f0); b.write(a.read(n*(f1-f0)))
def run(cmd):
    r=subprocess.run(cmd,capture_output=True,text=True)
    if r.returncode!=0: raise SystemExit(f'FAILED rc={r.returncode}: {" ".join(cmd)}\n{r.stderr[-800:]}')
    return r.stdout
def main(tag,src,W,H,arms,N=12,F0=2,FT=None,tools=True):
    FT=min(8,N-2) if FT is None else FT
    os.makedirs(OUT+tag,exist_ok=True); o=OUT+tag+'/'
    cut(src,o+'src.yuv',W,H,F0,N); lines=[]
    for k,v in arms.items():
        if not os.path.exists(v): lines.append(f'{tag} {k}: MISSING {v}'); continue
        cut(v,o+k+'.yuv',W,H,F0,N)
        fr,m=negframes(o+'src.yuv',o+k+'.yuv',W,H,N-F0)
        ps=np.array([[psnr(a,b) for a,b in zip(seq2.read(o+'src.yuv',W,H,f),seq2.read(o+k+'.yuv',W,H,f))] for f in range(N-F0)])
        line=f'{tag} {k:6s} NEG mean {m:.2f} worst {min(fr):.2f} | PSNR mean {ps[:,0].mean():.2f}/{ps[:,1].mean():.2f}/{ps[:,2].mean():.2f} worst {ps[:,0].min():.2f}/{ps[:,1].min():.2f}/{ps[:,2].min():.2f}'
        if tools:
            ft=str(FT-F0)
            sm=run(['python3',T+'smudgegroups.py',o+'src.yuv',o+k+'.yuv',str(W),str(H),ft,o+k+'_sm'])
            fp=run(['python3',T+'flatplane.py',o+'src.yuv',o+k+'.yuv',str(W),str(H),ft])
            am=[]
            for pl in ('Y','Cb','Cr'):
                os.makedirs(o+k+'_am',exist_ok=True)
                am.append(run(['python3',T+'artifactmap.py',o+'src.yuv',o+k+'.yuv',str(W),str(H),ft,o+k+'_am','--plane',pl]).strip().splitlines()[-1].split('->')[0].strip())
            smg=[l.split(':')[1].split(',')[0].strip() for l in sm.splitlines() if l.strip()[:3] in ('Y: ','Cb:','Cr:')]
            fpl=[l.split('%')[0].split()[-1] for l in fp.splitlines() if '% of' in l]
            line+=f' | smudge groups Y/Cb/Cr {"/".join(smg)} | artifactmap {" ; ".join(a.split(":")[1].strip() for a in am)} | flat% {"/".join(fpl)}'
        lines.append(line); print(line,flush=True)
        os.remove(o+k+'.yuv')
    os.remove(o+'src.yuv')
    return lines
if __name__=='__main__':
    tag,src,W,H=sys.argv[1],sys.argv[2],int(sys.argv[3]),int(sys.argv[4]); arms=dict(a.split('=',1) for a in sys.argv[5:])
    main(tag,src,W,H,arms,N=int(os.environ.get('N','12')))
