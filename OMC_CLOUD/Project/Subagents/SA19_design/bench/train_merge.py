import sys, pickle, ent
t = ent.Tables()
for f in sys.argv[2:]:
    for k, a in pickle.load(open(f, 'rb')).items():
        t.cnt[k] = t.cnt.get(k, 0) + a
t.build(sys.argv[1]); print('tables', len(t.len))
