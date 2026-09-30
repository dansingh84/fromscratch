"""Bucket-3 validation: 12-bit real-content, PQ-statistics HDR stress, 8K canvas.

All material is derived from the customer masters and labeled for what it is:
  - twelve_bit: masters promoted 10->12 bit (<<2), coded at the delivery rate.
    Checks rt=0 (decode == encoder recon), exact CBR, per-plane PSNR (12-bit peak).
  - pq_stress: luma remapped through BT.1886 -> 100-nit -> SMPTE 2084 (PQ) into
    12-bit limited range (chroma promoted <<2). This is a *statistics* stress -
    PQ concentrates codes in the darks - not a color-managed grade, and is
    labeled as such. Signals transfer=16 (PQ) and verifies it round-trips.
    Adds a 12-bit PQ dark ramp banding tripwire (max reconstructed step <= 2
    codes at 12 bit, matching the 10-bit G2 gate).
  - eightk: 7680x4320 canvas tiled 1:1 (no rescale) from the masters' real
    pixels, 2 frames so temporal prediction runs. Checks rt=0, exact CBR,
    PSNR, and wall-clock software speed.

Run: python3 harness/hdr8k_tests.py
"""

import json
import os
import subprocess
import time

import numpy as np

from common import MASTERS_DIR, SCRATCH, psnr_all, read_yuv, write_yuv

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(SCRATCH, "hdr8k")
RES = {}


def enc_dec(src, w, h, depth, tag, transfer=None, frames=None):
    bs = os.path.join(OUT, f"{tag}.omc")
    dc = os.path.join(OUT, f"{tag}_dec.yuv")
    rc = os.path.join(OUT, f"{tag}_rec.yuv")
    cmd = [os.path.join(REPO, "omc_enc"), "-i", src, "-o", bs, "-w", str(w),
           "-h", str(h), "--fmt", "422", "--depth", str(depth), "--bpp", "2.0",
           "--recon", rc]
    if transfer is not None:
        cmd += ["--primaries", "9", "--transfer", str(transfer), "--matrix", "9"]
    t0 = time.time()
    subprocess.run(cmd, check=True, capture_output=True)
    t1 = time.time()
    subprocess.run([os.path.join(REPO, "omc_dec"), "-i", bs, "-o", dc],
                   check=True, capture_output=True)
    t2 = time.time()
    n = frames or 2
    F = int(2.0 * w * h / 8)
    size = os.path.getsize(bs)
    rt0 = open(dc, "rb").read() == open(rc, "rb").read()
    return {"bs": bs, "dec": dc, "rt0": rt0,
            "cbr_exact": size == 32 + n * F,
            "enc_s_per_frame": round((t1 - t0) / n, 2),
            "dec_s_per_frame": round((t2 - t1) / n, 2)}


def twelve_bit():
    out = {}
    for name, w, h in (("cow", 4480, 3072), ("beach", 2048, 1152),
                       ("couch12", 1920, 1056)):
        src = read_yuv(os.path.join(MASTERS_DIR, f"{name}_422_10.yuv"), w, h, w // 2)
        p12 = [(Y.astype(np.uint16) << 2, Cb << 2, Cr << 2) for Y, Cb, Cr in src]
        sp = os.path.join(OUT, f"{name}_12.yuv")
        write_yuv(sp, p12)
        r = enc_dec(sp, w, h, 12, f"{name}_12", frames=len(src))
        dec = read_yuv(r["dec"], w, h, w // 2)
        ps = [psnr_all(a, b, bits=12) for a, b in zip(p12, dec)]
        out[name] = {"rt0": r["rt0"], "cbr_exact": r["cbr_exact"],
                     "worst_psnr": {k: round(min(p[k] for p in ps), 2)
                                    for k in ("Y", "Cb", "Cr")}}
        for f in (sp, r["dec"], r["bs"], os.path.join(OUT, f"{name}_12_rec.yuv")):
            os.unlink(f)
        print("12bit", name, out[name], flush=True)
    RES["twelve_bit"] = out


def pq(l_norm):
    """SMPTE 2084 PQ OETF for display light l_norm in [0,1] (= L/10000 nits)."""
    m1, m2 = 2610 / 16384, 2523 / 4096 * 128
    c1, c2, c3 = 3424 / 4096, 2413 / 4096 * 32, 2392 / 4096 * 32
    y = np.power(np.clip(l_norm, 0, 1), m1)
    return np.power((c1 + c2 * y) / (1 + c3 * y), m2)


def pq_stress():
    out = {}
    for name, w, h in (("beach", 2048, 1152), ("couch12", 1920, 1056)):
        src = read_yuv(os.path.join(MASTERS_DIR, f"{name}_422_10.yuv"), w, h, w // 2)
        frames = []
        for Y, Cb, Cr in src:
            # BT.1886-ish display light from 10-bit limited-range SDR, mapped to
            # 100 nit peak, then PQ into 12-bit limited range. Chroma << 2.
            n = np.clip((Y.astype(np.float64) - 64) / 876, 0, 1)
            l = 100.0 * np.power(n, 2.4) / 10000.0
            y12 = np.round(pq(l) * 3504 + 256).astype(np.uint16)  # 256..3760
            frames.append((y12, Cb << 2, Cr << 2))
        sp = os.path.join(OUT, f"{name}_pq12.yuv")
        write_yuv(sp, frames)
        r = enc_dec(sp, w, h, 12, f"{name}_pq12", transfer=16, frames=len(frames))
        # colorimetry signaling round-trip
        hdr = open(r["bs"], "rb").read(32)
        sig_ok = hdr[17] == 9 and hdr[18] == 16 and hdr[19] == 9
        dec = read_yuv(r["dec"], w, h, w // 2)
        ps = [psnr_all(a, b, bits=12) for a, b in zip(frames, dec)]
        # dark-region fidelity: PSNR over PQ codes < 1600 (~< 5 nits)
        dm = []
        for (a, _, _), (b, _, _) in zip(frames, dec):
            m = a < 1600
            if m.any():
                e = (a[m].astype(np.int64) - b[m].astype(np.int64))
                dm.append(10 * np.log10(4095.0 ** 2 / max((e * e).mean(), 1e-9)))
        out[name] = {"rt0": r["rt0"], "cbr_exact": r["cbr_exact"], "sig_pq": sig_ok,
                     "worst_psnr": {k: round(min(p[k] for p in ps), 2)
                                    for k in ("Y", "Cb", "Cr")},
                     "dark_psnr_min": round(min(dm), 2) if dm else None}
        for f in (sp, r["dec"], r["bs"], os.path.join(OUT, f"{name}_pq12_rec.yuv")):
            os.unlink(f)
        print("pq12", name, out[name], flush=True)

    # PQ dark ramp banding tripwire at 12 bit (G2 analogue of the 10-bit gate).
    # The ramp is linear in PQ *code* space (codes 256..1256 ~= 0..2.5 nits):
    # that is what a real graded master contains - a ramp linear in nits is
    # not smooth in code space (PQ jumps ~37 codes across the first columns).
    w, hh = 1920, 512
    x = np.linspace(0, 1, w)
    y12 = np.round(256 + 1000 * x).astype(np.uint16)
    Y = np.tile(y12, (hh, 1))
    Cb = np.full((hh, w // 2), 2048, np.uint16)
    Cr = np.full((hh, w // 2), 2048, np.uint16)
    sp = os.path.join(OUT, "pqramp.yuv")
    write_yuv(sp, [(Y, Cb, Cr), (Y, Cb, Cr)])
    r = enc_dec(sp, w, hh, 12, "pqramp", transfer=16, frames=2)
    dec = read_yuv(r["dec"], w, hh, w // 2)
    step = max(int(np.max(np.abs(np.diff(d[0].astype(np.int64), axis=1)))) for d in dec)
    out["pq_dark_ramp_max_step"] = step
    RES["pq_stress"] = out
    for f in (sp, r["dec"], r["bs"], os.path.join(OUT, "pqramp_rec.yuv")):
        os.unlink(f)
    print("pq ramp max step:", step, "(gate <= 2)", flush=True)


def eightk():
    W, H = 7680, 4320
    tiles = [("cow", 4480, 3072), ("fence", 4480, 1856), ("alpine", 2048, 1152),
             ("city", 2048, 1152), ("forest4k", 2048, 1152), ("beach", 2048, 1152)]
    frames = []
    for fi in range(2):
        Y = np.zeros((H, W), np.uint16)
        Cb = np.zeros((H, W // 2), np.uint16)
        Cr = np.zeros((H, W // 2), np.uint16)
        srcs = {}
        for name, w, h in tiles:
            fs = read_yuv(os.path.join(MASTERS_DIR, f"{name}_422_10.yuv"), w, h, w // 2)
            srcs[name] = fs[min(fi, len(fs) - 1)]
        # 1:1 tiling, no rescale: cow top-left, fence below it, the 2K
        # sequences fill the right column and the bottom strip (cropped to fit).
        def put(name, x0, y0, cw_, ch_):
            sY, sCb, sCr = srcs[name]
            Y[y0:y0 + ch_, x0:x0 + cw_] = sY[:ch_, :cw_]
            Cb[y0:y0 + ch_, x0 // 2:(x0 + cw_) // 2] = sCb[:ch_, :cw_ // 2]
            Cr[y0:y0 + ch_, x0 // 2:(x0 + cw_) // 2] = sCr[:ch_, :cw_ // 2]
        put("cow", 0, 0, 4480, 3072)
        put("fence", 0, 3072, 4480, 1248)
        put("alpine", 4480, 0, 2048, 1152)
        put("city", 4480, 1152, 2048, 1152)
        put("forest4k", 4480, 2304, 2048, 1152)
        put("beach", 4480, 3456, 2048, 864)
        put("alpine", 6528, 0, 1152, 4320 // 1152 * 0 + 1152)  # corner: alpine crop
        put("city", 6528, 1152, 1152, 1152)
        put("forest4k", 6528, 2304, 1152, 1152)
        put("beach", 6528, 3456, 1152, 864)
        frames.append((Y, Cb, Cr))
    sp = os.path.join(OUT, "canvas8k.yuv")
    write_yuv(sp, frames)
    r = enc_dec(sp, W, H, 10, "canvas8k", frames=2)
    dec = read_yuv(r["dec"], W, H, W // 2)
    ps = [psnr_all(a, b) for a, b in zip(frames, dec)]
    RES["eightk"] = {"rt0": r["rt0"], "cbr_exact": r["cbr_exact"],
                     "slices_per_frame": H // 16,
                     "enc_s_per_frame": r["enc_s_per_frame"],
                     "dec_s_per_frame": r["dec_s_per_frame"],
                     "psnr_f0": {k: round(ps[0][k], 2) for k in ("Y", "Cb", "Cr")},
                     "psnr_f1": {k: round(ps[1][k], 2) for k in ("Y", "Cb", "Cr")}}
    print("8k", RES["eightk"], flush=True)
    for f in (sp, r["dec"], r["bs"], os.path.join(OUT, "canvas8k_rec.yuv")):
        os.unlink(f)


def main():
    os.makedirs(OUT, exist_ok=True)
    twelve_bit()
    pq_stress()
    eightk()
    with open(os.path.join(OUT, "hdr8k_results.json"), "w") as f:
        json.dump(RES, f, indent=1)
    print(json.dumps(RES, indent=1))


if __name__ == "__main__":
    main()
