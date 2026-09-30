#!/usr/bin/env python3
import sys, re, os, math
CELLS=["spot","vb","gfx","dng1080","dng720"]
GEO={"spot":(1920,1080,16),"vb":(1920,1080,16),"gfx":(448,256,8),"dng1080":(1920,1080,16),"dng720":(1280,720,8)}
def pct(a,p):
    if not a: return 0
    a=sorted(a); return a[min(len(a)-1,int(round((len(a)-1)*p)))]
print("(a) two-phase WHOLE-STEP pass: completeness")
print("cell     bpp | slices | closed<=2 |  %% | bad0 | left after 1 | left after 2 | moves | conflict | nocover | guard | deep0 | deep2")
RES={}
for c in CELLS:
    W,H,SH=GEO[c]
    for B in ("0.5","1.0"):
        f="out/P/%s_b%s.p3.log"%(c,B)
        if not os.path.exists(f): continue
        n=ok=b0=l1=l2=mv=cf=nc=gd=0; d0=d2=0; res=set()
        for line in open(f):
            if not line.startswith("SA7P "): continue
            d=dict(x.split("=",1) for x in line.split() if "=" in x)
            t=line.split(); fr=int(t[1][1:]); sl=int(t[2][1:])
            n+=1; ok+= (d["ok"]=="1")
            b0+=int(d["bad0"]); l1+=int(d["left1"]); l2+=int(d["left2"]); mv+=int(d["moves"])
            cf+=int(d["conflict"]); nc+=int(d["nocover"]); gd+=int(d["guard"])
            d0=max(d0,int(d["deep0"])); d2=max(d2,int(d["deep2"]))
            if d["ok"]!="1": res.add((fr,sl))
        if not n: continue
        RES[(c,B)]=res
        print("%-8s %s | %6d | %9d |%4.0f | %5d | %12d | %12d | %5d | %8d | %7d | %5d | %5d | %5d"%(
            c,B,n,ok,100.0*ok/n,b0,l1,l2,mv,cf,nc,gd,d0,d2))
print()
print("(b) residue slices and the escape bits they need, against the bank cap")
print("cell     bpp | residue slices | of all slices %% | esc coeffs/residue p50/p90/max | escape bits p50/p90/max | bits as %% of slice budget | %% of the 2x cap draw")
for c in CELLS:
    W,H,SH=GEO[c]; Nco=SH*(W+W//2+W//2)
    for B in ("0.5","1.0"):
        key=(c,B)
        if key not in RES: continue
        f="out/P/%s_b%s.esc.log"%(c,B)
        if not os.path.exists(f): continue
        slice_bits=int(round(float(B)*W*SH))
        tot_slices=0
        for line in open("out/P/%s_b%s.p3.log"%(c,B)):
            if line.startswith("omc_enc:") and "slices/frame" in line:
                m=re.search(r'(\d+) slices/frame',line); tot_slices=int(m.group(1))*12
        esc=[]
        for line in open(f):
            if not line.startswith("SA7 "): continue
            t=line.split(); fr=int(t[1][1:]); sl=int(t[2][1:])
            if (fr,sl) not in RES[key]: continue
            d=dict(x.split("=",1) for x in line.split() if "=" in x)
            esc.append(int(d["esc"]))
        if not esc: esc=[0]
        def bits(e,k=2):
            if e<=0: return 0
            return int(e*(math.log2(max(Nco/e,2))+2+k))
        bb=[bits(e) for e in esc]
        nres=len(RES[key])
        print("%-8s %s | %14d | %15.2f | %10d/%5d/%5d | %8d/%6d/%6d | %10.2f/%5.2f | %6.2f"%(
            c,B,nres,100.0*nres/max(tot_slices,1),pct(esc,.5),pct(esc,.9),max(esc),
            pct(bb,.5),pct(bb,.9),max(bb),100.0*pct(bb,.5)/slice_bits,100.0*max(bb)/slice_bits,
            100.0*max(bb)/slice_bits))
