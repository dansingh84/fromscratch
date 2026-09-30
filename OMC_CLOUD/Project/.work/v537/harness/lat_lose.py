#!/usr/bin/env python3
"""[A5-LOSE] Correct single-slice loss injection.

`omc_dec --lose f:s` zeroes `[s*slice_bytes, (s+1)*slice_bytes)` of the frame --
a FIXED stride.  Slices are VARIABLE length on the wire (48 + ceil(used_bits/8)),
so that window is not the named slice.  Measured on dng/fbgame 1080p @1.0:
slice 34 truly spans [128659,132179) while the probe zeroes [130560,134400),
straddling slices 34 AND 35 -- and `--lose "4:34"` ends up damaging 12 slices
across 7 frames instead of 1 slice in 1 frame.

This walks each frame's true slice extents from the headers' own used_bits and
zeroes exactly the named slice, preserving file length so nothing downstream
shifts.

Multiple slices must be zeroed in ONE walk: once a slice is zeroed its header
is gone, so a second pass cannot traverse past it ("lost sync walking to slice
N").  Chaining two invocations fails, and if the caller does not check the exit
status the stale output file is silently re-used -- which produced two void rows
in my own first run of this.

usage: lat_lose.py in.omc out.omc frame slice[,slice...]
"""
import sys

src, dst, F = sys.argv[1], sys.argv[2], int(sys.argv[3])
SLICES = sorted(int(x) for x in sys.argv[4].split(","))
raw = bytearray(open(src, "rb").read())
assert int.from_bytes(raw[:4], "little") == 0x4F4D4331, "not an OMC stream"
H = int.from_bytes(raw[8:10], "little"); slice_h = raw[12]
slice_bytes = int.from_bytes(raw[21:25], "little") // 8
nsl = H // slice_h
frame_bytes = slice_bytes * nsl

class BR:
    def __init__(s, b): s.b = b; s.p = 0
    def u(s, n):
        v = 0
        for i in range(n):
            v |= ((s.b[(s.p + i) >> 3] >> ((s.p + i) & 7)) & 1) << i
        s.p += n
        return v

base = 32 + F * frame_bytes
if base + frame_bytes > len(raw):
    sys.exit("frame %d is beyond the stream" % F)
# walk the UNDAMAGED stream once, recording every extent, then zero
extents = []
o = base
for s in range(nsl):
    r = BR(raw[o:o + 48])
    if r.u(32) != 0x4F4D5331:
        sys.exit("lost sync walking to slice %d (frame %d)" % (s, F))
    r.u(8); r.u(16); r.u(4); r.u(2); r.u(8); r.u(16)
    ln = 48 + (r.u(24) + 7) // 8
    extents.append((o, ln))
    o += ln
for S in SLICES:
    if S >= nsl: sys.exit("slice %d beyond %d" % (S, nsl))
    o, ln = extents[S]
    raw[o:o + ln] = b"\x00" * ln
    print("zeroed frame %d slice %d: frame bytes [%d,%d) len %d "
          "(fixed-stride probe would zero [%d,%d))"
          % (F, S, o - base, o - base + ln, ln, S * slice_bytes, (S + 1) * slice_bytes))
open(dst, "wb").write(bytes(raw))
