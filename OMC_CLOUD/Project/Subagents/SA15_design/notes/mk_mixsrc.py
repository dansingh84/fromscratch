import sys,seq2,mk_mixed,mk_cut
class A: N=12
w=sys.argv[1]; fr=(mk_mixed if w=='mixed' else mk_cut).make(A)
seq2.write(sys.argv[2],fr)
