#!/usr/bin/env python3
import os,re,sys
CELLS=["dng720","dng1080","spot","gfx"]
print("(a) per-plane PSNR, mean over 12 frames, and the worst frame")
print("cell     bpp | d1m ON  Y/Cb/Cr        | d1m=0   Y/Cb/Cr        | delta Y/Cb/Cr        | worst-frame delta Y")
for c in CELLS:
    for B in ("0.5","1.0"):
        r={}
        for a in (0,1):
            f="out/DM/%s_b%s_a%d.psnr"%(c,B,a)
            if not os.path.exists(f): r=None; break
            v=[tuple(float(x) for x in t.split('/')) for t in open(f).read().split() if '/' in t]
            if not v: r=None; break
            r[a]=(v,[sum(x[i] for x in v)/len(v) for i in range(3)])
        if not r: continue
        m0,m1=r[0][1],r[1][1]
        wf=min(r[1][0][i][0]-r[0][0][i][0] for i in range(len(r[0][0])))
        print("%-8s %s | %6.3f/%6.3f/%6.3f | %6.3f/%6.3f/%6.3f | %+.3f/%+.3f/%+.3f | %+.3f"%(
            c,B,m0[0],m0[1],m0[2],m1[0],m1[1],m1[2],m1[0]-m0[0],m1[1]-m0[1],m1[2]-m0[2],wf))
print()
print("(b) seam: row bias at rows 12-15 (Y), d1m ON -> d1m=0")
for c in CELLS:
    for B in ("0.5","1.0"):
        out=[]
        for a in (0,1):
            f="out/DM/%s_b%s_a%d.rowbias"%(c,B,a)
            if not os.path.exists(f): out=None; break
            t=open(f).read()
            m=re.search(r'bias Y: inner ([-+][\d.]+) r12 ([-+][\d.]+) r13 ([-+][\d.]+) r14 ([-+][\d.]+) r15 ([-+][\d.]+)',t)
            out.append([float(x) for x in m.groups()] if m else None)
        if not out or out[0] is None or out[1] is None: continue
        print("%-8s %s | ON  inner %+.3f r13 %+.3f r14 %+.3f r15 %+.3f | OFF inner %+.3f r13 %+.3f r14 %+.3f r15 %+.3f"%(
            c,B,out[0][0],out[0][2],out[0][3],out[0][4],out[1][0],out[1][2],out[1][3],out[1][4]))
print()
print("(c) energy-meter flat share, frame 8 (a NUMBER, not a verdict)")
for c in CELLS:
    for B in ("0.5","1.0"):
        vals=[]
        for a in (0,1):
            f="out/DM/%s_b%s_a%d.flat"%(c,B,a)
            if not os.path.exists(f): vals=None; break
            v=[float(x) for x in re.findall(r'(\d+\.\d+)%',open(f).read())]
            vals.append(v[:3] if len(v)>=3 else None)
        if not vals or vals[0] is None or vals[1] is None: continue
        print("%-8s %s | ON %5.2f/%5.2f/%5.2f | OFF %5.2f/%5.2f/%5.2f | d %+.2f/%+.2f/%+.2f"%(
            c,B,vals[0][0],vals[0][1],vals[0][2],vals[1][0],vals[1][1],vals[1][2],
            vals[1][0]-vals[0][0],vals[1][1]-vals[0][1],vals[1][2]-vals[0][2]))
