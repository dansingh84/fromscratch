"""Evaluate the OMC-1 C codec on the corpus: encode at target bpp, verify rt=0,
measure VMAF + per-plane PSNR + chroma tripwire. Prints a table and writes
omc_eval_{fmt}.json next to the masters.

Run: python3 harness/eval_omc.py [--fmt 422|444] [--bpp 2.0] [--seqs a,b,...]
"""

import argparse
import json
import os
import subprocess

from common import (MASTERS_DIR, SCRATCH, SEQUENCES, chroma_spread_tripwire,
                    psnr_all, read_yuv, run_vmaf, ssim_plane, write_y4m)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(SCRATCH, "omc_out")


def run(cmd):
    subprocess.run(cmd, check=True, capture_output=True)


def eval_seq(name, w, h, fmt, bpp, keep=False):
    cw = w // 2 if fmt == "422" else w
    src = os.path.join(MASTERS_DIR, f"{name}_{fmt}_10.yuv")
    bs = os.path.join(OUT, f"{name}_{fmt}.omc")
    recy = os.path.join(OUT, f"{name}_{fmt}_rec.yuv")
    decy = os.path.join(OUT, f"{name}_{fmt}_dec.yuv")
    run([os.path.join(REPO, "omc_enc"), "-i", src, "-o", bs, "-w", str(w),
         "-h", str(h), "--fmt", fmt, "--bpp", str(bpp), "--recon", recy])
    run([os.path.join(REPO, "omc_dec"), "-i", bs, "-o", decy])
    with open(recy, "rb") as a, open(decy, "rb") as b:
        rt0 = a.read() == b.read()
    ref = read_yuv(src, w, h, cw)
    dec = read_yuv(decy, w, h, cw)
    dec_y4m = decy + ".y4m"
    write_y4m(dec_y4m, dec, fmt=fmt, bits=10)
    vmaf = run_vmaf(os.path.join(MASTERS_DIR, f"{name}_{fmt}_10.y4m"), dec_y4m)
    per = [psnr_all(r, d) for r, d in zip(ref, dec)]
    trip = [chroma_spread_tripwire(r, d) for r, d in zip(ref, dec)]
    ssim = min(ssim_plane(r[0], d[0]) for r, d in zip(ref, dec))
    # exact worst-frame bits from the stream layout (CBR: all frames equal)
    hdr = 32
    stream_bytes = os.path.getsize(bs) - hdr
    bits_frame = stream_bytes * 8 // len(ref)
    res = {
        "rt0": rt0,
        "bpp": bits_frame / (w * h),
        "vmaf_min": vmaf["min"],
        "vmaf_frames": vmaf["frames"],
        "worst_psnr": {p: min(fr[p] for fr in per) for p in ("Y", "Cb", "Cr")},
        "ssim_min": ssim,
        "sat_ratio_min": min(t["sat_ratio"] for t in trip),
        "spread_max": max(t["dPSNR_spread"] for t in trip),
    }
    if not keep:
        for f in (recy, decy, dec_y4m):
            os.unlink(f)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fmt", default="422", choices=["422", "444"])
    ap.add_argument("--bpp", type=float, default=2.0)
    ap.add_argument("--seqs", default=",".join(SEQUENCES))
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--tag", default="")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(MASTERS_DIR, "manifest.json")) as f:
        mani = json.load(f)
    results = {}
    for name in args.seqs.split(","):
        w, h = mani[name]["w"], mani[name]["h"]
        r = eval_seq(name, w, h, args.fmt, args.bpp, keep=args.keep)
        results[name] = r
        print(f"{name:9s} {args.fmt} bpp={r['bpp']:.3f} rt0={'PASS' if r['rt0'] else 'FAIL'} "
              f"vmaf_min={r['vmaf_min']:.2f} PSNR Y/Cb/Cr="
              f"{r['worst_psnr']['Y']:.2f}/{r['worst_psnr']['Cb']:.2f}/{r['worst_psnr']['Cr']:.2f} "
              f"ssim={r['ssim_min']:.4f} sat={r['sat_ratio_min']:.3f}", flush=True)
    out = os.path.join(MASTERS_DIR, f"omc_eval_{args.fmt}{args.tag}.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print("wrote", out)


if __name__ == "__main__":
    main()
