# CPP-LL round-2 sequence model: exact-CBR rate control (exact lanes), per-coefficient step memory,
# bit-metered one-way refresh sweep, decoder simulation (loss), static-table code lengths.
import os, sys, time, pickle, numpy as np
from common import psnr
import cpp2
from cpp2 import Q, R
ESC=15; NS=2*ESC+2; HDR=3*11+16
TAU=int(os.environ.get('TAU','2')); RES0=float(os.environ.get('RES0','32')); RESC=float(os.environ.get('RESC','0')); TAUF=2.0**(-TAU/8.0)
TAB=os.environ.get('TABLES',os.path.join(os.path.dirname(os.path.abspath(__file__)),'../out/tables.pkl'))
# ----------------------------------------------------------------- formats / io
def plane_shapes(W,H,fmt):
    cw=W//2 if fmt in (422,420) else W; ch=H//2 if fmt==420 else H
    return [(H,W),(ch,cw),(ch,cw)]
def read(path,W,H,f,fmt=422):
    sh=plane_shapes(W,H,fmt); n=sum(a*b for a,b in sh)
    a=np.fromfile(path,dtype='<u2',count=n,offset=2*n*f).astype(np.int64)
    out=[];o=0
    for s in sh: out.append(a[o:o+s[0]*s[1]].reshape(s)); o+=s[0]*s[1]
    return out
def write(path,frames):
    with open(path,'wb') as f:
        for fr in frames:
            for p in fr: f.write(p.astype('<u2').tobytes())
# ----------------------------------------------------------------- motion
def down2(a): return (a[0::2,0::2]+a[1::2,0::2]+a[0::2,1::2]+a[1::2,1::2])/4.0
def shifted(a,dy,dx):
    H,W=a.shape; return a[np.clip(np.arange(H)+dy,0,H-1)][:,np.clip(np.arange(W)+dx,0,W-1)]
def hp_shift(a,vy2,vx2):
    """shift by half-pel units (bilinear average of the integer neighbours)"""
    y0,x0=vy2//2,vx2//2; fy,fx=vy2&1,vx2&1
    s=shifted(a,y0,x0).astype(np.int64)
    if fy or fx:
        s=s+shifted(a,y0+fy,x0+fx)
        if fy and fx: s=s+shifted(a,y0+fy,x0)+shifted(a,y0,x0+fx); return (s+2)>>2
        return (s+1)>>1
    return s
def motion(cur,ref,B=16,R_=8,hp=False):
    """backward vectors in HALF-pel units: cur(x) ~ ref(x+u)."""
    H,W=cur.shape; nby,nbx=H//B,W//B
    c2=down2(cur.astype(float)); r2=down2(ref.astype(float)); b2=B//2
    def bsad(a,b,bs):
        d=np.abs(a-b)[:nby*bs,:nbx*bs]; return d.reshape(nby,bs,nbx,bs).sum(axis=(1,3))
    best=np.full((nby,nbx),np.inf); V=np.zeros((nby,nbx,2),int)
    for dy in range(-R_,R_+1):
        for dx in range(-R_,R_+1):
            s=bsad(c2,shifted(r2,dy,dx),b2)+0.01*(abs(dy)+abs(dx))
            m=s<best; best[m]=s[m]; V[m]=(4*dy,4*dx)
    cf=cur.astype(float)
    steps=[2,1] if hp else [2]
    for st in steps:
        best=np.full((nby,nbx),np.inf); V2=V.copy()
        for ddy in (-st,0,st):
            for ddx in (-st,0,st):
                cand=V+np.array([ddy,ddx]); s=np.full((nby,nbx),np.inf)
                for (vy,vx) in set(map(tuple,cand.reshape(-1,2))):
                    m=(cand[...,0]==vy)&(cand[...,1]==vx)
                    s[m]=bsad(cf,hp_shift(ref,vy,vx).astype(float),B)[m]
                s=s+0.01*np.abs(cand).sum(-1)/2
                m=s<best; best[m]=s[m]; V2[m]=cand[m]
        V=V2
    return V
def obmc(ref,V,B,sy,sx):
    """bilinear OBMC over block centres; V half-pel luma units; sy/sx plane subsampling (1 or 2)."""
    H,W=ref.shape; By,Bx=B//sy,B//sx; nby,nbx=V.shape[:2]
    yc=(np.arange(H)-(By/2-0.5))/By; xc=(np.arange(W)-(Bx/2-0.5))/Bx
    y0=np.clip(np.floor(yc).astype(int),0,nby-1); x0=np.clip(np.floor(xc).astype(int),0,nbx-1)
    y1=np.clip(y0+1,0,nby-1); x1=np.clip(x0+1,0,nbx-1)
    fy=np.clip(np.round((yc-np.floor(yc))*16).astype(int),0,16); fx=np.clip(np.round((xc-np.floor(xc))*16).astype(int),0,16)
    fy=np.where(yc<0,0,np.where(np.floor(yc)>=nby-1,0,fy)); fx=np.where(xc<0,0,np.where(np.floor(xc)>=nbx-1,0,fx))
    acc=np.zeros((H,W),np.int64)
    uniq={}
    for (ya,wy) in ((y0,16-fy),(y1,fy)):
        for (xa,wx) in ((x0,16-fx),(x1,fx)):
            vy=V[ya][:,xa][...,0]; vx=V[ya][:,xa][...,1]
            # plane half-pel units: luma half-pel / subsampling
            vyp=np.floor_divide(vy,sy); vxp=np.floor_divide(vx,sx)
            g=np.zeros((H,W),np.int64)
            for key in set(zip(vyp.ravel().tolist(),vxp.ravel().tolist())):
                if key not in uniq: uniq[key]=hp_shift(ref,key[0],key[1])
                m=(vyp==key[0])&(vxp==key[1]); g[m]=uniq[key][m]
            acc+=np.outer(wy,wx)*g
    return (acc+128)>>8
# ----------------------------------------------------------------- static tables
class Tables:
    def __init__(s,path=TAB):
        s.ok=os.path.exists(path)
        if s.ok: s.L,s.VL=pickle.load(open(path,'rb'))
        s.cnt={}; s.vcnt=np.zeros((2,NS))
    @staticmethod
    def ctx(sym):
        a=np.minimum(np.abs(sym),2); L=np.zeros_like(a); L[...,:,1:]=a[...,:,:-1]
        U=np.zeros_like(a); U[...,1:,:]=a[...,:-1,:]; return L+3*U
    @staticmethod
    def idx(sym): return np.where(np.abs(sym)>ESC,NS-1,np.clip(sym,-ESC,ESC)+ESC)
    @staticmethod
    def escbits(sym):
        a=np.abs(sym)-ESC; e=a>0
        return np.where(e,2*np.floor(np.log2(np.maximum(a,1))).astype(int)+2,0)
    def key(s,pc,band,mode): return (pc,band if band=='LL' else (band[0],band[1]),mode)
    def bits(s,pc,band,mode,sym,ctx):
        k=s.key(pc,band,mode); L=s.L.get(k)
        if L is None: L=s.L[('Y','LL' if band=='LL' else ('HH',0),mode)]
        return L[ctx,s.idx(sym)]+s.escbits(sym)
    def count(s,pc,band,mode,sym,ctx):
        k=s.key(pc,band,mode); c=s.cnt.setdefault(k,np.zeros((9,NS)))
        np.add.at(c,(ctx.ravel(),s.idx(sym).ravel()),1)
    def vbits(s,V):
        d=V.copy(); d[:,1:]=V[:,1:]-V[:,:-1]
        return float(sum(s.VL[c][s.idx(d[...,c])].sum() for c in range(2)))
    def vcount(s,V):
        d=V.copy(); d[:,1:]=V[:,1:]-V[:,:-1]
        for c in range(2): np.add.at(s.vcnt[c],s.idx(d[...,c]).ravel(),1)
def build_tables(cnts,vcnt,path=TAB):
    L={}
    for k,c in cnts.items():
        p=(c+0.25)/(c+0.25).sum(1,keepdims=True)
        p=np.maximum(np.round(p*2048),1)/2048.0; L[k]=-np.log2(p)
    VL=[-np.log2(np.maximum(np.round((v+0.25)/(v+0.25).sum()*2048),1)/2048.0) for v in vcnt]
    pickle.dump((L,VL),open(path,'wb'))
# ----------------------------------------------------------------- the codec state machine
class Codec:
    def __init__(s,W,H,fmt=422,depth=10,rng=None,S=8,Lh=5,theta=0.25,hp=False,rho=1/16,tabs=None,
                 refresh=True,train=False):
        s.W,s.H,s.fmt=W,H,fmt; s.S=S; s.Lh=Lh; s.theta=theta; s.hp=hp; s.rho=rho
        s.shapes=plane_shapes(W,H,fmt); s.Lvs=[2,1 if fmt==420 else 2,1 if fmt==420 else 2]
        s.sy=[1,2 if fmt==420 else 1,2 if fmt==420 else 1]; s.sx=[1,1 if fmt==444 else 2,1 if fmt==444 else 2]
        mx=(1<<depth)-1
        s.rng=rng if rng is not None else [(0,mx)]*3
        s.nsl=H//S; s.tabs=tabs; s.train=train; s.refresh_on=refresh
        s.g=[s.gains(i) for i in range(3)]
        s.NS=float(os.environ.get('NSMOOTH','16')); s.kst=None; s.dec=[]; s.kprev=None; s.front=0; s.pot=0.0; s.credit=0.0; s.t=0
        s.lastsym=None; s.front_prev=None; s.selfread=0; s.sr_over=0; s.prevrow={}
    def gains(s,pi):
        shp=s.shapes[pi]; Lv=s.Lvs[pi]; z=np.zeros(shp,np.int64)
        T=cpp2.analysis(z,s.Lh,Lv); g={}
        for k in T:
            # synthesis energy of a unit (4096) impulse, no boxes
            Df={kk:np.ones((T[kk].shape[0],1)) for kk in T}
            TT={kk:np.zeros_like(v) for kk,v in T.items()}
            a=TT[k]; a[a.shape[0]//2,a.shape[1]//2]=4096
            y,_=cpp2.code_plane(TT,None,Df,None,-10**9,10**9,s.Lh,Lv,None,None)
            g[k]=(y.astype(float)**2).sum()/4096**2
        return g
    def excl_masks(s,pic):
        out=[]
        for pi in range(3):
            lo,hi=s.rng[pi]; rail=((pic[pi]<=lo)|(pic[pi]>=hi)).astype(np.int64)
            T=cpp2.analysis(np.zeros(pic[pi].shape,np.int64),s.Lh,s.Lvs[pi]); d={}
            for key,v in T.items():
                ry=pic[pi].shape[0]//v.shape[0]; rx=pic[pi].shape[1]//v.shape[1]
                m=rail[:v.shape[0]*ry,:v.shape[1]*rx].reshape(v.shape[0],ry,v.shape[1],rx).max(axis=(1,3))
                mm=m.copy(); mm[1:]|=m[:-1]; mm[:-1]|=m[1:]; m2=mm.copy(); m2[:,1:]|=mm[:,:-1]; m2[:,:-1]|=mm[:,1:]
                d[key]=m2.astype(bool)
            out.append(d)
        return out
    def D(s,pi,key,kap): return np.maximum(2.0,(2.0**(np.asarray(kap)/8.0))/np.sqrt(s.g[pi][key]))
    def band_slice_rows(s,pi,key,shape):
        """slice index of every coefficient row of a band (by the LAST plane row it covers, in luma rows)."""
        sp=cpp2.rowsp(key,s.Lvs[pi]); r1=(np.arange(shape[0])+1)*sp-1
        return (r1*s.sy[pi])//s.S, ((r1*s.sy[pi])%s.S+s.sy[pi]*sp)/s.S
    def field_rows(s,pi,key,shape,kap_list,kprev_first):
        sl,frac=s.band_slice_rows(pi,key,shape)
        k1=np.array(kap_list)[sl]; k0=np.array([kprev_first]+list(kap_list[:-1]))[sl]
        return np.round(k0+(k1-k0)*np.minimum(frac,1.0)).astype(int)
    # ------------------------------------------------------------------ lanes (exact open-loop cost)
    def lane_cost(s,k,cands,T,Tm,kprev,inter,hf_fn,kstate,want=False):
        """exact open-loop cost of slice k for every candidate knot (static tables, contexts incl. the row
        above from the previous slice); exact-representability flags; lane values U (for self-read)."""
        C=len(cands); tot=np.zeros(C); exact=np.ones(C,bool); tot_hf=np.zeros(C); U={}; last={}
        for pi in range(3):
            pc='Y' if pi==0 else 'C'
            for key,t in T[pi].items():
                sl,frac=s.band_slice_rows(pi,key,t.shape); rows=np.where(sl==k)[0]
                if len(rows)==0: continue
                kap=np.round(kprev+(np.array(cands)[:,None]-kprev)*np.minimum(frac[rows],1.0)[None,:]).astype(int)
                Df=s.D(pi,key,kap)[...,None]
                tt=t[rows][None].astype(np.int64)
                Dpk=None; keepm=None; vk=None; hk=None
                if inter: Dpk=np.minimum(s.D(pi,key,kstate[pi][key][rows])[None],Df)
                if key=='LL':
                    mid=(s.rng[pi][0]+s.rng[pi][1]+1)//2
                    rec=np.zeros((C,)+t[rows].shape,np.int64); u=np.zeros_like(rec); kp_=np.zeros(rec.shape,bool); exLL=np.zeros(rec.shape,bool)
                    hkk=np.zeros_like(rec); vkk=np.zeros_like(rec)
                    for c in range(t.shape[1]):
                        p=np.full((C,len(rows)),mid) if c==0 else rec[:,:,c-1]
                        x=tt[:,:,c]-p; Dc=Df[:,:,0]
                        q=Q(x,Dc); v=R(q,Dc); exLL[:,:,c]=(v==x)
                        if inter:
                            Dpc=Dpk[:,:,c] if Dpk.shape[2]>1 else Dpk[:,:,0]; tmx=Tm[pi]['LL'][rows][:,c][None]-p
                            vkc=R(Q(tmx,Dpc),Dpc); hkk[:,:,c]=Q(tmx,Dc); vkk[:,:,c]=vkc
                            exl=(v==x); exk=(vkc==x)
                            kc=exk|(~exl&((np.abs(x-vkc)<=(0.5+s.theta)*Dpc)|(np.abs(x-vkc)<=np.abs(x-v))))
                            v=np.where(kc,vkc,v); kp_[:,:,c]=kc; exLL[:,:,c]|=exk
                        rec[:,:,c]=p+v; u[:,:,c]=v
                    qq=Q(u,Df); tq=u
                    if inter: keepm=kp_; vk=vkk; hk=hkk
                    Ukey=rec
                else:
                    qq=Q(tt,Df); tq=tt
                    if inter:
                        tm=Tm[pi][key][rows][None]; vk=R(Q(tm,Dpk),Dpk); hk=Q(tm,Df)
                        exl=(R(qq,Df)==tt); exk=(vk==tt)
                        keepm=exk|(~exl&((np.abs(tt-vk)<=(0.5+s.theta)*Dpk)|(np.abs(tt-vk)<=np.abs(tt-R(qq,Df)))))
                    Ukey=np.where(keepm,vk,R(qq,Df)) if inter else R(qq,Df)
                if key=='LL': ex=exLL|s.excl[pi][key][rows][None]
                else:
                    ex=(R(Q(tq,Df),Df)==tq)|s.excl[pi][key][rows][None]
                    if inter: ex=ex|(keepm&(vk==tq))
                exact&=ex.reshape(C,-1).all(1)
                if want: U[(pi,key)]=Ukey
                def withprev(a,tag):
                    pr=s.prevrow.get((pi,key,tag))
                    if pr is None: pr=np.zeros(a.shape[2],np.int64)
                    return np.concatenate([np.broadcast_to(pr,(C,1,a.shape[2])),a],1)
                if inter:
                    symI=np.where(keepm,Q(vk,Dpk),qq)
                    sP=np.where(keepm,0,np.where(qq-hk>=0,qq-hk+1,qq-hk))
                    cP=Tables.ctx(withprev(sP,'P'))[:,1:]; cI=Tables.ctx(withprev(symI,'I'))[:,1:]
                    bP=s.tabs.bits(pc,key,'P',sP,cP); bI=s.tabs.bits(pc,key,'I',symI,cI)
                    bI=bI+1.0+3.0*(keepm&(Dpk<Df))
                    hf=hf_fn(pi,key,rows)[None]
                    tot+=np.where(hf,bI,bP).reshape(C,-1).sum(1); tot_hf+=bI.reshape(C,-1).sum(1)
                    last[(pi,key,'P')]=sP[:,-1]; last[(pi,key,'I')]=symI[:,-1]
                else:
                    symI=qq; cI=Tables.ctx(withprev(symI,'I'))[:,1:]
                    b=s.tabs.bits(pc,key,'I',symI,cI).reshape(C,-1).sum(1); tot+=b; tot_hf+=b
                    last[(pi,key,'I')]=symI[:,-1]
        return tot,tot_hf,exact,U,last
    # ------------------------------------------------------------------ one frame
    def encode(s,frame,B=0.0,kfixed=None):
        if kfixed is not None or not s.tabs.ok:
            s.excl=s.excl_masks(frame); return s._encode(frame,B,kfixed)
        snap=s.snapshot(); s.excl=s.excl_masks(frame)
        yA=s._encode(frame,B,None)
        s.restore(snap); s.excl=s.excl_masks(yA)
        return s._encode(frame,B,None)
    def snapshot(s):
        import copy
        return copy.deepcopy({k:getattr(s,k) for k in ('kst','dec','kprev','front','pot','credit','t','front_prev','selfread','sr_over','prevrow')})
    def restore(s,snap):
        for k,v in snap.items(): setattr(s,k,v)
    def _encode(s,frame,B=0.0,kfixed=None):
        t=s.t; inter=t>0 and len(s.dec)>0
        # motion from decoded history, clean-region clamp against the refresh front
        if inter:
            V=motion(s.dec[-1][0],s.dec[-2][0],hp=s.hp) if len(s.dec)>=2 else np.zeros((s.H//16,s.W//16,2),int)
            if s.refresh_on and s.front_prev is not None and s.front>0:
                yb=np.arange(V.shape[0])*16+15+8
                above=(np.arange(V.shape[0])*16+16)<=s.front
                lim=((s.front_prev-1-4)-yb)*2
                V[...,0]=np.where(above[:,None],np.minimum(V[...,0],lim[:,None]),V[...,0])
            mc=[obmc(s.dec[-1][pi],V,16,s.sy[pi],s.sx[pi]) for pi in range(3)]
            Tm=[cpp2.analysis(mc[pi],s.Lh,s.Lvs[pi]) for pi in range(3)]
        else: V=None; Tm=None; mc=None
        vb_sl=(s.tabs.vbits(V)/s.nsl) if (inter and s.tabs.ok) else 0.0
        T=[cpp2.analysis(frame[pi],s.Lh,s.Lvs[pi]) for pi in range(3)]
        if s.kst is None: s.kst=[{k:np.full(v.shape,60) for k,v in T[pi].items()} for pi in range(3)]
        kap=[]; kprev0=s.kprev[0] if s.kprev is not None else 56
        lane=[]; hfslice=[]
        # refresh region (rows) for this frame, extended block by block from the lanes' hint-free extra cost
        s.front_prev=s.front
        rfr=[s.front,s.front]           # [start,end) luma rows refreshed this frame
        def hf_rows_fn(k_hf):
            def f(pi,key,rows):
                sp=cpp2.rowsp(key,s.Lvs[pi]); r=(rows*sp)*s.sy[pi]
                m=(r>=rfr[0])&(r<rfr[1]) if s.refresh_on else np.zeros(len(rows),bool)
                return np.broadcast_to((m|k_hf)[:,None],(len(rows),T[pi][key].shape[1]))
            return f
        J=[-64,-48,-32,-24,-16,-12,-8,-6,-4,-3,-2,-1,0,1,2,3,4,6,8,12,16,24,32,48,64]
        kmax=110; s.prevrow={}; s.overflow=0; Tcur=[dict(d) for d in T]
        for k in range(s.nsl):
            kp=kprev0 if k==0 else kap[-1]
            s.credit+=B*(1-s.rho)-vb_sl-HDR; s.pot+=B*s.rho; budget=s.credit
            target=B*(1-s.rho)-vb_sl-HDR+max(budget-(B*(1-s.rho)-vb_sl-HDR),0)/s.NS
            if kfixed is not None:
                cands=[kfixed]
            else:
                cands=sorted(set(int(np.clip(kp+j,8,kmax)) for j in J)|{kmax})
            hff=hf_rows_fn(False)
            if kfixed is not None:
                kap.append(kfixed); hfslice.append(not inter); lane.append([kfixed,0,0,0])
                if inter and s.refresh_on and k==0: rfr[1]=min(rfr[0]+s.S,s.H)
                continue
            cost,cost_hf,exact,U,last=s.lane_cost(k,cands,Tcur,Tm,kp,inter,hff,s.kst,want=True)
            costx=np.minimum(cost,cost_hf) if inter else cost
            nex=sum(int(v[np.where(s.band_slice_rows(pi,key,v.shape)[0]==k)[0]].sum()) for pi in range(3) for key,v in s.excl[pi].items())
            hard=budget-RES0-RESC*nex; target=min(target,hard)
            fit=costx<=hard; ca=np.array(cands)
            if kfixed is not None: i=0
            else:
                fitT=costx<=target; ikp=int(np.where(ca==kp)[0][0])
                if exact.all(): i=ikp                      # no informative coefficient: keep the knot
                elif exact.any(): i=int(np.where(exact)[0][-1])  # plan recovery: coarsest exact candidate
                else:
                    if fitT.any(): i=int(np.where(fitT)[0][0])
                    elif fit.any(): i=int(np.where(fit)[0][0])
                    else: i=len(cands)-1; s.overflow+=1
                    # gen-1 self-read: apply the recovery rule to the chosen reconstruction
                    Tsr=[dict(d) for d in Tcur]
                    for (pi,key),v in U.items():
                        sl,_=s.band_slice_rows(pi,key,T[pi][key].shape); rows=np.where(sl==k)[0]
                        a_=Tsr[pi][key].copy(); a_[rows]=v[i]; Tsr[pi][key]=a_
                    c2,c2h,ex2,U2,last2=s.lane_cost(k,cands,Tsr,Tm,kp,inter,hff,s.kst,want=True)
                    i2=ikp if ex2.all() else int(np.where(ex2)[0][-1])
                    c2x=np.minimum(c2,c2h) if inter else c2
                    Tcur=Tsr; cost,cost_hf,costx,last=c2,c2h,c2x,last2
                    if i2!=i:
                        s.selfread+=1
                        if c2x[i2]>hard: s.sr_over+=1
                    i=i2
            hfk=bool(inter and cost_hf[i]<cost[i]) or not inter
            kap.append(cands[i]); hfslice.append(hfk)
            s.credit-=costx[i]; lane.append([cands[i],costx[i],budget,cands[i]-kp])
            if inter and s.refresh_on:
                r0,r1=k*s.S,(k+1)*s.S
                while rfr[1]>=r0 and rfr[1]<r1:
                    save=list(rfr); rfr[1]=min(rfr[1]+4,r1)
                    cw,cwh,_,_,_=s.lane_cost(k,[cands[i]],Tcur,Tm,kp,True,hf_rows_fn(False),s.kst)
                    extra=(cw[0]-lane[-1][1]) if not hfk else 0.0
                    if extra<=s.pot: s.pot-=extra; lane[-1][1]+=extra
                    else: rfr[:]=save; break
            for kk,v in last.items(): s.prevrow[kk]=v[i]
        # ---- actual coding with the chosen field
        out_planes=[];bits_sl=np.zeros(s.nsl);info=[]
        s.hf_mask={}; SYMS=[];HFS=[];KEPTI=[];KSTB=[];DFS=[]
        for pi in range(3):
            Lv=s.Lvs[pi]; Df={};Dp={};it={};hf={}
            for key,tv in T[pi].items():
                kr=s.field_rows(pi,key,tv.shape,kap,kprev0); Df[key]=s.D(pi,key,kr)[:,None]
                Dp[key]=s.D(pi,key,s.kst[pi][key])
                sl,_=s.band_slice_rows(pi,key,tv.shape)
                sp=cpp2.rowsp(key,Lv); r=(np.arange(tv.shape[0])*sp)*s.sy[pi]
                hr=(np.array(hfslice)[sl]) | ((r>=rfr[0])&(r<rfr[1]) if s.refresh_on else False)
                hf[key]=np.broadcast_to(hr[:,None],tv.shape).copy() if inter else np.ones(tv.shape,bool)
                it[key]=np.ones(tv.shape,bool) if inter else None
                if not inter: it[key]=None
            lo,hi=s.rng[pi]
            KSTB.append({k_:v.copy() for k_,v in s.kst[pi].items()}); DFS.append(Df)
            y,o=cpp2.code_plane(Tcur[pi],Tm[pi] if inter else None,Df,Dp if inter else None,lo,hi,s.Lh,Lv,
                                it if inter else None,hf,s.theta)
            out_planes.append(y)
            pc='Y' if pi==0 else 'C'
            for key,(kept,Dn,sP,sI,used,w,hfm) in o.items():
                mode_I=hfm
                cP=Tables.ctx(sP); cI=Tables.ctx(sI)
                if s.train:
                    if inter: s.tabs.count(pc,key,'P',sP[~mode_I],cP[~mode_I])
                    s.tabs.count(pc,key,'I',sI[mode_I],cI[mode_I])
                if s.tabs.ok:
                    b=np.where(mode_I,s.tabs.bits(pc,key,'I',sI,cI),s.tabs.bits(pc,key,'P',sP,cP)) if inter else s.tabs.bits(pc,key,'I',sI,cI)
                    if inter: b=b+np.where(mode_I,1.0+3.0*(kept&(Dn<np.broadcast_to(Df[key],Dn.shape))),0)
                    sl,_=s.band_slice_rows(pi,key,b.shape)
                    np.add.at(bits_sl,sl,b.sum(1))
                # state: step memory as knot index
                kr=s.field_rows(pi,key,T[pi][key].shape,kap,kprev0)
                s.kst[pi][key]=np.where(kept,np.minimum(s.kst[pi][key],kr[:,None]),kr[:,None]) if inter else np.broadcast_to(kr[:,None],kept.shape).copy()
            s.hf_mask[pi]={key:v[6] for key,v in o.items()}
            SYMS.append({key:v[4] for key,v in o.items()}); HFS.append({key:v[6] for key,v in o.items()})
            KEPTI.append({key:(v[0]&v[6]) for key,v in o.items()})
            if pi==0: s.last_o=[o]
            else: s.last_o.append(o)
        bits_sl+=HDR               # 3 tANS flushes + slice header (2 knots)
        bits_sl+=vb_sl
        vbits=s.tabs.vbits(V) if (inter and s.tabs.ok) else 0.0
        if s.train and inter: s.tabs.vcount(V)
        s.dec.append(out_planes); s.dec=s.dec[-2:]; s.kprev=kap; s.t+=1
        s.front=rfr[1] if rfr[1]<s.H else 0
        dev=[bits_sl[k]-lane[k][1]-HDR-vb_sl for k in range(s.nsl)] if s.tabs.ok else []
        s.frame_info=dict(sym=SYMS,hf=HFS,keptI=KEPTI,kstb=KSTB,Df=DFS,inter=inter,kprev0=kprev0,kap=kap,lane=lane,bits=bits_sl,vbits=vbits,refresh=tuple(rfr),V=V,hfslice=hfslice,dev=dev)
        return out_planes

class Decoder:
    """decoder simulation: own reference, own step-memory state; lost rows decode as 'keep' (concealment)."""
    def __init__(s,cod):
        s.c=cod; s.dec=[]; s.kst=None
    def decode(s,fi,lost=None):
        c=s.c; inter=fi['inter']
        if inter:
            V=fi['V']; mc=[obmc(s.dec[-1][pi],V,16,c.sy[pi],c.sx[pi]) for pi in range(3)]
            Tm=[cpp2.analysis(mc[pi],c.Lh,c.Lvs[pi]) for pi in range(3)]
        out=[]
        for pi in range(3):
            Lv=c.Lvs[pi]; SYM={}; hf={}; ds={}; Dp={}; it={}
            if s.kst is None or not inter: s.kst_pi=None
            for key,sym in fi['sym'][pi].items():
                sy=sym.copy(); h=fi['hf'][pi][key].copy(); kI=fi['keptI'][pi][key].copy()
                if lost is not None:
                    sp=cpp2.rowsp(key,Lv); r=(np.arange(sym.shape[0])*sp)*c.sy[pi]
                    m=((r>=lost[0])&(r<lost[1]))[:,None]
                    if inter:
                        sy=np.where(m,0,sy); h=np.where(m,False,h); kI=np.where(m,False,kI)
                SYM[key]=sy; hf[key]=h if inter else np.ones(sym.shape,bool); ds[key]=kI
                if inter:
                    kd=s.kst[pi][key].copy()
                    kd=np.where(kI,fi['kstb'][pi][key],kd)          # refresh map restores the step of kept values
                    Dp[key]=c.D(pi,key,kd); it[key]=np.ones(sym.shape,bool)
            lo,hi=c.rng[pi]
            y,o=cpp2.code_plane(None,Tm[pi] if inter else None,fi['Df'][pi],Dp if inter else None,lo,hi,c.Lh,Lv,
                                it if inter else None,hf,c.theta,enc=False,SYM=SYM,decstate=ds)
            out.append(y)
            if s.kst is None: s.kst=[None,None,None]
            newk={}
            for key,(kept,Dn,sP,sI,used,w,hfm) in o.items():
                kr=c.field_rows(pi,key,SYM[key].shape,fi['kap'],fi['kprev0'])
                if inter:
                    kd=np.where(ds[key],fi['kstb'][pi][key],s.kst[pi][key])
                    newk[key]=np.where(kept,np.minimum(kd,kr[:,None]),kr[:,None])
                else: newk[key]=np.broadcast_to(kr[:,None],kept.shape).copy()
            s.kst[pi]=newk
        s.dec.append(out); s.dec=s.dec[-2:]
        return out
