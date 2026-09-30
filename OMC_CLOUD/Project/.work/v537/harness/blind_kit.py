#!/usr/bin/env python3
"""Build the rev.6 blind viewing kit: sealed A/B pairs, OMC2 @ R vs fair
JPEG XS @ 2R, lossless-wrapped for playback (x264 lossless for 10-bit 4:2:2,
FFV1 for 12-bit 4:4:4). Randomized A/B per pair; key sealed in KEY.b64.

usage: blind_kit.py <clip> [corr]
clips are added incrementally; kit lives in blind_kit/.
"""
import base64, json, os, random, subprocess, sys

W_ = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.join(W_, "blind_kit")
XS = os.path.join(W_, "../svtjxs_build/SVT-JPEG-XS-main/Bin/Release")
CLIPS = {
    "beach":  (2048, 1152, 422, 10, "m_beach.yuv", 24),
    "cow":    (4480, 3096, 444, 12, "m_cow.yuv", 8),
    "heli":   (2048, 1152, 422, 10, "m_heli.yuv", 24),
    "aerial": (2048, 1152, 422, 10, "m_aerial.yuv", 24),
    "confetti": (3840, 2160, 422, 10, "m8_confetti.yuv", 8),
    "couch":  (1920, 1080, 444, 12, "m_couch.yuv", 16),
}
PAIR = (2.0, 4.0)  # default; override per-run: blind_kit.py <clip> [corr] [Romc Rxs]

def run(cmd, env=None):
    e = dict(os.environ); e.update(env or {})
    r = subprocess.run(cmd, capture_output=True, env=e)
    assert r.returncode == 0, (cmd, r.stderr.decode()[-300:])

def wrap(raw, out, W, H, fmt, depth, n):
    """Lossless wrap with PER-FILE structural variation so a decode shared by
    two rungs never ships as identical bytes (the unblinding defect the first
    kit build of this project had - do not reintroduce)."""
    pix = f"yuv{fmt}p{depth}le"
    v = (hash(os.path.basename(out)) & 3)
    if fmt == 422 and depth == 10:
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", pix,
             "-s", f"{W}x{H}", "-r", "25", "-i", raw, "-frames:v", str(n),
             "-c:v", "libx264", "-qp", "0", "-preset", "veryfast",
             "-x264-params", f"slices={2 + v}", "-metadata", f"title=v{v}",
             "-pix_fmt", pix, out + ".mkv"])
    else:
        run(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", pix,
             "-s", f"{W}x{H}", "-r", "25", "-i", raw, "-frames:v", str(n),
             "-c:v", "ffv1", "-level", "3", "-slices", str((4, 6, 9, 12)[v]),
             "-metadata", f"title=v{v}", out + ".mkv"])

def main():
    clip = sys.argv[1]
    corr = "corr" in sys.argv[2:]
    nums = [a for a in sys.argv[2:] if a not in ("corr",)]
    global PAIR
    if len(nums) == 2: PAIR = (float(nums[0]), float(nums[1]))
    W, H, fmt, depth, src, n = CLIPS[clip]
    os.makedirs(KIT, exist_ok=True)
    keyp = os.path.join(KIT, "key.json")
    key = json.load(open(keyp)) if os.path.exists(keyp) else {}
    r_omc, r_xs = PAIR
    tag = f"{clip}_R{int(r_omc*10):02d}v{int(r_xs*10):02d}" + ("_corr" if corr else "")
    # encode OMC
    args = ["../omc2/omc_enc", "-i", src, "-o", "bk.omc", "-w", str(W), "-h", str(H),
            "--fmt", str(fmt), "--depth", str(depth), "--bpp", str(r_omc)]
    if corr: args += ["--grain-replace", "--grain-corr"]
    run(args)
    run(["../omc2/omc_dec", "-i", "bk.omc", "-o", "bk_omc.yuv"])
    # encode fair XS
    run([f"{XS}/SvtJpegxsEncApp", "-i", src, "-w", str(W), "-h", str(H),
         "--colour-format", f"yuv{fmt}", "--input-depth", str(depth),
         "--bpp", str(r_xs), "--coding-signs", "2", "--coding-vpred", "2",
         "--quantization", "1", "-b", "bk.jxs", "--no-progress", "1"])
    run([f"{XS}/SvtJpegxsDecApp", "-i", "bk.jxs", "-o", "bk_xs.yuv"])
    # randomized A/B
    rng = random.Random(hash(tag) & 0xffffffff)
    omc_is_a = rng.random() < 0.5
    a_src, b_src = ("bk_omc.yuv", "bk_xs.yuv") if omc_is_a else ("bk_xs.yuv", "bk_omc.yuv")
    wrap(a_src, os.path.join(KIT, f"{tag}_A"), W, H, fmt, depth, n)
    wrap(b_src, os.path.join(KIT, f"{tag}_B"), W, H, fmt, depth, n)
    key[tag] = {"A": "OMC" if omc_is_a else "XS", "B": "XS" if omc_is_a else "OMC",
                "omc_bpp": r_omc, "xs_bpp": r_xs, "grain_corr": corr}
    json.dump(key, open(keyp, "w"), indent=1)
    open(os.path.join(KIT, "KEY.b64"), "w").write(
        base64.b64encode(json.dumps(key).encode()).decode())
    for f in ("bk.omc", "bk.jxs", "bk_omc.yuv", "bk_xs.yuv"):
        if os.path.exists(f): os.unlink(f)
    print(f"{tag}: pair written ({'OMC=A' if omc_is_a else 'OMC=B'} sealed)")

if __name__ == "__main__":
    main()
