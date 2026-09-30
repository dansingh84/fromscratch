"""Rate-quality curve of the NEST v3 temporal model vs today's real decodes (SA7 DM a0), steady-state frames 2..11.
Coded rate = zeroth-order entropy x static-tANS overhead factor (1.15 at <=0.5 bpp, 1.06 at >=0.8, linear between)."""
import sys, os, subprocess, numpy as np
sys.path.insert(0,'.')
import temporal3 as T, common14 as cm
SCR=sys.argv[1]; cell=sys.argv[2]; D0S=[int(x) for x in sys.argv[3].split(',')]
TOOLS='/home/user/fromscratch/OMC_CLOUD/Project/Subagents/shared_tools'
DM='/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/out/DM'
path,W,H,fmt,dep=cm.CELLS[cell]; cw=W//2; fw=W*H+2*cw*H; NF=12
def factor(b): return 1.15 if b<=0.5 else (1.06 if b>=0.8 else 1.15+(b-0.5)*(1.06-1.15)/0.3)
def trim(src,dst,a,b):
    d=np.fromfile(src,dtype='<u2',count=fw*b)[fw*a:]; d.tofile(dst)
def neg(ref,dec,n):
    r=subprocess.run(['bash',TOOLS+'/negscore.sh',ref,dec,str(W),str(H),fmt,str(dep),str(n)],capture_output=True,text=True)
    return float(r.stdout.strip().split()[-1])
def psn(src,dec,a,b):
    S=np.fromfile(src,dtype='<u2',count=fw*b).astype(float); D=np.fromfile(dec,dtype='<u2',count=fw*b).astype(float)
    out=[]
    for f in range(a,b):
        s=S[f*fw:(f+1)*fw]; d=D[f*fw:(f+1)*fw]
        pl=[(0,W*H),(W*H,W*H+cw*H),(W*H+cw*H,fw)]
        out.append([10*np.log10(1023**2/np.mean((s[x:y]-d[x:y])**2)) for x,y in pl])
    o=np.array(out); return o.mean(0), o.min(0)
srcs=os.path.join(SCR,f'{cell}_src2.yuv'); trim(path,srcs,2,NF)
rows=[]
for D0 in D0S:
    dec=os.path.join(SCR,f'{cell}_nest_{D0}.yuv')
    st=T.run(cell,D0,NF,False,gen2=True,write=dec)
    ent=np.mean([s[1] for s in st]); coded=ent*factor(ent)
    d2=dec+'.s'; trim(dec,d2,2,NF)
    v=neg(srcs,d2,NF-2); pm,pw=psn(path,dec,2,NF)
    g2=all(s[4] for s in st); oob=sum(s[3] for s in st)
    rows.append(('NEST',D0,coded,v,pm,pw,g2,oob)); os.remove(dec); os.remove(d2)
    print(f"NEST {cell} D0={D0} coded_bpp={coded:.3f} VMAF-NEG(f2-11)={v:.3f} PSNR mean Y/Cb/Cr={pm[0]:.2f}/{pm[1]:.2f}/{pm[2]:.2f} worst={pw[0]:.2f}/{pw[1]:.2f}/{pw[2]:.2f} gen2_all_same={g2} oob={oob}",flush=True)
for b in ('0.5','1.0'):
    dec=f'{DM}/{cell}_b{b}_a0.d.yuv'
    if not os.path.exists(dec): continue
    d2=os.path.join(SCR,'today.s'); trim(dec,d2,2,NF)
    v=neg(srcs,d2,NF-2); pm,pw=psn(path,dec,2,NF); os.remove(d2)
    print(f"TODAY {cell} {b} bpp (exact CBR) VMAF-NEG(f2-11)={v:.3f} PSNR mean Y/Cb/Cr={pm[0]:.2f}/{pm[1]:.2f}/{pm[2]:.2f} worst={pw[0]:.2f}/{pw[1]:.2f}/{pw[2]:.2f}",flush=True)
os.remove(srcs)
