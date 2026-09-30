"""Today's codec (.work/v537, shipped defaults) on every comparison cell at 0.5 and 1.0 bpp, 12 frames."""
import sys, os, subprocess, json
sys.path.insert(0,'.')
import metrics
E='/home/user/fromscratch/OMC_CLOUD/Project/.work/v537/omc_enc'; Dd='/home/user/fromscratch/OMC_CLOUD/Project/.work/v537/omc_dec'
A='/home/user/fromscratch/OMC_CLOUD/Project/.work/arms'
SCR=sys.argv[1]; OUT='../out/today.json'
cells={'dng720':(A+'/dng_1280x720_422_10.yuv',1280,720),'gfx':(A+'/cf_gfx_448x256_422_10.yuv',448,256),
 'spot':(A+'/long/spotrobotL_1920x1080_422_10.yuv',1920,1080),'floor':(A+'/long/floorballgameL_1920x1080_422_10.yuv',1920,1080),
 'hwy':(A+'/long/highwaydriveL_1920x1080_422_10.yuv',1920,1080),'volley':(A+'/long/volleyballgameL_1920x1080_422_10.yuv',1920,1080)}
res=json.load(open(OUT)) if os.path.exists(OUT) else {}
for c,(src,W,H) in cells.items():
    for b in ('0.5','1.0'):
        k=f'{c}_{b}'
        if k in res: continue
        om=os.path.join(SCR,'t.omc'); dec=os.path.join(SCR,'t.yuv')
        r=subprocess.run([E,'-i',src,'-o',om,'-w',str(W),'-h',str(H),'--fmt','422','--depth','10','--bpp',b,'-n','12'],capture_output=True,text=True)
        if r.returncode!=0: print('ENC FAIL',k,r.returncode,r.stderr[-300:]); continue
        r2=subprocess.run([Dd,'-i',om,'-o',dec],capture_output=True,text=True)
        if r2.returncode!=0: print('DEC FAIL',k,r2.stderr[-300:]); continue
        sz=os.path.getsize(dec)
        s=metrics.summary(src,dec,W,H,'422',SCR); s['bytes']=os.path.getsize(om); s['bpp_actual']=8*s['bytes']/(W*H*12)
        res[k]=s; json.dump(res,open(OUT,'w'),indent=1); print(k,s,flush=True)
        os.remove(om); os.remove(dec)
