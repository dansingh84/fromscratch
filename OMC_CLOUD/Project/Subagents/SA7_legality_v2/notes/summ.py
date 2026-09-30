import sys, re, statistics as st
def pct(a,p):
    if not a: return 0
    a=sorted(a); i=int(round((len(a)-1)*p)); return a[i]
for cell in sys.argv[1:]:
    print("=== %s ===" % cell)
    print("  r | slices ok=0 | moves p50/p90/p99/max | inverses p50/p90/p99/max | lies | legacy slices/passes/fb/worst | oob")
    for r in (0,1,2,3):
        f="out/D/%s_r%d.enc.log"%(cell,r)
        mv=[];iv=[];ok0=0;n=0;lies=0
        gl=("-","-","-","-"); oob="?"
        for line in open(f):
            m=re.match(r'LATTAPPLY f\d+ s\d+ ok=(\d+) moves=(\d+) inv=(\d+) lies=(\d+)',line)
            if m:
                n+=1
                if m.group(1)=='0': ok0+=1
                mv.append(int(m.group(2))); iv.append(int(m.group(3))); lies+=int(m.group(4))
            m=re.search(r'gamut-strict: \d+ passes max, (\d+) slices repaired in (\d+) passes \((\d+) fell back',line)
            if m: gl=(m.group(1),m.group(2),m.group(3),gl[3])
            m=re.search(r'worst total passes (\d+) of cap',line)
            if m: gl=(gl[0],gl[1],gl[2],m.group(1))
            m=re.search(r'gamut: (-?\d+) committed samples outside legal range',line)
            if m: oob=m.group(1)
        print("  %d | %4d  %3d | %5d/%5d/%5d/%5d | %5d/%5d/%5d/%5d | %5d | %s/%s/%s/%s | %s" % (
            r,n,ok0,pct(mv,.5),pct(mv,.9),pct(mv,.99),max(mv or [0]),
            pct(iv,.5),pct(iv,.9),pct(iv,.99),max(iv or [0]),lies,gl[0],gl[1],gl[2],gl[3],oob))
    print("  PSNR mean over 12 frames (Y/Cb/Cr) and worst frame:")
    for r in (0,1,2,3):
        t=open("out/D/%s_r%d.psnr.txt"%(cell,r)).read().split()
        vals=[tuple(float(x) for x in v.split('/')) for v in t if '/' in v]
        my=[sum(v[i] for v in vals)/len(vals) for i in range(3)]
        wy=[min(v[i] for v in vals) for i in range(3)]
        print("   r%d mean %.3f/%.3f/%.3f   worstframe %.3f/%.3f/%.3f"%(r,my[0],my[1],my[2],wy[0],wy[1],wy[2]))
