import numpy as np
def bd(a, b):
    wa = (6 * a[:, 1] + a[:, 2] + a[:, 3]) / 8; wb = (6 * b[:, 1] + b[:, 2] + b[:, 3]) / 8
    pa = np.polyfit(wa, np.log(a[:, 0]), 3); pb = np.polyfit(wb, np.log(b[:, 0]), 3)
    lo, hi = max(wa.min(), wb.min()), min(wa.max(), wb.max())
    ia = np.polyval(np.polyint(pa), [lo, hi]); ib = np.polyval(np.polyint(pb), [lo, hi])
    return 100 * (np.exp(((ib[1] - ib[0]) - (ia[1] - ia[0])) / (hi - lo)) - 1)
