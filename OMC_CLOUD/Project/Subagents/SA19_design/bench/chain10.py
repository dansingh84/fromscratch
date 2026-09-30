# SA19 generation chains. Each generation is a FULL encoder run on the previous generation's decoded pictures (read=False:
# the encoder does not know its input is decoded), followed by its own decode; rates per generation from RATES.
# Reports per generation: differing samples vs previous generation (pictures), bits identical, oob, prefix overs,
# and the first generation from which pictures+bits stay identical (fixed point).
import numpy as np, sys, yuv, ent, tpp
SA7 = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA7_legality_v2/arms/'
C = {'cut24': (SA7 + 'cut24.yuv', 256, 64, 0, 1023), 'ext10': (SA7 + 'ext_10_422_l0.yuv', 512, 128, 0, 1023),
     'gfx': (yuv.ARMS + 'cf_gfx_448x256_422_10.yuv', 448, 256, 4, 1019), 'dng720': (yuv.CELLS['dng720'][0], 1280, 720, 4, 1019),
     'spot': (yuv.CELLS['spot'][0], 1920, 1080, 4, 1019), 'floor': (yuv.CELLS['floor'][0], 1920, 1080, 4, 1019)}
AUTO = int(sys.argv[5]) if len(sys.argv) > 5 else 0
tabs = ent.Tables(sys.argv[1]); cell = sys.argv[2]; N = int(sys.argv[3]); RATES = [float(r) for r in sys.argv[4].split(',')]
path, W, H, lo, hi = C[cell]; nf = yuv.nframes(path, W, H)
frames = [yuv.read_frame(path, W, H, f % nf) for f in range(N)]
prev_pics, prev_bits = None, None; fixed = None
for gi, bpp in enumerate(RATES):
    g = tpp.TPP(W, H, bpp, tabs, lo=lo, hi=hi, S=4 if H <= 720 else 8, tilt=0.25, rho=0.35, cheap=1, auto=AUTO)
    pics = []; bits = []; oob = 0; over = 0
    for f in range(N):
        o, b, i = g.encode(frames[f] if prev_pics is None else prev_pics[f])
        pics.append(o); bits.append(np.asarray(b, float)); over += i['over']
        oob += sum(int(((o[p] < lo) | (o[p] > hi)).sum()) for p in range(3))
    if prev_pics is not None:
        dp = [sum(int((a[p] != b[p]).sum()) for p in range(3)) for a, b in zip(pics, prev_pics)]
        db = [not np.allclose(a, b) for a, b in zip(bits, prev_bits)]
        same = (sum(dp) == 0 and not any(db) and RATES[gi] == RATES[gi - 1])
        if same and fixed is None: fixed = gi          # generation gi reproduces generation gi-1 (1-based gi+1 vs gi)
        if not same: fixed = None
        print('%s gen %d @%.2f: differing samples per frame %s | frames with different bits %d | oob %d overs %d' % (cell, gi + 1, bpp, dp, sum(db), oob, over), flush=True)
    else:
        print('%s gen 1 @%.2f: oob %d overs %d' % (cell, bpp, oob, over), flush=True)
    prev_pics, prev_bits = pics, bits
print('%s rates %s: fixed point from generation %s' % (cell, RATES, (fixed + 1) if fixed is not None else 'NONE'), flush=True)
