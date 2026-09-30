"""Build the 64-frame program feed (v2) from the customer masters.

4 shots x 16 frames, 1920x1056, 3 hard cuts:
  S1 beach    static ping-pong of the genuinely captured beach frames
              (every frame-to-frame delta is a real camera delta with grain)
  S2 couch    static ping-pong of the captured couch12 frames (dim interior)
  S3 fencepan 6 px/frame window pan over fence capture 0 (single frame -
              a true rigid pan)
  S4 cowpan   4 px/frame window pan over cow capture 0 (single frame)

v2 change (construction fix, found in customer review of v1): the v1 pan shots
cycled through the master's separate captures while panning to keep fresh grain
per frame - but the subjects moved between those captures (they are stills
seconds apart, not adjacent video frames), so the subject pose strobed at frame
rate. That flicker was source material, faithfully reproduced by every codec
under test. v2 pans window a SINGLE capture: deltas are pure rigid shifts, the
pose is stable, and fresh-grain-per-frame stress remains covered by S1/S2
(whose ping-pong deltas ARE real camera deltas).

Run: python3 harness/build_program.py   (writes program.yuv, program.y4m,
                                         program_labels.json in SCRATCH)
"""

import json
import os

from common import MASTERS_DIR, SCRATCH, read_yuv, write_y4m, write_yuv

W, H = 1920, 1056


def window(frame, x0, y0):
    Y, Cb, Cr = frame
    return (Y[y0:y0 + H, x0:x0 + W].copy(),
            Cb[y0:y0 + H, x0 // 2:(x0 + W) // 2].copy(),
            Cr[y0:y0 + H, x0 // 2:(x0 + W) // 2].copy())


def main():
    beach = read_yuv(os.path.join(MASTERS_DIR, "beach_422_10.yuv"), 2048, 1152, 1024)
    couch = read_yuv(os.path.join(MASTERS_DIR, "couch12_422_10.yuv"), 1920, 1056, 960)
    fence = read_yuv(os.path.join(MASTERS_DIR, "fence_422_10.yuv"), 4480, 1856, 2240)
    cow = read_yuv(os.path.join(MASTERS_DIR, "cow_422_10.yuv"), 4480, 3072, 2240)

    frames, labels = [], []
    # S1 beach: ping-pong the captures, fixed window
    bw = [window(f, 64, 48) for f in beach]
    seq = (bw + bw[-2:0:-1]) if len(bw) > 2 else bw   # 0,1,2,1 cycle
    for i in range(16):
        frames.append(seq[i % len(seq)])
        labels.append(f"S1.beach.{i}")
    # S2 couch: full-frame ping-pong
    seq = (couch + couch[-2:0:-1]) if len(couch) > 2 else couch
    for i in range(16):
        frames.append(seq[i % len(seq)])
        labels.append(f"S2.couch.{i}")
    # S3 fencepan: 6 px/frame rigid pan over capture 0 (v1 trajectory kept)
    for i in range(16):
        frames.append(window(fence[0], 300 + 6 * i, 400))
        labels.append(f"S3.fencepan.{i}")
    # S4 cowpan: 4 px/frame rigid pan over capture 0 (v1 trajectory kept)
    for i in range(16):
        frames.append(window(cow[0], 600 + 4 * i, 900))
        labels.append(f"S4.cowpan.{i}")

    write_yuv(os.path.join(SCRATCH, "program.yuv"), frames)
    write_y4m(os.path.join(SCRATCH, "program.y4m"), frames, fps=(50, 1))
    with open(os.path.join(SCRATCH, "program_labels.json"), "w") as f:
        json.dump({"version": 2, "note": "v2: pans window a single capture "
                   "(v1 cycled captures and strobed the subject pose)",
                   "labels": labels}, f, indent=1)
    print("program v2 written:", len(frames), "frames")


if __name__ == "__main__":
    main()
