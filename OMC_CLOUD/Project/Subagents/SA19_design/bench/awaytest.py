import numpy as np, sys, yuv, ent, seq, pyr
SA7='/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/'
C={'cut24':(SA7+'cut24.yuv',256,64,0,1023),'ext10':(SA7+'ext_10_422_l0.yuv',512,128,0,1023),'ext10l1':(SA7+'ext_10_422_l1.yuv',512,128,4,1019),
   'gfx':(yuv.ARMS+'cf_gfx_448x256_422_10.yuv',448,256,4,1019),'dng720':(yuv.CELLS['dng720'][0],1280,720,4,1019),'dng720fr':(yuv.CELLS['dng720'][0],1280,720,0,1023)}
tabs=ent.Tables(sys.argv[1])
for cell in sys.argv[2].split(','):
  path,W,H,lo,hi=C[cell]
  if len(sys.argv)>3 and sys.argv[3]=="rl": pyr.RAILLIM=(lo,hi)
  if len(sys.argv)>3 and sys.argv[3]=="rg": pyr.RANGELIM=(lo,hi)
  for bpp in (0.5,1.0,2.0):
    g=seq.Seq(W,H,bpp,tabs,lo=lo,hi=hi); tot=dict(ch=0,tow=0,away=0); hist=[]; oob=0
    for f in range(3):
        x=yuv.read_frame(path,W,H,f); o,b,i=g.encode(x)
        if i['intra']==False and 'V0' not in i: continue
        for p in range(3):
            yu,_,_=pyr.synthesis(i['V0'][p],lo,hi,legal=False); yc=np.clip(yu,lo,hi); oob+=int(((yu<lo)|(yu>hi)).sum())
            s=x[p]; ea=np.abs(o[p]-s); ec=np.abs(yc-s); ch=o[p]!=yc
            tot['ch']+=ch.sum(); tot['tow']+=(ea<ec).sum(); tot['away']+=(ea>ec).sum(); hist+=(ea-ec)[ea>ec].tolist()
    h=np.array(hist) if hist else np.array([0])
    print(cell,bpp,'unclamped out-of-range samples',oob,'| legal vs clip arm: differ',tot['ch'],'closer',tot['tow'],'farther',tot['away'],'excess p50/90/99',np.percentile(h,[50,90,99]).round(1),'max',h.max(),flush=True)
