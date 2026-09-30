import sys, os, subprocess, numpy as np
ROOT=os.environ.get("R","/tmp/fix")
sys.path.insert(0,ROOT+"/harness")
import uc_verify as V
from common import write_yuv, read_yuv
T="/tmp/al"; os.makedirs(T,exist_ok=True)
W=H=768
def scale(src,dw,dh):
    write_yuv(T+"/i.yuv",[[src,src.copy(),src.copy()]])
    r=subprocess.run([ROOT+"/omc_uc_tool","scale","-i",T+"/i.yuv","-o",T+"/o.yuv",
        "-w",str(W),"-h",str(H),"--fmt","444","--depth","10","--frames","1",
        "--out-w",str(dw),"--out-h",str(dh)],capture_output=True,text=True)
    if r.returncode: return None
    return read_yuv(T+"/o.yuv",dw,dh,dw,1)[0][0].astype(float)
def amp_at(sig, cyc):
    """amplitude of the component with `cyc` cycles across the row"""
    n=len(sig); k=np.exp(-2j*np.pi*cyc*np.arange(n)/n)
    return 2*abs((sig-sig.mean())@k)/n
mid=(V.LO+V.HI)/2.0; A=(V.HI-V.LO)/2.0*0.8
print("2:1 DOWNCONVERSION -- horizontal sinusoid injection, %d -> %d"%(W,W//2))
print("f is in units of the OUTPUT Nyquist; ideal decimation passes f<1 and kills f>1\n")
print("  %-8s %-14s %-12s %s"%("f","input cycles","output amp","verdict"))
for f in (0.25,0.5,0.75,0.95,1.15,1.4,1.7,1.9):
    cyc = f*(W//2)/2.0                      # cycles across the row
    x=np.arange(W)
    row=mid+A*np.cos(2*np.pi*cyc*x/W)
    src=np.tile(row,(H,1)).round().clip(0,1023).astype(np.uint16)
    o=scale(src,W//2,H//2)
    if o is None: print("  %-8.2f FAILED"%f); continue
    # the alias of `cyc` in the output lands at |cyc| folded about output Nyquist
    outn=(W//2)/2.0
    ac = cyc if cyc<=outn else (W//2)-cyc
    a=amp_at(o[o.shape[0]//2], abs(ac))/A
    print("  %-8.2f %-14.1f %-12.4f %s"%(f,cyc,a,"passband" if f<1 else
          ("OK, suppressed" if a<0.05 else "ALIAS %.3f"%a)))
