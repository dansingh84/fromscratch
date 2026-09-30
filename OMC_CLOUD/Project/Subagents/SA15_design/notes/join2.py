# mid-stream join under exact CBR: a fresh encoder starts at frame J on the upstream decodes (same rate)
import sys, numpy as np, seq2
dec1,W,H,bpp,N,J,S=sys.argv[1],int(sys.argv[2]),int(sys.argv[3]),float(sys.argv[4]),int(sys.argv[5]),int(sys.argv[6]),int(sys.argv[7])
tabs=seq2.Tables(); cod=seq2.Codec(W,H,S=S,tabs=tabs)
for t in range(J,N):
    up=seq2.read(dec1,W,H,t); y=cod.encode(up,bpp*W*S); fi=cod.frame_info
    nd=[int((a!=b).sum()) for a,b in zip(y,up)]
    rows=np.where((y[0]!=up[0]).any(1))[0]
    print(f'join J={J} t={t} differing samples vs upstream Y/Cb/Cr={nd} slices differing={len(set((rows//S).tolist()))}/{H//S} bpp={(fi["bits"].sum()+fi["vbits"])/(W*H):.4f} overflow={cod.overflow} kap med={int(np.median(fi["kap"]))}',flush=True)
