#!/usr/bin/env python3
"""[SA7] summarise the within-bin escape oracle logs."""
import sys, re, math, os
def pct(a,p):
    if not a: return 0
    a=sorted(a); return a[min(len(a)-1,int(round((len(a)-1)*p)))]
BANDS="LL5 HL5 HL4 HL3 LH2 HL2 HH2 LH1 HL1 HH1".split()
CELLGEO={"spot":(1920,1080,16),"vb":(1920,1080,16),"gfx":(448,256,8),"dng1080":(1920,1080,16),"dng720":(1280,720,8)}
cells=sys.argv[1:]
for cell in cells:
    print("\n=== %s ===" % cell)
    print(" k | slices | closed | bad0 | left | %%resid | esc/slice p50/p90/p99/max | moves p50/p90/p99/max | inv p50/p90/p99/max | bits%% mean/worst (delta) | bits%% worst (16b) | pmax | bs>0")
    for k in (1,2,3,4):
        f="out/E/%s_b%s_k%d.log"%(cell,os.environ.get("BPP","0.5"),k)
        if not os.path.exists(f): continue
        bits_per_slice=None; Nco=None
        esc=[];mv=[];iv=[];bad0=0;left=0;n=0;ok=0;pmax=0;bsn=0
        band=[0]*10; col=[0]*32; emag=[0]*16
        for line in open(f):
            if line.startswith("omc_enc:") and "bits/slice" in line:
                m=re.search(r'(\d+) bits/slice',line); bits_per_slice=int(m.group(1))
            if line.startswith("SA7B"):
                t=line.split()
                i=t.index("band"); j=t.index("col"); l=t.index("emag")
                for z,v in enumerate(t[i+1:j]): band[z]+=int(v)
                for z,v in enumerate(t[j+1:l]): col[z]+=int(v)
                for z,v in enumerate(t[l+1:]):  emag[z]+=int(v)
                continue
            if not line.startswith("SA7 "): continue
            d=dict(x.split("=",1) for x in line.split() if "=" in x)
            n+=1; ok+= (d["ok"]=="1")
            bad0+=int(d["bad0"]); left+=int(d["left"])
            esc.append(int(d["esc"])); mv.append(int(d["moves"])); iv.append(int(d["inv"]))
            pmax=max(pmax,int(d["pmax"])); bsn += (int(d["bs"])>0)
        if not n: continue
        # bit cost: position + k.  N = coefficients per slice (4:2:2) from the cell geometry
        W,H,SH = CELLGEO[cell]
        Nco = SH*(W+W//2+W//2)
        def bits(e):
            if e<=0: return 0
            delta = math.log2(max(Nco/e,2))+2
            return e*(delta+k)
        mean_b = sum(bits(e) for e in esc)/n
        worst_b= max(bits(e) for e in esc)
        worst16= max(e*(16+k) for e in esc)
        B=bits_per_slice or 1
        print(" %d | %5d | %5d | %6d | %5d | %5.2f | %4d/%4d/%4d/%4d | %4d/%5d/%5d/%5d | %5d/%5d/%5d/%5d | %5.2f/%5.2f | %5.2f | %4d | %d"%(
            k,n,ok,bad0,left,100.0*left/max(bad0,1),
            pct(esc,.5),pct(esc,.9),pct(esc,.99),max(esc),
            pct(mv,.5),pct(mv,.9),pct(mv,.99),max(mv),
            pct(iv,.5),pct(iv,.9),pct(iv,.99),max(iv),
            100*mean_b/B,100*worst_b/B,100*worst16/B,pmax,bsn))
        if k==4:
            tot=sum(band) or 1
            print("    band share: "+" ".join("%s %.1f%%"%(BANDS[z],100*band[z]/tot) for z in range(10) if band[z]))
            ct=sum(col) or 1
            print("    column buckets (32 across the plane, %% of escapes): "+" ".join("%.1f"%(100*c/ct) for c in col))
            print("    column spread: min %.2f%% max %.2f%% (uniform = 3.12%%), ratio max/min %.2f"%(
                100*min(col)/ct,100*max(col)/ct, (max(col)/max(min(col),1))))
            et=sum(emag) or 1
            print("    |e| histogram (0..15, %% of escapes): "+" ".join("%.1f"%(100*x/et) for x in emag))
            cum=0; 
            for z in range(16):
                cum+=emag[z]
                if cum>=0.99*et: print("    99%% of escapes have |e| <= %d (of a %d-bit budget, max %d)"%(z,k,(1<<(k-1))));break
