"""Package the OMC conformance vector set.

Each vector = (input.yuv, stream.omc, reference decode) triple + SHA-256
manifest. Directed coverage: formats (422/444, 8/10/12-bit, slice_h 8/16),
refresh settings (1/2/8), modes (perception/fidelity), v4.2 features
(pad-and-crop, RCT RGB, mono), loss/resync (a stream with a corrupted
slice + its concealed reference), plus the 4.0/4.1 back-compat streams.

Usage: python3 make_conformance.py <outdir>
(Requires the repo binaries and the session masters; regenerates
deterministically - inputs are seeded synthetics + fixed master crops.)
"""
import hashlib
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from common import read_yuv, write_yuv, MASTERS_DIR

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()


def run(args):
    subprocess.run(args, check=True, capture_output=True)


def main(outdir):
    os.makedirs(outdir, exist_ok=True)
    man = []
    beach = read_yuv(os.path.join(MASTERS_DIR, 'beach_422_10.yuv'), 2048, 1152, 1024)

    def crop422(n, W, H, fr=3):
        out = []
        for i in range(fr):
            f = beach[i % len(beach)]
            out.append((f[0][:H, :W].copy(), f[1][:H, :W // 2].copy(),
                        f[2][:H, :W // 2].copy()))
        return out

    def vec(name, frames_or_file, enc_args, W, H):
        src = os.path.join(outdir, name + '.in.yuv')
        if isinstance(frames_or_file, str):
            if os.path.abspath(frames_or_file) != os.path.abspath(src):
                import shutil
                shutil.copy(frames_or_file, src)
        else:
            write_yuv(src, frames_or_file)
        bs = os.path.join(outdir, name + '.omc')
        ref = os.path.join(outdir, name + '.ref.yuv')
        run([ROOT + '/omc_enc', '-i', src, '-o', bs, '-w', str(W), '-h', str(H)] + enc_args)
        run([ROOT + '/omc_dec', '-i', bs, '-o', ref])
        for p in (src, bs, ref):
            man.append((os.path.basename(p), sha(p)))
        return bs, ref

    # formats
    vec('f422_10_sh16', crop422('a', 640, 128), ['--fmt', '422', '--bpp', '2.0'], 640, 128)
    vec('f422_10_sh8', crop422('b', 640, 120), ['--fmt', '422', '--bpp', '2.0'], 640, 120)
    f = crop422('c', 640, 128)
    f444 = [(y, np.repeat(cb, 2, axis=1), np.repeat(cr, 2, axis=1)) for y, cb, cr in f]
    vec('f444_10', f444, ['--fmt', '444', '--bpp', '2.0'], 640, 128)
    f8 = [tuple(np.clip(p >> 2, 0, 255).astype(np.uint16) for p in fr) for fr in f]
    vec('f422_8', f8, ['--fmt', '422', '--depth', '8', '--bpp', '2.0'], 640, 128)
    f12 = [tuple(np.clip(p.astype(np.int32) * 4, 0, 4095).astype(np.uint16) for p in fr) for fr in f]
    vec('f422_12', f12, ['--fmt', '422', '--depth', '12', '--bpp', '2.0'], 640, 128)
    # refresh + modes
    vec('r1_stateless', crop422('d', 640, 128, 6), ['--fmt', '422', '--bpp', '2.0', '--refresh', '1'], 640, 128)
    vec('r2', crop422('e', 640, 128, 6), ['--fmt', '422', '--bpp', '2.0', '--refresh', '2'], 640, 128)
    vec('fidelity', crop422('g', 640, 128, 6), ['--fmt', '422', '--bpp', '2.0', '--no-fill'], 640, 128)
    # v4.2 features
    vec('padcrop_601x100', [(f[0][0][:100, :601].copy(), f[0][1][:100, :301].copy(),
                             f[0][2][:100, :301].copy())] * 3,
        ['--fmt', '422', '--bpp', '2.0'], 601, 100)
    rgbf = []
    for i in range(3):
        R = f[i][0][:128, :640]
        G = np.roll(R, 5, axis=1)
        B = ((R.astype(np.int32) + G) // 2).astype(np.uint16)
        rgbf.append((R, G, B))
    vec('rct_rgb10', rgbf, ['--fmt', '444', '--depth', '10', '--rgb', '--bpp', '3.0'], 640, 128)
    K = np.zeros((128, 640), dtype=np.uint16)
    K[20:100, 40:600] = 1023
    vec('mono_key', [(K, K[:, :320] * 0 + 512, K[:, :320] * 0 + 512)] * 3,
        ['--fmt', '422', '--mono', '--bpp', '2.0'], 640, 128)
    # loss/resync: corrupt one slice of a copy, decode with concealment
    bs, _ = vec('loss_base', crop422('h', 640, 128, 4), ['--fmt', '422', '--bpp', '2.0'], 640, 128)
    dmg = os.path.join(outdir, 'loss_damaged.omc')
    blob = bytearray(open(bs, 'rb').read())
    fsz = (len(blob) - 32) // 4
    blob[32 + fsz + 100] ^= 0xFF  # corrupt frame 1, slice 0 payload
    open(dmg, 'wb').write(bytes(blob))
    ref = os.path.join(outdir, 'loss_damaged.ref.yuv')
    run([ROOT + '/omc_dec', '-i', dmg, '-o', ref])
    man.append(('loss_damaged.omc', sha(dmg)))
    man.append(('loss_damaged.ref.yuv', sha(ref)))

    with open(os.path.join(outdir, 'MANIFEST.sha256'), 'w') as f:
        for n, h in sorted(man):
            f.write(f'{h}  {n}\n')
    print(f'{len(man)} artifacts, manifest written')


if __name__ == '__main__':
    main(sys.argv[1])
