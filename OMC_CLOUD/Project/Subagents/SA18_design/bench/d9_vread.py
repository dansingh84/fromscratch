# D9: can gen 2 re-derive source-searched vectors from the decoded picture? V1 = derive(S(t), D(t-1)) (what gen 1 used
# in the oracle run); V2 = derive(P1(t), D(t-1)) (same search on gen 2's input = gen 1's output). Agreement, and the
# share of blocks where the predictions differ.
import numpy as np, sys, yuv, motion
motion.BX = 64
for cell in sys.argv[1].split(','):
    p_, W, H = yuv.CELLS[cell]; DEC = '../out/dec/orc_%s_b0.5.d.yuv' % cell
    ag = []; pd = []
    for f in range(3, 11):
        S = yuv.read_frame(p_, W, H, f)[0]; P1 = yuv.read_frame(DEC, W, H, f)[0]; D1 = yuv.read_frame(DEC, W, H, f - 1)[0]
        V1 = motion.derive(S, D1, bx=64, lam=4); V2 = motion.derive(P1, D1, bx=64, lam=4)
        same = (np.abs(V1 - V2).sum(-1) == 0); ag.append(same.mean())
        pr1 = motion.predict(D1, V1); pr2 = motion.predict(D1, V2); diff = (pr1 != pr2)
        pd.append(diff.reshape(H // 8, 8, W // 64, 64).any(axis=(1, 3)).mean())
    print(cell, 'block vectors equal %.2f %%  blocks whose prediction differs %.2f %%' % (100 * np.mean(ag), 100 * np.mean(pd)), flush=True)
