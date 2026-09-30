"""JPEG XS incumbent reference sweep (A1 baseline).

Encodes every master with SVT-JPEG-XS (isolated comparison instrument, not part of the
codec) across a CBR bpp ladder, decodes, and measures VMAF + per-plane PSNR against the
master. Output: xs_sweep.json in the masters dir.

The 1.0x "provisioned rate at service quality" per chroma config is then chosen as the
lowest sweep rate that holds service quality (VMAF at the self-score ceiling class,
healthy per-plane PSNR, artifact-free on review) across the corpus.

Run:  python3 harness/xs_sweep.py [--fmt 422|444] [--bpps 4.0,3.0,...]
"""

import argparse
import json
import os
import subprocess

from common import (MASTERS_DIR, SCRATCH, SEQUENCES, chroma_spread_tripwire,
                    psnr_all, read_yuv, run_vmaf, write_y4m)

SVT_BIN = os.path.join(SCRATCH, "SVT-JPEG-XS-main/Bin/Release")


def encode_decode_xs(name, w, h, fmt, bpp, workdir):
    src = os.path.join(MASTERS_DIR, f"{name}_{fmt}_10.yuv")
    bs = os.path.join(workdir, f"{name}_{fmt}_{bpp}.jxs")
    rec = os.path.join(workdir, f"{name}_{fmt}_{bpp}_rec.yuv")
    subprocess.run(
        [os.path.join(SVT_BIN, "SvtJpegxsEncApp"), "-i", src, "-b", bs,
         "-w", str(w), "-h", str(h), "--colour-format", f"yuv{fmt}",
         "--input-depth", "10", "--bpp", str(bpp), "--no-progress", "1", "-v", "1"],
        check=True, capture_output=True)
    subprocess.run(
        [os.path.join(SVT_BIN, "SvtJpegxsDecApp"), "-i", bs, "-o", rec, "-v", "1"],
        check=True, capture_output=True)
    bs_bytes = os.path.getsize(bs)
    return bs, rec, bs_bytes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fmt", default="422", choices=["422", "444"])
    ap.add_argument("--bpps", default="4.0,3.0,2.5,2.0,1.5,1.25,1.0,0.75")
    args = ap.parse_args()
    fmt = args.fmt
    bpps = [float(x) for x in args.bpps.split(",")]

    with open(os.path.join(MASTERS_DIR, "manifest.json")) as f:
        manifest = json.load(f)

    workdir = os.path.join(SCRATCH, "xs_sweep")
    os.makedirs(workdir, exist_ok=True)
    out_path = os.path.join(MASTERS_DIR, f"xs_sweep_{fmt}.json")
    results = {}
    if os.path.exists(out_path):
        with open(out_path) as f:
            results = json.load(f)

    for name in SEQUENCES:
        w, h = manifest[name]["w"], manifest[name]["h"]
        cw = w // 2 if fmt == "422" else w
        ref_y4m = os.path.join(MASTERS_DIR, f"{name}_{fmt}_10.y4m")
        ref_frames = read_yuv(os.path.join(MASTERS_DIR, f"{name}_{fmt}_10.yuv"), w, h, cw)
        results.setdefault(name, {})
        for bpp in bpps:
            key = str(bpp)
            if key in results[name]:
                continue
            bs, rec, nbytes = encode_decode_xs(name, w, h, fmt, bpp, workdir)
            rec_frames = read_yuv(rec, w, h, cw)
            rec_y4m = rec + ".y4m"
            write_y4m(rec_y4m, rec_frames, fmt=fmt, bits=10)
            vmaf = run_vmaf(ref_y4m, rec_y4m)
            per_frame = [psnr_all(r, d) for r, d in zip(ref_frames, rec_frames)]
            trip = [chroma_spread_tripwire(r, d) for r, d in zip(ref_frames, rec_frames)]
            nfr = len(rec_frames)
            bits_per_frame = nbytes * 8 / nfr
            results[name][key] = {
                "bpp_requested": bpp,
                "bits_per_frame": bits_per_frame,
                "bpp_actual": bits_per_frame / (w * h),
                "vmaf_min": vmaf["min"], "vmaf_frames": vmaf["frames"],
                "psnr_frames": per_frame,
                "worst_psnr": {p: min(fr[p] for fr in per_frame) for p in ("Y", "Cb", "Cr")},
                "sat_ratio_min": min(t["sat_ratio"] for t in trip),
            }
            os.unlink(rec)
            os.unlink(rec_y4m)
            v = results[name][key]
            print(f"{name} {fmt} bpp={bpp}: vmaf_min={v['vmaf_min']:.2f} "
                  f"PSNR Y/Cb/Cr={v['worst_psnr']['Y']:.2f}/{v['worst_psnr']['Cb']:.2f}/"
                  f"{v['worst_psnr']['Cr']:.2f} actual_bpp={v['bpp_actual']:.3f}", flush=True)
            with open(out_path, "w") as f:
                json.dump(results, f, indent=2)

    print("wrote", out_path)


if __name__ == "__main__":
    main()
