#!/usr/bin/env python3
import glob, re, os, sys
D = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA11_plan/u4'
P3 = '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA8_r1lock/out/pP/run3'
exec(open('/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA11_plan/notes/u_parse.py').read().split("def main")[0])
def eplan_shifts(path, f, s):
    for ln in open(path):
        if ln.startswith('EPLAN %d %d ' % (f, s)):
            d = kv(ln); return d['shifts'], int(d['k']), d['prof'] + ',' + d['Q'] + ',' + d['ns'] + ',' + d['k']
    return None
def shv(path):
    out = {}
    for ln in open(path):
        if ln.startswith('R1U SHV'):
            d = kv(ln); out[int(d['r'])] = (d['shv'], int(d['k']))
    return out
def psnr_bits(logline): pass
res = {}
for ln in open(os.path.join(os.path.dirname(D), 'u4.log')):
    if ln.startswith('U4 '):
        x = ln.split()[1]; res[x] = ln.strip()
print('U4 per slice. Columns: alt plan | g1 bits | slice PSNR Y/Cb/Cr and d vs gen 1 choice | (i) rank of the alt on gen 1\'s decoded slice [exact there with gen 1\'s delta*: pstar] | (ii) on the alt\'s OWN decode: rank of its plan, rank 0 plan verify/pstar/bits*, first exact rank, rank-0 = fixed-path success (rank 0 verifies, exact with delta*, bits* <= own g1 bits)')
for base in sorted(glob.glob(D + '/*.base.g2.err')):
    X = os.path.basename(base)[:-len('.g2.err')]
    tag, fs = X.split('.')[0], X.split('.')[1]
    f, s = map(int, re.match(r'f(\d+)s(\d+)', fs).groups())
    g1 = D + '/' + X + '.g1'; n = os.path.getsize(g1)
    same = open(g1, 'rb').read() == open(P3 + '/' + tag + '.g1', 'rb').read(n)
    B = load(base, tag)[(tag, f, s)]
    bl = res.get(X, '')
    bb = int(re.search(r'g1_bits=(\d+)', bl).group(1)); bp = list(map(float, re.search(r'PSNR (\S+) (\S+) (\S+)', bl).groups()))
    sv = shv(base)
    bc = {c['r']: c for c in B['cand']}
    print('\n%s f=%d s=%d  base gen-1 prefix == census g1: %s ; gen 1 choice %s bits=%d PSNR %.3f/%.3f/%.3f ; gen-2 rank of gen 1 plan on its decode = %s of nlcand %s' % (
        tag, f, s, same, B['slice']['g1'], bb, bp[0], bp[1], bp[2], B['slice']['g1rank'], B['slice']['nlcand']))
    r0 = bc[0]
    print('   base rank 0: %s verify=%d pstar=%s bits*=%s ndiff_vs_g1=%d' % (r0['triple'], r0['verify'], r0['pstar'], r0['bits_star'], r0['ndiff']))
    for alt in sorted(glob.glob(D + '/%s.%s.a*.g2.err' % (tag, fs)), key=lambda p: int(p.split('.a')[-1].split('_')[2])):
        A = os.path.basename(alt)[:-len('.g2.err')]
        al = res.get(A, '')
        if not al: print('   %s: no result line' % A); continue
        ab = int(re.search(r'g1_bits=(\d+)', al).group(1)); ap = list(map(float, re.search(r'PSNR (\S+) (\S+) (\S+)', al).groups()))
        es = eplan_shifts(D + '/' + A + '.eplan.txt', f, s)
        ri = [r for r, (v, k) in sorted(sv.items()) if es and v == es[0] and k == es[1]]
        ri_s = 'rank %d' % ri[0] if ri else 'absent'
        if ri: ri_s += ' [pstar %s bits* %s]' % (bc[ri[0]]['pstar'] if bc[ri[0]]['verify'] else 'noverify', bc[ri[0]]['bits_star'])
        Aa = load(alt, tag)[(tag, f, s)]
        ac = Aa['cand']; a0 = ac[0]
        own = [c for c in ac if c['isg1']]
        own_b = own[0]['bits_star'] if own else -1
        fx = [c['r'] for c in ac if c['verify'] and c['pstar'] == 0]
        ok = a0['verify'] == 1 and a0['pstar'] == 0 and 0 <= a0['bits_star'] <= ab
        print('   alt %-10s emitted %-10s bits=%5d (d%+5d) PSNR %.3f/%.3f/%.3f (d %+.3f/%+.3f/%+.3f) | (i) %s | (ii) own rank %s, rank0 %s ver=%d pstar=%s p2=%s bits*=%s, first exact r=%s, own bits*=%s, FIXED-PATH %s' % (
            A.split('.a')[-1].replace('_', ','), es[2] if es else '?', ab, ab - bb, ap[0], ap[1], ap[2], ap[0] - bp[0], ap[1] - bp[1], ap[2] - bp[2],
            ri_s, Aa['slice']['g1rank'], a0['triple'], a0['verify'], a0['pstar'] if a0['verify'] else '-', a0['p2'] if a0['verify'] else '-', a0['bits_star'],
            fx[0] if fx else 'none', own_b, 'OK' if ok else ('FAIL(+%d bit)' % (a0['bits_star']-ab) if a0['verify']==1 and a0['pstar']==0 else 'FAIL')))
