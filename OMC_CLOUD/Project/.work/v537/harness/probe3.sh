#!/bin/bash
# probe3.sh LABEL "ENV=V ..."  -- print one arm's mean signed error at the three
# blocks sect.51.7 uses to attribute a residual blotch to a named change.
# Run from the working root; W is the working root.
W="$(cd "$(dirname "$0")/.." && pwd)"
ARM=${ARM:-$W/arms/dng_1920x1080_422_10.yuv}
env $2 $W/v51/omc_v5.1.1/omc_enc -i "$ARM" -o /tmp/p.omc \
    -w 1920 -h 1080 --fmt 422 --depth 10 --bpp 0.5 -n 6 2>&1 \
  | grep -oP 'gamut: \K[0-9]+' | tr '\n' ' '
$W/v51/omc_v5.1.1/omc_dec -i /tmp/p.omc -o /tmp/p.yuv >/dev/null 2>&1
ARM="$ARM" python3 - "$1" <<'EOF'
import numpy as np, os, sys
W,H=1920,1080; per=W*H*2
arm=os.environ['ARM']
def b(f,y,x):
    s=np.fromfile(arm,dtype='<u2',count=per,offset=f*per*2)[:W*H].reshape(H,W).astype(float)
    d=np.fromfile('/tmp/p.yuv',dtype='<u2',count=per,offset=f*per*2)[:W*H].reshape(H,W).astype(float)
    return (d-s)[y:y+4,x:x+32].mean()
print("%-30s f0/560/832 %+7.1f  f5/976/864 %+7.1f  f3/400/800 %+7.1f"
      % (sys.argv[1], b(0,560,832), b(5,976,864), b(3,400,800)))
EOF
rm -f /tmp/p.omc /tmp/p.yuv
