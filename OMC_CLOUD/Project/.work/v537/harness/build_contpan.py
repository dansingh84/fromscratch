"""Build the continuous-pan review sequences (no repeats, every frame unique).

Two 256-frame, 50 fps, 1920x1056 sequences windowed over a single capture:
  fencecont: fence capture 0, y=400, x = 300 + 6*i  (6 px/frame, 1530 px travel)
  cowcont:   cow   capture 0, y=900, x = 600 + 4*i  (4 px/frame, 1020 px travel)

Same trajectories/anchors as the program-feed pan shots, extended to 5.12 s of
genuinely continuous motion. Usage: build_contpan.py <fencecont|cowcont> <out.yuv>
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import MASTERS_DIR, read_yuv, write_yuv

W, H, N = 1920, 1056, 256

def window(frame, x0, y0):
    Y, Cb, Cr = frame
    return (Y[y0:y0+H, x0:x0+W].copy(),
            Cb[y0:y0+H, x0//2:(x0+W)//2].copy(),
            Cr[y0:y0+H, x0//2:(x0+W)//2].copy())

def main(which, out):
    if which == 'fencecont':
        m = read_yuv(os.path.join(MASTERS_DIR,'fence_422_10.yuv'),4480,1856,2240)[0]
        frames = [window(m, 300+6*i, 400) for i in range(N)]
    elif which == 'cowcont':
        m = read_yuv(os.path.join(MASTERS_DIR,'cow_422_10.yuv'),4480,3072,2240)[0]
        frames = [window(m, 600+4*i, 900) for i in range(N)]
    else:
        raise SystemExit('unknown sequence '+which)
    write_yuv(out, frames)
    print(which, len(frames), 'frames ->', out)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
