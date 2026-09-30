import sys, numpy as np
a=np.fromfile(sys.argv[1],dtype=np.uint16).astype(np.int32)-2048
np.clip(a,0,(1<<int(sys.argv[3]))-1).astype(np.uint16).tofile(sys.argv[2])
