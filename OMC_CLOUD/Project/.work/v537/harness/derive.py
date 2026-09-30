#!/usr/bin/env python3
"""derive.py -- make one test arm from a canonical 4:4:4/12-bit master.

  derive.py <master.yuv> <mW> <mH> <outW> <outH> <fmt 422|444> <depth 8|10|12>
            <nframes> <out.yuv>

Order of operations (chosen so nothing is resampled twice):
  1. raster change, if any, on the 4:4:4/12-bit planes:
       - down (1920x1080, 1280x720 from 3840x2160): ffmpeg Lanczos, all three
         planes identically (they are co-located at 4:4:4, so no siting
         question arises);
       - up to 7680x4320: 2x2 REPLICATION TILING of the native frame, not
         interpolation -- an 8K canvas of real 4K pixels, the same
         construction docs/REPORT.md 7 used, so the 8K arm carries genuine
         per-pixel statistics instead of a resampler's invented detail.
  2. chroma decimation to 4:2:2, if asked: horizontal pair average
     ((a+b+1)>>1), co-sited -- the convention BITSTREAM.md and the project's
     own prep use.
  3. depth: >> (12-depth).  Integer, deterministic.
"""
import sys, os, subprocess, numpy as np

def main():
    mas, mW, mH, oW, oH, fmt, depth, n, out = sys.argv[1:10]
    mW, mH, oW, oH, depth, n = int(mW), int(mH), int(oW), int(oH), int(depth), int(n)
    fw = mW*mH*3
    src = np.fromfile(mas, dtype='<u2', count=fw*n).reshape(n, 3, mH, mW)

    if (oW, oH) == (mW, mH):
        cur = src
    elif oW == mW*2 and oH == mH*2:
        cur = np.repeat(np.repeat(src, 2, axis=2), 2, axis=3)   # 2x2 tiling
    elif oW < mW:
        tmp = out + ".scale.tmp"
        p = subprocess.run(["ffmpeg","-v","error","-y","-f","rawvideo",
              "-pix_fmt","yuv444p12le","-s",f"{mW}x{mH}","-i",mas,
              "-frames:v",str(n),
              "-vf",f"scale={oW}:{oH}:flags=lanczos","-pix_fmt","yuv444p12le",
              "-f","rawvideo",tmp], check=True)
        cur = np.fromfile(tmp, dtype='<u2', count=oW*oH*3*n).reshape(n,3,oH,oW)
        os.unlink(tmp)
    else:
        sys.exit("unsupported raster change")

    sh = 12 - depth
    with open(out, "wb") as fo:
        for k in range(n):
            y = (cur[k,0] >> sh).astype('<u2')
            cb = cur[k,1].astype(np.int32); cr = cur[k,2].astype(np.int32)
            if fmt == "422":
                cb = (cb[:,0::2] + cb[:,1::2] + 1) >> 1
                cr = (cr[:,0::2] + cr[:,1::2] + 1) >> 1
            fo.write(y.tobytes())
            fo.write((cb >> sh).astype('<u2').tobytes())
            fo.write((cr >> sh).astype('<u2').tobytes())
    print(f"{out}: {n}f {oW}x{oH} {fmt}/{depth}b {os.path.getsize(out)} bytes")

if __name__ == "__main__":
    main()
