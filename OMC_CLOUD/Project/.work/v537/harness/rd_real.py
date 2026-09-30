"""Rev. 5 curve measurement on real captured frames: OMC @ R vs JPEG XS @ 2R.

For every corpus scene (real ProRes-master frames, 4:2:2 10-bit), sweep both
codecs across rate and score per-plane PSNR on:
  - frame 0  (cold intra -- the worst-frame case), and
  - the last frame (after the scene's 1-2 GENUINE captured temporal steps --
    the only real-motion prediction steps this corpus contains).

The rev. 5 test is always OMC @ R against XS @ 2R. VMAF is deliberately not
used: it saturates (ceiling ~97.4) in this operating region and cannot
discriminate (Team A evaluation, 2026-07-27).

Output: rd_real.json in SCRATCH + a printed OMC@R-vs-XS@2R table.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import MASTERS_DIR, SCRATCH, read_yuv, psnr_all

XS_BIN = os.path.join(SCRATCH, "SVT-JPEG-XS-main/Bin/Release")

SCENES = [
    ("cow", 4480, 3072), ("fence", 4480, 1856), ("alpine", 2048, 1152),
    ("city", 2048, 1152), ("forest4k", 2048, 1152), ("beach", 2048, 1152),
    ("couch12", 1920, 1056),
]
OMC_RATES = [0.5, 0.75, 1.0, 1.5, 2.0, 3.0]
XS_RATES = [1.0, 1.5, 2.0, 3.0, 4.0, 6.0]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP = os.path.join(SCRATCH, "rdreal")


def run_omc(src, w, h, bpp, out_yuv):
    bs = os.path.join(TMP, "a.omc")
    subprocess.run([os.path.join(ROOT, "omc_enc"), "-i", src, "-o", bs,
                    "-w", str(w), "-h", str(h), "--fmt", "422",
                    "--bpp", f"{bpp}"], check=True, capture_output=True)
    subprocess.run([os.path.join(ROOT, "omc_dec"), "-i", bs, "-o", out_yuv],
                   check=True, capture_output=True)


def run_xs(src, w, h, bpp, out_yuv):
    bs = os.path.join(TMP, "a.jxs")
    subprocess.run([os.path.join(XS_BIN, "SvtJpegxsEncApp"), "-i", src, "-b", bs,
                    "-w", str(w), "-h", str(h), "--colour-format", "yuv422",
                    "--input-depth", "10", "--bpp", f"{bpp}",
                    "--no-progress", "1", "-v", "1"], check=True, capture_output=True)
    subprocess.run([os.path.join(XS_BIN, "SvtJpegxsDecApp"), "-i", bs,
                    "-o", out_yuv, "-v", "1"], check=True, capture_output=True)


def main():
    os.makedirs(TMP, exist_ok=True)
    res = {}
    for name, w, h in SCENES:
        src = os.path.join(MASTERS_DIR, f"{name}_422_10.yuv")
        frames = read_yuv(src, w, h, w // 2)
        last = len(frames) - 1
        res[name] = {"frames": len(frames), "omc": {}, "xs": {}}
        for codec, rates, runner in (("omc", OMC_RATES, run_omc),
                                     ("xs", XS_RATES, run_xs)):
            for bpp in rates:
                dec_p = os.path.join(TMP, "dec.yuv")
                runner(src, w, h, bpp, dec_p)
                dec = read_yuv(dec_p, w, h, w // 2)
                res[name][codec][f"{bpp}"] = {
                    "f0": {k: round(v, 2) for k, v in psnr_all(frames[0], dec[0]).items()},
                    "flast": {k: round(v, 2) for k, v in psnr_all(frames[last], dec[last]).items()},
                }
                print(name, codec, bpp, res[name][codec][f"{bpp}"]["flast"], flush=True)
    with open(os.path.join(SCRATCH, "rd_real.json"), "w") as f:
        json.dump(res, f, indent=1)

    print("\n=== rev. 5 test: OMC @ R vs XS @ 2R (luma PSNR dB, steady/last frame) ===")
    print(f"{'scene':10s}" + "".join(f"  R={r:<4}" for r in [0.5, 0.75, 1.0, 1.5, 2.0, 3.0]))
    for name, _, _ in SCENES:
        row = f"{name:10s}"
        for r in [0.5, 0.75, 1.0, 1.5, 2.0, 3.0]:
            o = res[name]["omc"][f"{r}"]["flast"]["Y"]
            x = res[name]["xs"][f"{2*r}"]["flast"]["Y"]
            row += f"  {o - x:+5.1f}"
        print(row + "   (OMC@R minus XS@2R; goal: >= 0)")


if __name__ == "__main__":
    main()
