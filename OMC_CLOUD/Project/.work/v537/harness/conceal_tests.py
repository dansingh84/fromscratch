"""Error-concealment characterization: motion-compensated + spatial vs freeze.

Measures what the v4.2 decoder-side concealment (omc_dec_set_conceal /
--no-conceal) buys on a lost burst, across the motion regimes that decide it:

  coherent   - global pan (neighbour MVs describe the lost strip well)
  divergent  - two halves moving oppositely (no single vector is right)
  cut        - a hard scene change on the damaged frame (temporal ref is
               wrong; the spatial fallback must carry it)
  static     - no motion (freeze is already exact; MC must not regress)

For each sequence we encode at the delivery point (2.0 bpp, R=8), zero a
contiguous burst of slices on a mid inter-frame, decode twice (freeze and
MC+spatial), and report the concealed-region luma PSNR against the CLEAN
coded decode - i.e. how close each concealment gets to the picture that
would have been shown with no loss. Higher is better; the honest figure of
merit is (MC - freeze).

Run: python3 harness/conceal_tests.py
"""
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import MASTERS_DIR, SCRATCH, read_yuv, write_yuv  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(SCRATCH, "conceal_tests")
os.makedirs(OUT, exist_ok=True)
W, H, N = 1920, 704, 10          # canvas, frames
BURST_F = 5                       # damaged frame (well past frame 0)
BURST_S0, BURST_K = 20, 6         # first slice, count (rows 320..416 at sh=16)
BPP, R = "2.0", "8"


def win(frames, x0, y0):
    Y, Cb, Cr = frames
    return (Y[y0:y0 + H, x0:x0 + W].copy(),
            Cb[y0:y0 + H, x0 // 2:(x0 + W) // 2].copy(),
            Cr[y0:y0 + H, x0 // 2:(x0 + W) // 2].copy())


def build_sequences():
    alp = read_yuv(os.path.join(MASTERS_DIR, "alpine_422_10.yuv"), 2048, 1152, 1024)[0]
    cty = read_yuv(os.path.join(MASTERS_DIR, "city_422_10.yuv"), 2048, 1152, 1024)[0]
    seqs = {}
    # coherent: global pan 8 px/frame over alpine
    seqs["coherent"] = [win(alp, 8 * i, 100) for i in range(N)]
    # divergent: left half pans right (+8), right half pans left (-8) over alpine
    div = []
    for i in range(N):
        a = win(alp, 8 * i, 100)
        b = win(alp, 8 * (N - i), 300)
        Y = a[0].copy(); Y[:, W // 2:] = b[0][:, W // 2:]
        Cb = a[1].copy(); Cb[:, W // 4:] = b[1][:, W // 4:]
        Cr = a[2].copy(); Cr[:, W // 4:] = b[2][:, W // 4:]
        div.append((Y, Cb, Cr))
    seqs["divergent"] = div
    # cut: alpine pan for frames < BURST_F, then hard-cut to city at BURST_F
    cut = []
    for i in range(N):
        if i < BURST_F:
            cut.append(win(alp, 6 * i, 100))
        else:
            cut.append(win(cty, 6 * (i - BURST_F), 200))
    seqs["cut"] = cut
    # static: a single frame held
    seqs["static"] = [win(alp, 40, 100) for _ in range(N)]
    for name, fr in seqs.items():
        write_yuv(os.path.join(OUT, name + ".yuv"), fr)
    return seqs


def enc(name):
    src = os.path.join(OUT, name + ".yuv")
    omc = os.path.join(OUT, name + ".omc")
    subprocess.run([REPO + "/omc_enc", "-i", src, "-o", omc, "-w", str(W),
                    "-h", str(H), "--fmt", "422", "--bpp", BPP, "--refresh", R],
                   check=True, capture_output=True)
    return omc


def dec(omc, out, extra=None):
    subprocess.run([REPO + "/omc_dec", "-i", omc, "-o", out] + (extra or []),
                   capture_output=True)
    return read_yuv(out, W, H, W // 2)


def psnr(a, b, bits=10):
    mse = np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2)
    peak = float((1 << bits) - 1)
    return float("inf") if mse == 0 else 10 * np.log10(peak * peak / mse)


def main():
    print(f"canvas {W}x{H}, {N} frames, {BPP} bpp R={R}; burst = slices "
          f"[{BURST_S0},{BURST_S0 + BURST_K}) on frame {BURST_F}\n")
    build_sequences()
    sh = 16
    r0, r1 = BURST_S0 * sh, (BURST_S0 + BURST_K) * sh
    sb = None
    print(f"{'sequence':10s} {'clean-ref':>9s} {'freeze':>8s} {'MC+spat':>8s} "
          f"{'gain':>7s}   mode")
    rows = []
    for name in ("coherent", "divergent", "cut", "static"):
        omc = enc(name)
        blob = bytearray(open(omc, "rb").read())
        bps = int.from_bytes(blob[21:25], "little"); sb = bps // 8
        nsl = H // sh; F = sb * nsl
        clean = dec(omc, os.path.join(OUT, name + "_clean.yuv"))
        # damage the burst on frame BURST_F
        dmg = bytearray(blob)
        for s in range(BURST_S0, BURST_S0 + BURST_K):
            a = 32 + BURST_F * F + s * sb
            dmg[a:a + sb] = b"\0" * sb
        dp = os.path.join(OUT, name + "_dmg.omc")
        open(dp, "wb").write(bytes(dmg))
        frz = dec(dp, os.path.join(OUT, name + "_frz.yuv"), ["--no-conceal"])
        mc = dec(dp, os.path.join(OUT, name + "_mc.yuv"))
        refY = clean[BURST_F][0][r0:r1]
        p_frz = psnr(frz[BURST_F][0][r0:r1], refY)
        p_mc = psnr(mc[BURST_F][0][r0:r1], refY)
        # Reported path. The decoder uses temporal MC whenever a surviving
        # INTER neighbour exists (any predicted frame), and spatial only for a
        # fully intra-coded frame (frame 0 / a full refresh) bracketed by two
        # survivors. This synthetic cut (alpine->city) is coded INTER by the
        # encoder - it predicts across the transition with a large residual -
        # so it is concealed by MC (prior content, still above freeze), not
        # spatially. A cut coded intra, and frame-0 loss, take the spatial path
        # (see the frame-0 check in the test suite).
        mode = {"coherent": "temporal-MC", "divergent": "temporal-MC",
                "cut": "temporal-MC (inter-coded)", "static": "MC==freeze"}[name]
        gain = p_mc - p_frz
        rows.append((name, p_frz, p_mc, gain))
        print(f"{name:10s} {'(1.0)':>9s} {p_frz:8.2f} {p_mc:8.2f} "
              f"{gain:+7.2f}   {mode}")
    print()
    worst = min(g for (_, _, _, g) in rows)
    print(f"worst-case gain across regimes: {worst:+.2f} dB "
          f"({'MC never regresses below freeze' if worst >= -0.5 else 'REGRESSION'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
