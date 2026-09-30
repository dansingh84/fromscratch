import sys; sys.argv=['x','run1','lists/tags.txt']
exec(open('notes/u_parse.py').read().split("if __name__")[0])
tags={}
for ln in open('lists/tags.txt'):
    c,f,s,t=ln.split(); tags[(c,int(f),int(s))]=t
S={}
for cell in ('gfx_05','gfx8_05','spot_10','d7x8_05'): S.update(load('run1/%s.g2.err'%cell,cell))
fn=dict(FEATS)
for name in ('x_exact_then_bits2','c_bits2','e_keyE','key'):
  for k in sorted(S):
    if not tags.get(k,'').startswith('C'): continue
    p=position(S[k]['cand'],fn[name])
    if p and p[0]>0:
      g=[c for c in S[k]['cand'] if c['isg1']][0]
      b=[c for c in S[k]['cand'] if c['verify'] and fn[name](c)<fn[name](g)]
      print(name,k,S[k]['slice']['sites'],'g1: r%d p2=%d bits2=%d pstar=%d bits*=%d'%(g['r'],g['p2'],g['bits2'],g['pstar'],g['bits_star']),
            '| better:',['r%d %s p2=%d bits2=%d pstar=%d bits*=%d nd=%d'%(c['r'],c['triple'],c['p2'],c['bits2'],c['pstar'],c['bits_star'],c['ndiff']) for c in b[:3]])
