"""Motion-tool evaluation (v3.1): what per-region + half-pel search buys.

Synthesizes two labeled test sequences from the customer masters:
  - multiobject: 1920x704 canvas, left half pans right (+6 px/frame windows
    over alpine), right half pans left (-6 px/frame windows over city) -
    divergent motion no single global vector can serve.
  - halfpelpan: 1920x704 window over alpine advancing 2.5 px/frame - true
    fractional motion (integer vectors are wrong by 0.5 px on odd frames).

Encodes each three ways at the delivery rate (2.0 bpp):
  no-mv (OMC_NO_MV=1), global (default), regions (--mv-regions),
reports per-frame luma PSNR of steady frames, and runs a 4-generation
re-encode loop for the regions mode to measure reconvergence honestly.

Run: python3 harness/motion_tests.py
"""

import json
import os
import subprocess

import numpy as np

from common import MASTERS_DIR, SCRATCH, psnr_all, read_yuv, write_yuv

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(SCRATCH, "motion_tests")
W, H, N = 1920, 704, 12


def window(frames, x0, y0):
    Y, Cb, Cr = frames
    return (Y[y0:y0 + H, x0:x0 + W].copy(),
            Cb[y0:y0 + H, x0 // 2:(x0 + W) // 2].copy(),
            Cr[y0:y0 + H, x0 // 2:(x0 + W) // 2].copy())


def halfpel_window(frames, x2, y0):
    """Window at half-pel horizontal position x2/2 (x2 in half-pels):
    even x2 = copy, odd x2 = (a+b+1)>>1 between neighbours."""
    Y, Cb, Cr = frames
    xi = x2 // 2
    if x2 % 2 == 0:
        return window(frames, xi, y0)
    def hp(P, xa, wa):
        a = P[y0:y0 + H, xa:xa + wa].astype(np.int32)
        b = P[y0:y0 + H, xa + 1:xa + 1 + wa].astype(np.int32)
        return ((a + b + 1) >> 1).astype(np.uint16)
    return (hp(Y, xi, W), hp(Cb, xi // 2, W // 2), hp(Cr, xi // 2, W // 2))


def build_sequences():
    os.makedirs(OUT, exist_ok=True)
    alp = read_yuv(os.path.join(MASTERS_DIR, "alpine_422_10.yuv"), 2048, 1152, 1024)[0]
    cty = read_yuv(os.path.join(MASTERS_DIR, "city_422_10.yuv"), 2048, 1152, 1024)[0]
    mo, hp = [], []
    for k in range(N):
        l = window(alp, 8 + 6 * k, 200)       # pans right
        r = window(cty, 8 + 6 * (N - 1 - k), 320)  # pans left
        Y = np.hstack([l[0][:, :W // 2], r[0][:, W // 2:]])
        Cb = np.hstack([l[1][:, :W // 4], r[1][:, W // 4:]])
        Cr = np.hstack([l[2][:, :W // 4], r[2][:, W // 4:]])
        mo.append((Y, Cb, Cr))
        hp.append(halfpel_window(alp, 16 + 5 * k, 260))  # +2.5 px/frame
    write_yuv(os.path.join(OUT, "multiobject.yuv"), mo)
    write_yuv(os.path.join(OUT, "halfpelpan.yuv"), hp)


def run(src, tag, extra=None, env=None):
    bs = os.path.join(OUT, f"{tag}.omc")
    dc = os.path.join(OUT, f"{tag}.yuv")
    ev = dict(os.environ)
    if env:
        ev.update(env)
    cmd = [os.path.join(REPO, "omc_enc"), "-i", src, "-o", bs, "-w", str(W),
           "-h", str(H), "--fmt", "422", "--bpp", "2.0"] + (extra or [])
    subprocess.run(cmd, check=True, capture_output=True, env=ev)
    subprocess.run([os.path.join(REPO, "omc_dec"), "-i", bs, "-o", dc],
                   check=True, capture_output=True)
    return dc


def psnr_trace(src, dec):
    s = read_yuv(src, W, H, W // 2)
    d = read_yuv(dec, W, H, W // 2)
    return [round(psnr_all(a, b)["Y"], 2) for a, b in zip(s, d)]


def main():
    build_sequences()
    res = {}
    for seq in ("multiobject", "halfpelpan"):
        src = os.path.join(OUT, f"{seq}.yuv")
        res[seq] = {}
        for tag, extra, env in (("nomv", None, {"OMC_NO_MV": "1"}),
                                ("global", None, None),
                                ("regions", ["--mv-regions"], None)):
            dc = run(src, f"{seq}_{tag}", extra, env)
            tr = psnr_trace(src, dc)
            res[seq][tag] = {"trace": tr, "steady_min": min(tr[2:])}
        # generation behavior of the opt-in mode: gens 1..4, regions on
        cur, gens = src, []
        for g in range(1, 5):
            dc = run(cur, f"{seq}_gen{g}", ["--mv-regions"])
            gens.append(dc)
            cur = dc
        ident = [open(gens[i], "rb").read() == open(gens[i - 1], "rb").read()
                 for i in range(1, 4)]
        res[seq]["regions_gens"] = {
            "gen_vs_prev_identical": ident,
            "gen4_vs_gen2_psnrY": round(psnr_all(
                read_yuv(gens[3], W, H, W // 2)[N - 1],
                read_yuv(gens[1], W, H, W // 2)[N - 1])["Y"], 2),
        }
        print(seq, json.dumps(res[seq], indent=1), flush=True)
    with open(os.path.join(OUT, "motion_results.json"), "w") as f:
        json.dump(res, f, indent=1)


if __name__ == "__main__":
    main()
