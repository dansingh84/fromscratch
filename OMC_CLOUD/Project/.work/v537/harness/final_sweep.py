#!/usr/bin/env python3
"""Final mandate sweep: OMC2 @ R vs fair JPEG XS @ 2R, all footage classes.

- XS always runs with --coding-signs 2 --coding-vpred 2 --quantization 1 (fair).
- OMC2 default config (= v4.2 + F-1 + F-3), deadzone ON (OMC_DZ=1), fill ON
  (perception mode) + no-fill diagnostic at the 2.0 anchor.
- Worst-steady accounting: frames 0-1 excluded (rev.3 ramp), per-plane PSNR.
- CBR audit: stream size == 32 + nframes * F.
Writes JSON to final_sweep.json and prints a table.
"""
import json, os, subprocess, sys
import numpy as np

W_ = os.path.dirname(os.path.abspath(__file__))
OMC_ENC = os.path.join(W_, "../omc2/omc_enc")
OMC_DEC = os.path.join(W_, "../omc2/omc_dec")
XS = os.path.join(W_, "../svtjxs_build/SVT-JPEG-XS-main/Bin/Release")
FT = os.path.join(W_, "../test_footage")

# name, src, W, H, fmt(422/444), depth, nframes, ffmpeg-extra
CLIPS = [
    ("beach",    f"{FT}/prores_footage/beach.mov",              2048, 1152, 422, 10, 24, []),
    ("heli",     f"{FT}/prores_footage/alpine_helicopter.mov",  2048, 1152, 422, 10, 24, []),
    ("aerial",   f"{FT}/prores_footage/city_aerial.mov",        2048, 1152, 422, 10, 24, []),
    ("trees",    f"{FT}/prores_footage/trees.mov",              4096, 2160, 422, 10, 16, []),
    ("soccer",   f"{FT}/soccer_footage_not_uncompressed/long_clip.mkv", 3840, 2160, 422, 10, 12, []),
    ("soccgfx",  f"{FT}/soccer_footage_not_uncompressed/long_clip_w_gfx.mkv", 3840, 2160, 422, 10, 12, []),
    ("confetti", f"{FT}/more_test_videos/confetti.mkv",         3840, 2160, 422, 10, 12, ["-ss", "3"]),
    ("talking",  f"{FT}/more_test_videos/talkinghead.mp4",      1280,  720, 422, 10, 24, ["-ss", "30"]),
    ("graincell",f"{FT}/more_test_videos/cell_phone_footage_grainy.mp4", 1920, 1080, 422, 10, 24, []),
    ("couch",    f"{FT}/prores_footage/couch_dark_with_movement.mov", 1920, 1080, 444, 12, 16, []),
    ("manwalk",  f"{FT}/prores_footage/man_walking.mxf",        3840, 2160, 444, 12, 10, []),
    ("mms",      f"{FT}/prores_footage/m&ms_flying.mov",        4480, 1856, 444, 12, 10, []),
    ("water",    f"{FT}/prores_footage/water_by_dam.mxf",       3840, 1608, 444, 12, 10, []),
    ("cow",      f"{FT}/prores_footage/cow.mxf",                4480, 3096, 444, 12,  8, []),
    ("8k",       f"{FT}/soccer_footage_not_uncompressed/short_clip.mkv", 7680, 4320, 422, 10, 6, ["-ss", "4"]),
]
# (OMC_R, XS_2R) anchor pairs
PAIRS = [(1.0, 2.0), (2.0, 4.0)]
LOW_PAIR_CLIPS = {"beach", "heli", "aerial", "talking", "graincell", "couch"}  # add 0.5 vs 1.0

def run(cmd, env=None):
    e = dict(os.environ)
    if env: e.update(env)
    r = subprocess.run(cmd, capture_output=True, env=e)
    if r.returncode != 0:
        raise RuntimeError(f"cmd failed: {' '.join(cmd)}\n{r.stderr.decode()[-500:]}")
    return r

def extract(name, src, W, H, fmt, depth, n, extra):
    pix = f"yuv{fmt}p{depth}le"
    out = os.path.join(W_, f"m_{name}.yuv")
    if not os.path.exists(out):
        run(["ffmpeg", "-y", "-loglevel", "error"] + extra +
            ["-i", src, "-frames:v", str(n), "-pix_fmt", pix, "-f", "rawvideo", out])
    return out

def psnr_frames(ref, dec, W, H, fmt, depth):
    cw = W // 2 if fmt == 422 else W
    fw = W * H + 2 * cw * H
    peak = float((1 << depth) - 1)
    a = np.fromfile(ref, dtype="<u2"); b = np.fromfile(dec, dtype="<u2")
    n = min(len(a), len(b)) // fw
    out = []
    for f in range(n):
        fa = a[f*fw:(f+1)*fw].astype(np.float64); fb = b[f*fw:(f+1)*fw].astype(np.float64)
        planes = [(0, W*H), (W*H, W*H+cw*H), (W*H+cw*H, fw)]
        ps = []
        for (s0, s1) in planes:
            mse = np.mean((fa[s0:s1]-fb[s0:s1])**2)
            ps.append(99.0 if mse == 0 else 10*np.log10(peak*peak/mse))
        out.append(ps)
    return out

def worst_steady(pf):
    ss = pf[2:] if len(pf) > 2 else pf
    return [round(min(p[i] for p in ss), 2) for i in range(3)]

def main():
    only = os.environ.get("CLIPS_ONLY")
    results = {}
    outp = os.path.join(W_, os.environ.get("OUT_JSON", "final_sweep.json"))
    if os.path.exists(outp):
        results = json.load(open(outp))
    for (name, src, W, H, fmt, depth, n, extra) in CLIPS:
        if only and name not in only.split(","):
            continue
        try:
            raw = extract(name, src, W, H, fmt, depth, n, extra)
        except Exception as ex:
            print(f"{name}: extract FAILED {ex}", flush=True); continue
        results.setdefault(name, {})
        pairs = PAIRS + ([(0.5, 1.0)] if name in LOW_PAIR_CLIPS else [])
        for (r_omc, r_xs) in pairs:
            key = f"{r_omc}v{r_xs}"
            if key in results[name]: continue
            entry = {}
            try:
                # --- OMC2 perception (fill on), deadzone on ---
                bs, dec = f"{W_}/t_{name}.omc", f"{W_}/t_{name}_dec.yuv"
                run([OMC_ENC, "-i", raw, "-o", bs, "-w", str(W), "-h", str(H),
                     "--fmt", str(fmt), "--depth", str(depth), "--bpp", str(r_omc)],
                    env={"OMC_DZ": "1"})
                # CBR audit
                sz = os.path.getsize(bs)
                run([OMC_DEC, "-i", bs, "-o", dec])
                pf = psnr_frames(raw, dec, W, H, fmt, depth)
                nf = len(pf)
                F = (sz - 32) // nf
                entry["omc_cbr_exact"] = (sz == 32 + nf * F)
                entry["omc_bpp"] = round(F * 8 / (W * H), 4)
                entry["omc_ws"] = worst_steady(pf)
                # no-fill diagnostic at the 2.0 anchor
                if r_omc == 2.0:
                    run([OMC_ENC, "-i", raw, "-o", bs, "-w", str(W), "-h", str(H),
                         "--fmt", str(fmt), "--depth", str(depth), "--bpp", str(r_omc),
                         "--no-fill"], env={"OMC_DZ": "1"})
                    run([OMC_DEC, "-i", bs, "-o", dec])
                    entry["omc_nofill_ws"] = worst_steady(psnr_frames(raw, dec, W, H, fmt, depth))
                # --- fair XS at 2R ---
                xbs, xdec = f"{W_}/t_{name}.jxs", f"{W_}/t_{name}_xdec.yuv"
                run([f"{XS}/SvtJpegxsEncApp", "-i", raw, "-w", str(W), "-h", str(H),
                     "--colour-format", f"yuv{fmt}", "--input-depth", str(depth),
                     "--bpp", str(r_xs), "--coding-signs", "2", "--coding-vpred", "2",
                     "--quantization", "1", "-b", xbs, "--no-progress", "1"])
                run([f"{XS}/SvtJpegxsDecApp", "-i", xbs, "-o", xdec])
                entry["xs_ws"] = worst_steady(psnr_frames(raw, xdec, W, H, fmt, depth))
                entry["dY"] = round(entry["omc_ws"][0] - entry["xs_ws"][0], 2)
                for f_ in (bs, dec, xbs, xdec):
                    if os.path.exists(f_): os.unlink(f_)
            except Exception as ex:
                entry["error"] = str(ex)[:300]
            results[name][key] = entry
            json.dump(results, open(outp, "w"), indent=1)
            print(f"{name} {key}: {json.dumps(entry)}", flush=True)
    # summary table
    print("\n=== OMC2@R vs fair-XS@2R, worst-steady luma delta (dY, dB) ===")
    for name in results:
        row = f"{name:10s}"
        for key in ("0.5v1.0", "1.0v2.0", "2.0v4.0"):
            e = results[name].get(key, {})
            row += f"  {key}: {e.get('dY', '—'):>6}"
        print(row)

if __name__ == "__main__":
    main()
