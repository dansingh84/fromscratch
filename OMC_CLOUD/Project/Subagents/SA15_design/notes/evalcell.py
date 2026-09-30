# Steady-state evaluation of CPP decode vs today's real decode, same source, frames F0..F1-1:
# VMAF-NEG (shared negscore.sh), per-plane PSNR, owner smudge/artifact/flatness tools on frame FT.
import sys, os, subprocess, numpy as np
from common import *
T='/home/user/fromscratch/OMC_CLOUD/Project/Subagents/shared_tools/'
DM='/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/out/DM/'
OUT='/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA15_design/out/eval/'
def cut(src,dst,W,H,f0,f1):
    n=W*H*2*2
    with open(src,'rb') as a, open(dst,'wb') as b:
        a.seek(n*f0); b.write(a.read(n*(f1-f0)))
def run(cmd):
    r=subprocess.run(cmd,capture_output=True,text=True)
    if r.returncode!=0: raise SystemExit(f'FAILED rc={r.returncode}: {" ".join(cmd)}\n{r.stderr[-2000:]}')
    return r.stdout
cell,dmname,mine,tag=sys.argv[1:5]; F0,F1,FT=2,12,8
path,W,H=CELLS[cell]; os.makedirs(OUT+tag,exist_ok=True); o=OUT+tag+'/'
arms={'today':(dmname if '/' in dmname else DM+dmname+'.d.yuv'),'cpp':mine}
cut(path,o+'src.yuv',W,H,F0,F1)
res={}
for k,v in arms.items():
    cut(v,o+k+'.yuv',W,H,F0,F1)
    neg=run(['bash',T+'negscore.sh',o+'src.yuv',o+k+'.yuv',str(W),str(H),'422','10',str(F1-F0)]).strip()
    ps=np.array([[psnr(a,b) for a,b in zip(read_frame(o+'src.yuv',W,H,f),read_frame(o+k+'.yuv',W,H,f))] for f in range(F1-F0)])
    res[k]=(neg,ps.mean(0),ps.min(0))
    ft=FT-F0
    sm=run(['python3',T+'smudgegroups.py',o+'src.yuv',o+k+'.yuv',str(W),str(H),str(ft),o+k+'_smudge'])
    fp=run(['python3',T+'flatplane.py',o+'src.yuv',o+k+'.yuv',str(W),str(H),str(ft)])
    am=[]
    for pl in ('Y','Cb','Cr'):
        os.makedirs(o+k+'_am',exist_ok=True)
        am.append(run(['python3',T+'artifactmap.py',o+'src.yuv',o+k+'.yuv',str(W),str(H),str(ft),o+k+'_am','--plane',pl]).strip().splitlines()[-1])
    with open(o+k+'_tools.txt','w') as f: f.write(sm+'\n'+fp+'\n'+'\n'.join(am)+'\n')
    print(f'{tag} {k:5s} NEG={neg} PSNR mean Y/Cb/Cr={res[k][1][0]:.2f}/{res[k][1][1]:.2f}/{res[k][1][2]:.2f} worst-frame={res[k][2][0]:.2f}/{res[k][2][1]:.2f}/{res[k][2][2]:.2f}',flush=True)
    print('   smudgegroups:',' | '.join(l.strip() for l in sm.splitlines() if l.strip()[:2] in ('Y ','Cb','Cr','Y:','Cb:','Cr:') or 'group' in l.lower())[:600])
    print('   flatplane:',' | '.join(l.strip() for l in fp.splitlines()[-4:]))
    print('   artifactmap:',' | '.join(am))
for k in arms: os.remove(o+k+'.yuv')
os.remove(o+'src.yuv')
