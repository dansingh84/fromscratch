# train static tANS tables on footage DISJOINT from every test cell
import numpy as np, seq2, sys
A='/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/'
clips=[A+'cityalley_1920x1080_422_10.yuv',A+'bosphorus_1920x1080_422_10.yuv',A+'readysetgo_1920x1080_422_10.yuv',
       A+'long/trafficlightsL_1920x1080_422_10.yuv',A+'long/winterdriveL_1920x1080_422_10.yuv',
       A+'long/floorballtrainL_1920x1080_422_10.yuv',A+'long/highwayviewL_1920x1080_422_10.yuv']
tabs=seq2.Tables(path='/nonexistent'); tabs.ok=False
SET=sys.argv[1]
if SET=='B': clips=[c for c in clips if 'floorballtrain' not in c and 'highwayview' not in c]
sched=[52,44,48,56,40,50]
for ci,c in enumerate(clips):
    for hp in (False,):
        cod=seq2.Codec(1920,1080,tabs=tabs,train=True,S=8,hp=hp)
        for t in range(6):
            fr=seq2.read(c,1920,1080,t)
            cod.encode(fr,kfixed=sched[(t+ci)%6]-(0 if t else 0))
        print('trained',c.split('/')[-1],flush=True)
seq2.build_tables(tabs.cnt,tabs.vcnt,path='/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA15_design/out/tables_'+SET+'.pkl')
print('keys',len(tabs.cnt),'symbols',int(sum(v.sum() for v in tabs.cnt.values())))
