#!/usr/bin/env python3
"""[SA11 U] parse R1U lines. usage: u_parse.py <run dir> <tags file>"""
import sys, re, collections
def kv(line):
    d = {}
    for t in line.split():
        if '=' in t:
            k, v = t.split('=', 1); d[k] = v
    return d
def load(path, cell):
    S = {}; last_fail = None
    for ln in open(path, errors='replace'):
        if ln.startswith('R1VFAIL'):
            last_fail = kv(ln); continue
        if not ln.startswith('R1U '):
            if not ln.startswith('R1VFAIL'): pass
            continue
        d = kv(ln); f, s = int(d['f']), int(d['s'])
        key = (cell, f, s)
        if ln.startswith('R1U SLICE'):
            S[key] = {'slice': d, 'cand': [], 'keyb': []}; last_fail = None
        elif ln.startswith('R1U KEYB'):
            S[key]['keyb'].append(d)
        elif ln.startswith('R1U CAND'):
            d['fail'] = last_fail if d['verify'] == '0' else None
            last_fail = None
            for k in ('r', 'verify', 'isg1', 'fine', 'ndiff'): d[k] = int(d[k])
            for k in ('key', 'keyrc', 'keyE', 'fineN', 'pstar', 'bits_star', 'Rstar', 'p2', 'bits2', 'R2'):
                d[k] = int(d[k])
            S[key]['cand'].append(d)
    return S
FEATS = [('a_R2', lambda c: c['R2']), ('b_p2', lambda c: c['p2']), ('c_bits2', lambda c: c['bits2']),
         ('c_bitsstar', lambda c: c['bits_star']), ('d_finest', lambda c: c['fine']),
         ('d_coarsest', lambda c: -c['fine']), ('d_finestN', lambda c: c['fineN']),
         ('d_coarsestN', lambda c: -c['fineN']), ('e_keyE', lambda c: c['keyE']), ('key', lambda c: c['key']),
         ('x_exact_then_bits2', lambda c: (c['p2'] != 0, c['bits2'])),
         ('x_R2_then_bits2', lambda c: (c['R2'], c['bits2'])),
         ('x_Rstar', lambda c: c['Rstar'])]
def position(cands, fn):
    V = [c for c in cands if c['verify'] == 1]
    g = [c for c in V if c['isg1'] == 1]
    if not g: return None
    g = g[0]; gv = fn(g)
    better = sum(1 for c in V if c is not g and fn(c) < gv)
    ties = [c for c in V if c is not g and fn(c) == gv]
    equiv = sum(1 for c in ties if c['pstar'] == 0 and c['bits_star'] == g['bits_star'])
    return better, len(ties), equiv, len(V)

def main():
    rd = sys.argv[1]; tags = {}
    for ln in open(sys.argv[2]):
        c, f, s, t = ln.split(); tags[(c, int(f), int(s))] = t
    S = {}
    for cell in ('gfx_05', 'gfx8_05', 'spot_10', 'd7x8_05'):
        try: S.update(load('%s/%s.g2.err' % (rd, cell), cell))
        except FileNotFoundError: pass
    # discriminator: recomputed key == stored key on every candidate; table recompute exact
    nc = sum(len(v['cand']) for v in S.values())
    bad = sum(1 for v in S.values() for c in v['cand'] if c['key'] != c['keyrc'])
    tm = collections.Counter(v['slice'].get('tabmis') for v in S.values())
    print('DISCRIMINATOR slices=%d candidates=%d key_recompute_mismatch=%d tabmis=%s' % (len(S), nc, bad, dict(tm)))
    # ---- U1 ----
    print('\n==== U1 PLAN-CLASS SLICES: candidates in rank order up to gen 1\'s plan ====')
    for key in sorted(S):
        if tags.get(key) != 'PLAN': continue
        v = S[key]; sl = v['slice']
        print('\n%s f=%d s=%d  sites=%s naff=%s nlcand=%s  gen1 plan=%s modes=%s part(pc,pp,pb,selon)=%s  gen1 rank=%s  emitted at g2=%s modes=%s bits=%s budget_hard=%s' % (
            key[0], key[1], key[2], sl['sites'], sl['naff'], sl['nlcand'], sl['g1'], sl['g1_modes'], sl['g1_part'],
            sl['g1rank'], sl['emitted'], sl['emitted_modes'], sl['emitted_bits'], sl['budget_hard']))
        g1r = int(sl['g1rank']); last = g1r if g1r >= 0 else len(v['cand']) - 1
        print('  r triple      key  keyE fine ver vxor cxor pstar bits* ndiff first_fail / band shifts (cand/gen1)')
        for c in v['cand']:
            if c['r'] > last: break
            ff = ''
            if c['fail']:
                F = c['fail']; ff = 'FAIL %s p%s b%s i%s val=%s sh=%s diff=%s aff=%s' % (F.get('stage'), F.get('p'), F.get('b'), F.get('i'), F.get('val'), F.get('sh'), F.get('diff'), F.get('aff'))
            print('  %2d %-11s %5d %5d %4d %d %5s %4s %5s %5s %2d %s %s' % (c['r'], c['triple'], c['key'], c['keyE'], c['fine'], c['verify'],
                  c['vxor'], c['cxor'], c['pstar'] if c['verify'] else '-', c['bits_star'] if c['verify'] else '-', c['ndiff'], ff,
                  c['diffs'] if c['ndiff'] else '(= gen 1 plan)'))
        if v['keyb']:
            print('  U2 key breakdown rank0 vs gen1 (bands differing):')
            dk = dke = dka = 0
            for k in v['keyb']:
                d = int(k['key_rank0']) - int(k['key_g1']); de = int(k['keyE_rank0']) - int(k['keyE_g1'])
                dk += d; dke += de
                if int(k['naff']) > 0: dka += d
                print('    p%s b%s shift %s/%s mode %s/%s key %s/%s (d=%+d) keyE %s/%s (d=%+d) naff=%s of n=%s' % (
                    k['p'], k['b'], k['s_rank0'], k['s_g1'], k['m_rank0'], k['m_g1'], k['key_rank0'], k['key_g1'], d,
                    k['keyE_rank0'], k['keyE_g1'], de, k['naff'], k['n']))
            print('    TOTAL key d=%+d (bands with affected coefs %+d, without %+d); keyE d=%+d' % (dk, dka, dk - dka, dke))
    # ---- U3 ----
    print('\n==== U3 FEATURES: position of gen 1\'s plan among VERIFYING candidates of ranks 0..RC-1 ====')
    print('  per slice: better/ties(equiv)/|S|; first = better 0 and ties 0; equiv = tie with pstar 0 and same bits*')
    groups = collections.defaultdict(list)
    for key in sorted(S):
        t = tags.get(key, '?'); groups[t].append(key)
    for t in ('PLAN',):
        for key in groups[t]:
            v = S[key]
            print('  %s %s f=%d s=%d:' % (t, key[0], key[1], key[2]), ' '.join('%s=%s' % (n, '%d/%d(%d)/%d' % position(v['cand'], fn) if position(v['cand'], fn) else 'g1_not_verifying') for n, fn in FEATS))
    print('\n  summary per feature and class: first / tied-first (all ties equivalent) / tied-first (a non-equivalent tie) / demoted / g1 not in S')
    for t in ('PLAN', 'C_site', 'C_nosite', 'M_site', 'M_nosite'):
        ks = groups.get(t, [])
        print('  class %s (%d slices)' % (t, len(ks)))
        for n, fn in FEATS:
            cnt = collections.Counter()
            for key in ks:
                p = position(S[key]['cand'], fn)
                if p is None: cnt['notinS'] += 1
                elif p[0] > 0: cnt['demoted'] += 1
                elif p[1] == 0: cnt['first'] += 1
                elif p[2] == p[1]: cnt['tie_equiv'] += 1
                else: cnt['tie_nonequiv'] += 1
            print('    %-20s first %3d  tie_equiv %3d  tie_nonequiv %3d  demoted %3d  notinS %3d' % (n, cnt['first'], cnt['tie_equiv'], cnt['tie_nonequiv'], cnt['demoted'], cnt['notinS']))
if __name__ == '__main__': main()
