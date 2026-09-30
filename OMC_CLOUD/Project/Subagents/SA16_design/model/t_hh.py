# NEG-first restatement of the HH predictor choice: HH_TWO=0 (chosen) vs HH_TWO=1 (two-sided), training clip only.
import sys, os, numpy as np
sys.path.insert(0, '/home/user/fromscratch/OMC_CLOUD/Project/Subagents/SA16_design/model')
import omc16, yuv, evalcell
clip = yuv.TRAIN[0]; W, H = 1920, 1080; nf = 6; bpp = float(sys.argv[1]) if len(sys.argv) > 1 else 0.5
tag = 'hh%s_%.1f' % (os.environ.get('HH_TWO', '0'), bpp); out = evalcell.ROOT + 'out/eval/' + tag + '.yuv'
tabs = omc16.Tables(evalcell.ROOT + 'out/tables/tables_p2.pkl'); cod = omc16.Codec(W, H, S=8, bpp=bpp, tabs=tabs)
frames = []
for t in range(nf):
    rec = cod.encode(yuv.read_frame(clip, W, H, t)); frames.append(rec)
    print('f%d bits %d/%d %s' % (t, cod.stats['frame_bits'], cod.F, {k: v for k, v in cod.stats.items() if k not in ('frame_bits', 'est_bits')}), flush=True)
yuv.write_frames(out, frames)
negs = [evalcell.neg_frame(clip, out, W, H, f, tag) for f in range(2, nf)]; ps = [evalcell.psnr_frame(clip, out, W, H, f) for f in range(2, nf)]
print('%s NEG mean %.2f worst %.2f | PSNR %.2f/%.2f/%.2f | bits/frame mean %d' % (tag, np.mean(negs), np.min(negs), *np.mean(ps, 0), cod.F))
