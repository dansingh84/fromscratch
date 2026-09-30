# run one cell at one rate (12 frames), write the decode, measure vs today's real decode:
# per-frame VMAF-NEG (owner's negscore.sh, single-frame extracts), per-plane PSNR, smudgegroups/artifactmap/flatplane.
import sys, os, subprocess, time, json, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import omc16, yuv
ROOT = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/'
TOOLS = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/shared_tools/'
SCR = os.environ.get('SCRATCH', '/tmp/claude-1000/-home-dan-Documents-Apps-Codec/349df860-b2b7-4717-bcf8-5bdc1c07368a/scratchpad')
os.makedirs(SCR, exist_ok=True)

def extract(path, W, H, f, out):
    n = W * H * 2 * 2   # 4:2:2 10-bit bytes per frame
    with open(path, 'rb') as fh: fh.seek(n * f); d = fh.read(n)
    open(out, 'wb').write(d)

def neg_frame(src, dec, W, H, f, tag):
    a = os.path.join(SCR, 'r_%s.yuv' % tag); b = os.path.join(SCR, 'd_%s.yuv' % tag)
    extract(src, W, H, f, a); extract(dec, W, H, f, b)
    r = subprocess.run(['bash', TOOLS + 'negscore.sh', a, b, str(W), str(H), '422', '10', '1'], capture_output=True, text=True)
    os.remove(a); os.remove(b)
    if r.returncode != 0: raise SystemExit('negscore failed: ' + r.stderr)
    return float(r.stdout.strip().split()[-1])

def psnr_frame(src, dec, W, H, f):
    s = yuv.read_frame(src, W, H, f); d = yuv.read_frame(dec, W, H, f)
    return [10 * np.log10(1023 ** 2 / max(1e-9, np.mean((s[p] - d[p]) ** 2.0))) for p in range(3)]

def run_codec(cell, bpp, nf, tabs_path, out_path, log):
    path, W, H = yuv.CELLS[cell]; S = 4 if H == 720 else 8
    tabs = omc16.Tables(tabs_path); cod = omc16.Codec(W, H, S=S, bpp=bpp, tabs=tabs)
    frames = []; t0 = time.time()
    with open(log, 'w') as lg:
        for t in range(nf):
            src = yuv.read_frame(path, W, H, t); rec = cod.encode(src); frames.append(rec)
            Pe = cod.last['Pe']; hist = dict(floor=int((Pe == omc16.PMAX).sum()), ge270=int((Pe >= 270).sum()), ge240=int((Pe >= 240).sum()), n=int(Pe.size), intra=bool(cod.last['intra']))
            lg.write('f%d bits %d/%d est %d Pe[min,med,max]=%d/%d/%d viaread %d planhist %s stats %s %.0fs\n' % (
                t, cod.stats['frame_bits'], cod.F, cod.stats['est_bits'], Pe.min(), np.median(Pe), Pe.max(),
                cod.last['viaread'], hist, {k: v for k, v in cod.stats.items() if k not in ('frame_bits', 'est_bits')}, time.time() - t0)); lg.flush()
    yuv.write_frames(out_path, frames)
    return cod

def tools(src, dec, W, H, f, outp, tag):
    res = {}
    r = subprocess.run(['python3', TOOLS + 'smudgegroups.py', src, dec, str(W), str(H), str(f), outp + '_sm'], capture_output=True, text=True, cwd=SCR)
    res['smudge'] = r.stdout.strip().splitlines()[-3:] if r.returncode == 0 else 'FAILED ' + r.stderr[-300:]
    for pl in ('Y', 'Cb', 'Cr'):
        od = outp + '_am_' + pl; os.makedirs(od, exist_ok=True)
        r = subprocess.run(['python3', TOOLS + 'artifactmap.py', src, dec, str(W), str(H), str(f), od, '--plane', pl], capture_output=True, text=True, cwd=SCR)
        reg = [x for x in os.listdir(od) if x.endswith('_regions.txt')]
        n = sum(1 for _ in open(os.path.join(od, reg[0]))) - (1 if reg else 0) if reg else -1
        res['artifactmap_' + pl] = (n if r.returncode == 0 else 'FAILED ' + r.stderr[-200:])
        r = subprocess.run(['python3', TOOLS + 'flatplane.py', src, dec, str(W), str(H), str(f), '--fmt', '422', '--depth', '10'], capture_output=True, text=True, cwd=TOOLS)
        res['flatplane'] = r.stdout.strip().splitlines()[-4:] if r.returncode == 0 else 'FAILED ' + r.stderr[-200:]
    return res

if __name__ == '__main__':
    cell, bpp = sys.argv[1], float(sys.argv[2]); nf = int(sys.argv[3]) if len(sys.argv) > 3 else 12
    tabs_path = sys.argv[4] if len(sys.argv) > 4 else ROOT + 'out/tables/tables_p2.pkl'
    path, W, H = yuv.CELLS[cell]; od = ROOT + 'out/eval/'; os.makedirs(od, exist_ok=True)
    tag = '%s_%.1f' % (cell, bpp); dec = od + tag + '.yuv'
    if not os.path.exists(dec) or os.environ.get('RERUN'):
        run_codec(cell, bpp, nf, tabs_path, dec, od + tag + '.enclog')
    today = yuv.TODAY[cell] % ('%.1f' % bpp)
    f0 = 2; fr = list(range(f0, nf))
    out = {'cell': cell, 'bpp': bpp, 'frames': fr, 'mine': {}, 'today': {}}
    for name, d in (('mine', dec), ('today', today)):
        negs = [neg_frame(path, d, W, H, f, tag + name) for f in fr]; ps = [psnr_frame(path, d, W, H, f) for f in fr]
        out[name] = dict(neg=negs, psnr=ps, neg_mean=float(np.mean(negs)), neg_worst=float(np.min(negs)),
                         psnr_mean=[float(np.mean([p[i] for p in ps])) for i in range(3)], psnr_worst=[float(np.min([p[i] for p in ps])) for i in range(3)])
        fa = 8 if H == 720 else 6
        out[name]['tools_f%d' % fa] = tools(path, d, W, H, fa, od + tag + '_' + name, name)
    json.dump(out, open(od + tag + '.json', 'w'), indent=1)
    m, t = out['mine'], out['today']
    print('%s @%.1f | NEG mine %.2f (worst %.2f) today %.2f (worst %.2f) | PSNR mine %.2f/%.2f/%.2f today %.2f/%.2f/%.2f | worst-frame PSNR mine %.2f/%.2f/%.2f today %.2f/%.2f/%.2f' % (
        cell, bpp, m['neg_mean'], m['neg_worst'], t['neg_mean'], t['neg_worst'], *m['psnr_mean'], *t['psnr_mean'], *m['psnr_worst'], *t['psnr_worst']))
    print('  tools mine:', {k: v for k, v in m.items() if k.startswith('tools')})
    print('  tools today:', {k: v for k, v in t.items() if k.startswith('tools')})
