"""evaluate a seq.py run on its steady-state inter frames 2..11 with the owner's instruments.
usage: evalseq.py tag W H sh [today_decode.yuv]  (today decode: 12-frame file, evaluated the same way for comparison)"""
import sys, os, json, subprocess, re, numpy as np
T = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/shared_tools'
ANTS = '/home/user/fromscratch/OMC_CLOUD/Project/.work/v537/tests/ants.py'
SCR = os.environ['SCR']
tag, W, H, sh = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), sys.argv[4]
fs = W * H * 2
def sub(src, dst, a, b):
    d = np.fromfile(src, dtype='<u2'); d[a * fs:b * fs].tofile(dst)
def run(cmd): return subprocess.run(cmd, capture_output=True, text=True, cwd=T).stdout
def evaluate(name, dec, src):
    s2 = os.path.join(SCR, name + '.s2.yuv'); d2 = os.path.join(SCR, name + '.d2.yuv')
    sub(src, s2, 2, 12); sub(dec, d2, 2, 12)
    r = {}
    r['NEG_f2_11'] = run(['bash', T + '/negscore.sh', s2, d2, str(W), str(H), '422', '10', '10']).strip().splitlines()[-1]
    ps = run(['python3', T + '/planepsnr.py', s2, d2, str(W), str(H), '422', '10', '10', name]).strip().splitlines()[-1]
    v = [tuple(map(float, x.split('/'))) for x in re.findall(r'f\d+ (\S+)', ps)]
    r['PSNR_mean_f2_11'] = '/'.join('%.2f' % np.mean([a[i] for a in v]) for i in range(3))
    r['PSNR_worst_f2_11'] = '/'.join('%.2f' % np.min([a[i] for a in v]) for i in range(3))
    r['ants'] = run(['python3', ANTS, s2, d2, str(W), str(H), '422', '10']).strip().splitlines()[-4:]
    r['smudge_f8'] = [l for l in run(['python3', T + '/smudgegroups.py', src, dec, str(W), str(H), '8', os.path.join(os.getcwd(), name + '_f8_smudge'), '--sh', sh, '--fmt', '422']).splitlines() if 'groups' in l]
    r['flatplane_f8'] = run(['python3', T + '/flatplane.py', src, dec, str(W), str(H), '8', '--fmt', '422']).strip().splitlines()[-1:]
    r['texstat_f8'] = [l for l in run(['python3', T + '/texstat.py', src, dec, str(W), str(H), '8', '--fmt', '422']).splitlines() if 'TEXSTAT' in l]
    os.remove(s2); os.remove(d2); return r
res = {tag: evaluate(tag, os.path.join(SCR, tag + '.dec.yuv'), os.path.join(SCR, tag + '.src.yuv'))}
if len(sys.argv) > 5: res['today'] = evaluate(tag + '_today', sys.argv[5], os.path.join(SCR, tag + '.src.yuv'))
js = json.load(open(tag + '.seq.json')); res[tag]['bpp_mean_f2_11'] = float(np.mean(js['bpp'][2:])); res[tag]['bpp_max_f2_11'] = float(np.max(js['bpp'][2:]))
res[tag]['changed_per_frame_Y/Cb/Cr'] = [['%.4f' % x for x in c] for c in js['changed']]
json.dump(res, open(tag + '.eval.json', 'w'), indent=1); print(json.dumps(res, indent=1))
