#!/usr/bin/env python3
import os, subprocess, sys
ARMS="/home/user/fromscratch/OMC_CLOUD/Project/.work/arms"
C={"spot":(ARMS+"/long/spotrobotL_1920x1080_422_10.yuv",1920,1080),
   "vb":(ARMS+"/long/volleyballgameL_1920x1080_422_10.yuv",1920,1080),
   "gfx":(ARMS+"/cf_gfx_448x256_422_10.yuv",448,256),
   "dng1080":(ARMS+"/dng_1920x1080_422_10.yuv",1920,1080),
   "dng720":(ARMS+"/dng_1280x720_422_10.yuv",1280,720)}
print("cell     bpp | base Y/Cb/Cr        | two-phase Y/Cb/Cr    | delta")
for c,(S,W,H) in C.items():
    for B in ("0.5","1.0"):
        r={}
        for tag,suf in (("base","bdec"),("2ph","dec")):
            f="out/P/%s_b%s.%s.yuv"%(c,B,suf)
            if not os.path.exists(f): r=None; break
            g=f
            if H==1080:
                g="out/P/_t.yuv"; subprocess.run([sys.executable,"notes/crop.py",f,g,"1920","1088","1080","12"],check=True)
            o=subprocess.run([sys.executable,"../shared_tools/planepsnr.py",S,g,str(W),str(H),"422","10",tag],
                             capture_output=True,text=True,check=True).stdout.split()
            v=[tuple(float(x) for x in t.split('/')) for t in o if '/' in t]
            r[tag]=[sum(x[i] for x in v)/len(v) for i in range(3)]
        if not r: continue
        b,p=r["base"],r["2ph"]
        print("%-8s %s | %6.3f/%6.3f/%6.3f | %6.3f/%6.3f/%6.3f | %+.3f/%+.3f/%+.3f"%(
            c,B,b[0],b[1],b[2],p[0],p[1],p[2],p[0]-b[0],p[1]-b[1],p[2]-b[2]))
try: os.remove("out/P/_t.yuv")
except: pass
