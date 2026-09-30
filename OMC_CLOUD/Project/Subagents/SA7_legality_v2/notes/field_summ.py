#!/usr/bin/env python3
import sys, re, os, glob
CELLS=["spot","vb","gfx","dng1080","dng720"]
ARM={0:"base",1:"A ideal",2:"B detector/legality",3:"C detector/texture"}
print("cell      arm                  passes  fallbacks  oob | PSNR mean Y/Cb/Cr        | worst frame Y/Cb/Cr      | dPSNR vs base")
for c in CELLS:
    base=None
    for a in (0,1,2,3):
        f="out/F/%s_b0.5_a%d.log"%(c,a)
        if not os.path.exists(f): continue
        t=open(f).read()
        m=re.search(r'repaired in (\d+) passes \((\d+) fell',t); p=m.group(1) if m else "-"; fb=m.group(2) if m else "-"
        m=re.search(r'gamut: (-?\d+) committed',t); oob=m.group(1) if m else "?"
        pf="out/F/%s_b0.5_a%d.psnr.txt"%(c,a)
        vals=[tuple(float(x) for x in v.split('/')) for v in open(pf).read().split() if '/' in v] if os.path.exists(pf) else []
        if not vals: continue
        mn=[sum(v[i] for v in vals)/len(vals) for i in range(3)]
        wf=[min(v[i] for v in vals) for i in range(3)]
        if a==0: base=mn
        d="" if a==0 else "  %+.3f/%+.3f/%+.3f"%(mn[0]-base[0],mn[1]-base[1],mn[2]-base[2])
        print("%-9s %-20s %6s %8s %5s | %7.3f/%7.3f/%7.3f | %6.2f/%6.2f/%6.2f |%s"%(c,ARM[a],p,fb,oob,mn[0],mn[1],mn[2],wf[0],wf[1],wf[2],d))
print()
print("energy-meter flat share per plane (frames 8 and 11) -- A NUMBER, NOT A VERDICT")
for c in CELLS:
    for a in (0,1,2,3):
        f="out/F/%s_b0.5_a%d.flat.txt"%(c,a)
        if not os.path.exists(f): continue
        rows=[l.strip() for l in open(f) if '%' in l or 'flat' in l.lower()]
        if rows: print("  %-9s %-20s %s"%(c,ARM[a]," ; ".join(rows[:4])))
