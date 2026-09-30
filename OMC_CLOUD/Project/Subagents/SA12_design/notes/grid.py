"""Block-grid test (coordinator request): decode dng1080 f5 and spotrobotL f5 at ~0.5 bpp with HF-B5 and with today's
structure model (SA11 struct_s TODAY: 5/3 + 9/7-like, 2V x 5H), per plane:
 - boundary-vs-interior error-step statistic: mean |e[x]-e[x-1]| (e = decode - source) at x = 0 mod P vs elsewhere,
   for P = 2,4,8,16,32 horizontally and rows mod 2,4,8,16 vertically (a block grid shows as ratio > 1 at its pitch)
 - level map: block means of e over 32x8 LL-support blocks: std, and the mean |difference| between neighbouring block
   means across block boundaries vs the same measured on blocks shifted by half a block (grid-aligned vs not)
 - writes renders (full frame, unmarked + _grid) of the level map and |e| for the eye."""
import sys, os, json, math, numpy as np
sys.argv += [] ; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA11_plan/notes')
import hf, struct_s as S
VK = os.environ.get('HF_VK', 's6a')
CL1 = float(os.environ.get('HF_CL1', '1')); CL2 = float(os.environ.get('HF_CL2', '1'))
from PIL import Image
def base_decode(planes, sh, Qf, k=-1):
    out = []
    for P in planes:
        H, W = P.shape; Hp = -(-H // sh) * sh
        X = np.vstack([P, np.repeat(P[-1:], Hp - H, 0)]).astype(float).reshape(Hp // sh, sh, W)
        Y = S.fwd(X, S.TODAY, 7); w = S.weights(sh, W, S.TODAY, 7); w[-1] *= 4.0 ** (-k); bl, ll = S.bands(sh, W, 7)
        Z = np.zeros_like(Y); bits = 0
        for i, (r0, r1, c0, c1) in enumerate(bl + [ll]):
            D = 2.0 ** round(Qf - 0.5 * math.log2(w[i])); q = S.quant(Y[:, r0:r1, c0:c1], D); bits += S.ent(q.ravel()); Z[:, r0:r1, c0:c1] = q * D
        out.append((np.clip(np.rint(S.inv(Z, S.TODAY, 7).reshape(Hp, W)[:H]), 0, 1023), bits))
    return [o[0] for o in out], sum(o[1] for o in out) / planes[0].size
def hf_decode(planes, sh, Qf, k=-1):
    os.environ['HF_FAST'] = '1'; recs = []; bits = 0
    for P in planes:
        H, W = P.shape; Hp = -(-H // sh) * sh
        X = np.vstack([P, np.repeat(P[-1:], Hp - H, 0)]).astype(np.int64).reshape(Hp // sh, sh, W)
        w = hf.weights(sh, W, 5, 3, 's10', VK); ks = hf.keys(5, 3); w[ks[-1]] *= 4.0 ** (-k)
        steps = {kk: max(1, int(round(2.0 ** round(Qf - 0.5 * math.log2(w[kk]))))) for kk in ks}
        if P is not planes[0]:                       # chroma: level-1 / level-2 step scale (R2 cause test)
            for kk in ks:
                sc = CL1 if kk[0] == 1 else (CL2 if kk[0] == 2 else 1.0)
                steps[kk] = max(1, int(round(steps[kk] * sc)))
        LO = np.zeros(X.shape, np.int64); HI = np.full(X.shape, 1023, np.int64)
        C = hf.Coder('enc', steps); R = hf.run_coder(C, X, LO, HI, 5, 3, 's10', VK, True)
        bits += sum(hf.ent(C.Q[kk]) for kk in ks); recs.append(R.reshape(Hp, W)[:H].astype(float))
    return recs, bits / planes[0].size
def find_qf(fn, planes, sh, target):
    best = None
    for Qf in [x / 4 for x in range(8, 44)]:
        r, b = fn(planes, sh, Qf)
        if best is None or abs(math.log2(b / target)) < abs(math.log2(best[2] / target)): best = (Qf, r, b)
        if b < target * 0.8: break
    return best
def stats(e):
    out = {}
    dx = np.abs(np.diff(e, axis=1)); dy = np.abs(np.diff(e, axis=0))
    for P in (2, 4, 8, 16, 32):
        xs = np.arange(1, e.shape[1]); m = (xs % P == 0)
        out['h%d' % P] = float(dx[:, m].mean() / dx[:, ~m].mean())
    for P in (2, 4, 8, 16):
        ys = np.arange(1, e.shape[0]); m = (ys % P == 0)
        out['v%d' % P] = float(dy[m].mean() / dy[~m].mean())
    return out
def levelmap(e, bw, bh, ox=0, oy=0):
    H, W = e.shape; e = e[oy:, ox:]; H2, W2 = (e.shape[0] // bh) * bh, (e.shape[1] // bw) * bw
    B = e[:H2, :W2].reshape(H2 // bh, bh, W2 // bw, bw).mean((1, 3))
    return B, float(np.abs(np.diff(B, axis=1)).mean()), float(np.abs(np.diff(B, axis=0)).mean())
def render(e, path, bw, bh, scale):
    a = np.clip(128 + e * scale, 0, 255).astype(np.uint8)
    Image.fromarray(a).save(path)
    g = np.stack([a] * 3, -1); g[:, ::bw] = (255, 0, 0); g[::bh, :] = (255, 0, 0); Image.fromarray(g).save(path.replace('.png', '_grid.png'))
if __name__ == '__main__':
    cells = [('dng1080', '/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/dng_1920x1080_422_10.yuv', 5),
             ('spot', '/home/user/fromscratch/OMC_CLOUD/Project/.work/arms/long/spotrobotL_1920x1080_422_10.yuv', 5)]
    res = {}
    for tag, path, fr in cells:
        planes = [p.astype(float) for p in hf.load(path, 1920, 1080, fr, '422')]
        for name, fn in (('base', base_decode), ('hfB5', hf_decode)):
            Qf, recs, b = find_qf(fn, [p.astype(np.int64) if name == 'hfB5' else p for p in planes], 16, 0.5)
            for pi, (R, P) in enumerate(zip(recs, planes)):
                e = R - P; st = stats(e)
                bw = 32 if pi == 0 else 16
                B, jh, jv = levelmap(e, bw, 8); _, jh2, jv2 = levelmap(e, bw, 8, bw // 2, 4)
                st.update(lm_std=float(B.std()), lm_jump_grid_h=jh, lm_jump_grid_v=jv, lm_jump_off_h=jh2, lm_jump_off_v=jv2)
                res['%s_%s_%s' % (tag, name, 'YUV'[pi])] = dict(bpp=b, Qf=Qf, **st)
                mag = np.kron(B, np.ones((8, bw))); render(mag, 'lm_%s_%s_%s.png' % (tag, name, 'YUV'[pi]), bw, 8, 16)
                render(np.abs(e), 'ad_%s_%s_%s.png' % (tag, name, 'YUV'[pi]), bw, 8, 8)
                print(tag, name, 'YUV'[pi], 'bpp %.3f' % b, ' '.join('%s=%.3f' % (k, v) for k, v in st.items()), flush=True)
    json.dump(res, open('grid.json', 'w'), indent=1)
