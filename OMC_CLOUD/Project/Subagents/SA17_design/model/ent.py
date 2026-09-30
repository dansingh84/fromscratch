# SA17 entropy model: magnitude-class symbols, static tANS tables (L=1024), REAL code lengths
# (sum of log2(L/f) for the class symbol + raw mantissa bits + sign bit; +12 bits state flush per stream).
import numpy as np, pickle
L = 1024
NC = 18                      # class 0 = zero, class c>=1 : 2^(c-1) <= |q| < 2^c
GROUP = {'H2': 3, 'LL': 0, 'H5': 1, 'H4': 2, 'H3': 3, 'HL2': 4, 'LH2': 4, 'HH2': 5, 'HL1': 6, 'LH1': 6, 'HH1': 7}
NCTX = 4

def cls(q):
    a = np.abs(q)
    return np.where(a == 0, 0, np.floor(np.log2(np.maximum(a, 1))).astype(np.int64) + 1)

def ctx(c):
    """causal context from the classes of the left and above neighbours in the same band (index based,
    therefore independent of the decoder's clamps)."""
    left = np.zeros_like(c); left[:, 1:] = c[:, :-1]
    up = np.zeros_like(c); up[1:] = c[:-1]
    s = left + up
    return np.minimum(NCTX - 1, (s + 1) // 2)

NEB = 3
def ebucket(e):
    return np.minimum(NEB - 1, np.maximum(0, (np.asarray(e) - 1) // 2))     # e<=2 -> 0, 3-4 -> 1, >=5 -> 2
def table_key(plane, band, inter, eb=0):
    return (0 if plane == 0 else 1, GROUP[band], int(inter), int(eb))

class Tables:
    def __init__(self, path=None):
        self.cnt = {}; self.len = {}
        if path:
            self.len = pickle.load(open(path, 'rb'))
            for k in list(self.len):              # tables trained before step buckets: same table for every bucket
                if len(k) == 3:
                    for eb in range(3): self.len.setdefault(k + (eb,), self.len[k])
    def add(self, key, c, cx):
        a = self.cnt.setdefault(key, np.zeros((NCTX, NC)))
        np.add.at(a, (cx.ravel(), np.minimum(c.ravel(), NC - 1)), 1)
    def build(self, path=None, prior=0.3):
        self.len = {}
        for k, a in self.cnt.items():
            ln = np.zeros_like(a)
            for x in range(NCTX):
                p = a[x] + prior
                f = np.maximum(1, np.round(p / p.sum() * (L - NC)).astype(np.int64))
                # renormalise to sum L exactly (tANS table size)
                while f.sum() > L: f[np.argmax(f)] -= 1
                while f.sum() < L: f[np.argmax(f)] += 1
                ln[x] = np.log2(L / f)
            self.len[k] = ln
        if path: pickle.dump(self.len, open(path, 'wb'))
    def bits(self, key, q, rowsum=False):
        """bits per row (if rowsum) or total, for index array q (2-D, raster)."""
        c = cls(q); cx = ctx(c)
        ln = self.len.get(key)
        if ln is None: ln = np.full((NCTX, NC), np.log2(NC))
        b = ln[cx, np.minimum(c, NC - 1)] + np.maximum(c - 1, 0) + (c > 0)
        return b.sum(axis=1) if rowsum else b.sum()
