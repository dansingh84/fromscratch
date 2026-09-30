# median per-block luma sigma-hat: temporal (frame difference, as the gate uses) vs spatial (Immerkaer), frames 0->1
import sys, os, numpy as np
sys.argv = [sys.argv[0], sys.argv[1], 'cm1'] + sys.argv[2:]
os.environ.setdefault('NF', '2')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'bench')); __file__ = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'bench', 'rcl_cbr.py')
src = open(__file__).read().split('\nfor R in RATES:')[0]
exec(src)
st = noise_gate(X[1], X[0], 0); t_ = float(np.median(SIG[0]))
NBY, NBX = (H + 15) // 16, (W + 15) // 16; lum = np.zeros((NBY * 16, NBX * 16)); lum[:H, :W] = X[1][0]
lb = np.minimum((lum.reshape(NBY, 16, NBX, 16).mean(axis=(1, 3)) / 128).astype(int), 7)
print(sys.argv[1], 'temporal %.2f spatial %.2f' % (t_, float(np.median(spatial_sigma(X[1][0], lb, 16)))))
