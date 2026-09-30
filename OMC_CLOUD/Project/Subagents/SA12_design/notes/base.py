import sys, json, numpy as np
sys.path.insert(0,'/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA11_plan/notes')
import struct_s as S
path,W,H,fr,sh,tag=sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),int(sys.argv[4]),int(sys.argv[5]),sys.argv[6]
Qfs=json.loads(sys.argv[7]); kls=json.loads(sys.argv[8])
planes=S.load(path,W,H,fr)
out={}
for k in kls:
    r=S.run(planes,sh,S.TODAY,7,Qfs,'tx',kll=k)
    ph=S.phase_tx(planes,sh,S.TODAY,7,7.0,k)
    out[str(k)]=[(a,b,c,d) for a,b,c,d in r]; out['phase'+str(k)]=ph
json.dump(out,open(tag+'.base.json','w')); print('base done',tag)
