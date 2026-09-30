# per-row-phase error statistics: for each plane, mean |dec-src| and mean (dec-src) per row phase of the slice
# (r mod S) and of the 4-row block (r mod 4), over the steady-state frames; slice-edge excess in percent.
import sys, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import yuv
def stats(src, dec, W, H, frames, S, fmt=422):
    out = {}
    for p, name in enumerate(('Y', 'Cb', 'Cr')):
        acc_abs = None; acc_sgn = None
        for f in frames:
            s = yuv.read_frame(src, W, H, f)[p]; d = yuv.read_frame(dec, W, H, f)[p]; e = (d - s).astype(np.float64)
            a = np.abs(e).mean(1); g = e.mean(1)
            acc_abs = a if acc_abs is None else acc_abs + a; acc_sgn = g if acc_sgn is None else acc_sgn + g
        acc_abs /= len(frames); acc_sgn /= len(frames)
        rows = np.arange(acc_abs.size)
        ph = [float(acc_abs[rows % S == i].mean()) for i in range(S)]; sg = [float(acc_sgn[rows % S == i].mean()) for i in range(S)]
        ph4 = [float(acc_abs[rows % 4 == i].mean()) for i in range(4)]
        mean = float(acc_abs.mean()); edge = (ph[0] + ph[S - 1]) / 2; inner = float(np.mean(ph[1:S - 1])) if S > 2 else mean
        out[name] = dict(phase_abs=ph, phase_signed=sg, block_phase_abs=ph4, mean_abs=mean, edge_excess_pct=100 * (edge / inner - 1),
                         spread_pct=100 * (max(ph) - min(ph)) / mean)
    return out
if __name__ == '__main__':
    src, dec, W, H, S = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
    frames = [int(x) for x in sys.argv[6].split(',')] if len(sys.argv) > 6 else list(range(2, 12))
    r = stats(src, dec, W, H, frames, S)
    for name in ('Y', 'Cb', 'Cr'):
        v = r[name]
        print('%-2s mean|e| %.3f | slice-phase |e| %s | edge excess %+.2f %% | spread %.2f %% | block-phase %s | signed %s' % (
            name, v['mean_abs'], ' '.join('%.3f' % x for x in v['phase_abs']), v['edge_excess_pct'], v['spread_pct'],
            ' '.join('%.3f' % x for x in v['block_phase_abs']), ' '.join('%+.3f' % x for x in v['phase_signed'])))
