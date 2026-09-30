# sequence tests: still input, mixed still/moving, generation chain, slice loss, mid-stream join.
import sys, os, time, json, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import omc16, yuv
ROOT = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/'
TAB = os.environ.get('TAB', ROOT + 'out/tables/tables_p1.pkl')
def mk(cell, bpp, tabs=None):
    path, W, H = yuv.CELLS[cell]; S = 4 if H == 720 else 8
    return omc16.Codec(W, H, S=S, bpp=bpp, tabs=tabs or omc16.Tables(TAB)), path, W, H
def psnr(a, b): return [10 * np.log10(1023 ** 2 / max(1e-9, np.mean((a[p] - b[p]) ** 2.0))) for p in range(3)]
def changed(a, b): return [int((a[p] != b[p]).sum()) for p in range(3)]
def toward(src, prev, cur):
    """samples that changed: count moving toward / away from the source."""
    tw = aw = 0
    for p in range(3):
        m = cur[p] != prev[p]; tw += int((np.abs(cur[p] - src[p]) < np.abs(prev[p] - src[p]))[m].sum()); aw += int((np.abs(cur[p] - src[p]) > np.abs(prev[p] - src[p]))[m].sum())
    return tw, aw

def test_still(cell='dng720', bpp=0.5, nf=10):
    cod, path, W, H = mk(cell, bpp); f0 = yuv.read_frame(path, W, H, 0); out = []
    prev = None
    for t in range(nf):
        rec = cod.encode(f0); ch = changed(rec, prev) if prev is not None else None
        out.append(dict(t=t, bits=int(cod.stats['frame_bits']), changed=ch, psnr=psnr(rec, f0), overflow=cod.stats.get('overflow', 0)))
        prev = rec
    return out

def test_mixed(cell='dng720', bpp=0.5, nf=10):
    """left half still (frame 0), right half moving (frames t); rate changes through the moving half."""
    cod, path, W, H = mk(cell, bpp); f0 = yuv.read_frame(path, W, H, 0); out = []; prev = None
    for t in range(nf):
        ft = yuv.read_frame(path, W, H, t); src = [np.concatenate([f0[p][:, :f0[p].shape[1] // 2], ft[p][:, ft[p].shape[1] // 2:]], 1) for p in range(3)]
        rec = cod.encode(src)
        if prev is not None:
            half = [(rec[p][:, :rec[p].shape[1] // 2], prev[p][:, :prev[p].shape[1] // 2], src[p][:, :src[p].shape[1] // 2]) for p in range(3)]
            ch = [int((h[0] != h[1]).sum()) for h in half]; tot = [h[0].size for h in half]
            tw = aw = 0
            for h in half:
                m = h[0] != h[1]; tw += int((np.abs(h[0] - h[2]) < np.abs(h[1] - h[2]))[m].sum()); aw += int((np.abs(h[0] - h[2]) > np.abs(h[1] - h[2]))[m].sum())
        else: ch = None; tot = None; tw = aw = 0
        out.append(dict(t=t, bits=int(cod.stats['frame_bits']), still_changed=ch, still_total=tot, toward=tw, away=aw, Pe_med=float(np.median(cod.last['Pe']))))
        prev = rec
    return out

def test_gen(cell='dng720', bpp=0.5, nf=6, gens=3):
    """generation chain: gen g encodes gen g-1's decode; pictures and bits compared."""
    path, W, H = yuv.CELLS[cell]; S = 4 if H == 720 else 8; tabs = omc16.Tables(TAB)
    cods = [omc16.Codec(W, H, S=S, bpp=bpp, tabs=tabs) for g in range(gens)]; out = []
    for t in range(nf):
        src = yuv.read_frame(path, W, H, t); pics = []; bits = []
        x = src
        for g in range(gens):
            x = cods[g].encode(x); pics.append(x); bits.append(int(cods[g].stats['frame_bits']))
        out.append(dict(t=t, bits=bits, diff_vs_g1=[changed(pics[g], pics[0]) for g in range(1, gens)]))
    return out

def test_loss(cell='dng720', bpp=0.5, nf=20, lose=(4, (20, 21))):
    """decoder loses slices at frame lose[0]; damage and recovery vs the encoder's reconstruction."""
    cod, path, W, H = mk(cell, bpp); dref = None; out = []
    for t in range(nf):
        src = yuv.read_frame(path, W, H, min(t, 11)); rec = cod.encode(src)
        lost = lose[1] if t == lose[0] else ()
        dec = cod.decode(cod.last, dref, lost=lost)
        d = [(dec[p] != rec[p]) for p in range(3)]
        rows = np.nonzero(d[0].any(1))[0]
        out.append(dict(t=t, damaged=[int(x.sum()) for x in d], maxabs=[int(np.abs(dec[p] - rec[p]).max()) for p in range(3)],
                        rows=(int(rows.min()), int(rows.max())) if rows.size else None))
        dref = dec
    return out

def test_join(cell='dng720', bpp=0.5, nf=24, join=5):
    """a decoder joins at frame `join` with no reference (grey); frames until exact."""
    cod, path, W, H = mk(cell, bpp); dref = None; out = []
    for t in range(nf):
        src = yuv.read_frame(path, W, H, t % 12); rec = cod.encode(src)
        if t < join: out.append(dict(t=t, joined=False)); continue
        if t == join: dref = [np.full(rec[p].shape, 512, np.int64) for p in range(3)]
        dec = cod.decode(cod.last, dref); d = [(dec[p] != rec[p]) for p in range(3)]
        out.append(dict(t=t, differing=[int(x.sum()) for x in d], phi=int(cod.last['phi'])))
        dref = dec
    return out

if __name__ == '__main__':
    which = sys.argv[1]; cell = sys.argv[2] if len(sys.argv) > 2 else 'dng720'; bpp = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
    t0 = time.time(); res = globals()['test_' + which](cell, bpp)
    os.makedirs(ROOT + 'out/seq', exist_ok=True)
    json.dump(res, open(ROOT + 'out/seq/%s_%s_%.1f.json' % (which, cell, bpp), 'w'), indent=1)
    for r in res: print(r)
    print('%.0fs' % (time.time() - t0))
