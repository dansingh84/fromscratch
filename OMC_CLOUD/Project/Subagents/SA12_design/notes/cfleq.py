"""R2 at EQUAL bits: chroma level-1 step x c1, chroma levels>=2 (and LL) step x c2, luma untouched; intra f8.
Reports per-plane bits, NEG, PSNR Y/Cb/Cr, flatplane, texstat.  usage: cfleq.py tag path Qf 'c1:c2,...'"""
import sys, os, math, subprocess, re, numpy as np
os.environ['HF_FAST'] = '1'; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hf
T = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/shared_tools'; SCR = os.environ['SCR']
tag, path, Qf = sys.argv[1], sys.argv[2], float(sys.argv[3]); variants = [tuple(map(float, v.split(':'))) for v in sys.argv[4].split(',')]  # c1:c2[:th1]
src = hf.load(path, 1920, 1080, 8, '422'); L, nv, kH, kV = 5, 3, 's10', 's10a'
sp = os.path.join(SCR, tag + '_s.yuv'); np.concatenate([p.astype('<u2').ravel() for p in src]).tofile(sp)
for vv in variants:
    c1, c2 = vv[0], vv[1]; th1 = int(vv[2]) if len(vv) > 2 else 7
    recs, bits = [], []
    for pi, P in enumerate(src):
        H, W = P.shape; Hp = -(-H // 16) * 16
        X = np.vstack([P, np.repeat(P[-1:], Hp - H, 0)]).astype(np.int64).reshape(-1, 16, W)
        w = hf.weights(16, W, L, nv, kH, kV); ks = hf.keys(L, nv); w[ks[-1]] *= 4.0
        st = {k: max(1, int(round(2.0 ** round(Qf - 0.5 * math.log2(w[k]))))) for k in ks}
        if pi > 0:
            for k in ks: st[k] = max(1, int(round(st[k] * (c1 if k[0] == 1 else c2))))
        hf.THMAP.clear()
        if pi > 0 and th1 != 7: hf.THMAP[1] = th1
        C = hf.Coder('enc', st); R = hf.run_coder(C, X, np.zeros(X.shape, np.int64), np.full(X.shape, 1023, np.int64), L, nv, kH, kV, True)
        bits.append(sum(hf.ent(C.Q[k]) for k in ks) / (1920 * 1080)); recs.append(R.reshape(Hp, W)[:H])
    dp = os.path.join(SCR, tag + '_d.yuv'); np.concatenate([p.astype('<u2').ravel() for p in recs]).tofile(dp)
    run = lambda c: subprocess.run(c, capture_output=True, text=True, cwd=T).stdout
    neg = run(['bash', T + '/negscore.sh', sp, dp, '1920', '1080', '422', '10', '1']).strip().splitlines()[-1]
    ps = '/'.join('%.2f' % (10 * math.log10(1023 ** 2 / float(((r - s) ** 2).mean()))) for r, s in zip(recs, src))
    fp = '/'.join(re.findall(r'(\d+\.\d+)%', run(['python3', T + '/flatplane.py', sp, dp, '1920', '1080', '0', '--fmt', '422'])))
    cor = '/'.join(re.findall(r'COR=(-?\d+\.\d+)', run(['python3', T + '/texstat.py', sp, dp, '1920', '1080', '0', '--fmt', '422'])))
    print('%s Qf %.2f c1 %.2f c2 %.2f th1 %d | bpp Y/Cb/Cr %.3f/%.3f/%.3f total %.3f | NEG %s | PSNR %s | flat%% %s | COR %s' % (tag, Qf, c1, c2, th1, *bits, sum(bits), neg, ps, fp, cor), flush=True)
    os.remove(dp)
os.remove(sp)
