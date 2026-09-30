#!/usr/bin/env python3
"""prep_master.py -- build the CANONICAL master for one clip.

The canonical master is planar Y'CbCr 4:4:4, BT.709 limited range, 12-bit,
u16 LE, frame-sequential, at the clip's native raster.  Every arm of the
battery is derived from it by integer-only operations plus (for the smaller
rasters) one Lanczos scale, so no arm resamples twice.

  DNG source: rawpy demosaic (AHD, camera WB, no auto-bright, Rec.709
              transfer + sRGB/709 primaries, 16-bit) -> RGB48 -> BT.709
              limited-range Y'CbCr at 12 bits.
  YUV source: planar 4:2:0 10-bit -> chroma upsampled to 4:4:4 (bilinear,
              co-sited horizontally, centre-sited vertically per BT.601/709
              4:2:0 siting) -> <<2 to 12 bits.  Documented as interpolation:
              the 4:4:4 chroma of a 4:2:0 source is reconstructed, not
              captured.

  YUV444/16 source: planar 4:4:4 16-bit -> 12 bits by ROUND-HALF-UP,
              (x + 8) >> 4, clamped to [0, 4095].  NOT truncation: a plain
              >>4 biases every sample down by half a step, and a master that
              every arm is derived from must not carry a DC bias.  NOT dither:
              that would put noise into the master.  Matches the intent of the
              dng path's np.rint while staying integer-only.  Approved by the
              coordinator 2026-09-05 (MEMO 012 5.2).  The source clips are
              genuinely 16-bit -- verified 44,389 distinct luma values in one
              frame, median spacing 1, 6.2 % of samples divisible by 16 against
              6.25 % by chance -- so this is a real precision reduction, not
              the removal of padding bits.

usage: prep_master.py dng     <dir-with-frame%06d.dng> <nframes> <out.yuv>
       prep_master.py yuv420  <in.yuv> <W> <H> <depth> <nframes> <out.yuv>
       prep_master.py yuv444_16 <in.yuv> <W> <H> <first_frame> <nframes> <out.yuv>
"""
import sys, os, numpy as np

KR, KB = 0.2126, 0.0722
KG = 1.0 - KR - KB

def rgb_to_ycbcr444(r, g, b, depth):
    """r,g,b float64 in [0,1]. -> limited-range Y'CbCr u16 at `depth`."""
    y  = KR*r + KG*g + KB*b
    cb = (b - y) / (2*(1-KB))
    cr = (r - y) / (2*(1-KR))
    d8 = depth - 8
    maxv = (1 << depth) - 1
    ys  = np.clip(np.rint(y  * (219 << d8) + (16  << d8)), 0, maxv)
    cbs = np.clip(np.rint(cb * (224 << d8) + (128 << d8)), 0, maxv)
    crs = np.clip(np.rint(cr * (224 << d8) + (128 << d8)), 0, maxv)
    return ys.astype('<u2'), cbs.astype('<u2'), crs.astype('<u2')

def do_dng(d, n, out):
    import rawpy
    PP = dict(use_camera_wb=True, no_auto_bright=True, output_bps=16,
              gamma=(2.222, 4.5), user_flip=0,
              demosaic_algorithm=rawpy.DemosaicAlgorithm.AHD,
              output_color=rawpy.ColorSpace.sRGB)   # sRGB primaries == BT.709
    with open(out, "wb") as fo:
        for i in range(n):
            p = os.path.join(d, "frame%06d.dng" % i)
            with rawpy.imread(p) as raw:
                a = raw.postprocess(**PP)
            a = a.astype(np.float64) / 65535.0
            y, cb, cr = rgb_to_ycbcr444(a[:,:,0], a[:,:,1], a[:,:,2], 12)
            fo.write(y.tobytes()); fo.write(cb.tobytes()); fo.write(cr.tobytes())
            print("  frame %d %dx%d" % (i, a.shape[1], a.shape[0]), flush=True)

def up2_h(c):
    """chroma width x2, co-sited: out[2k]=c[k], out[2k+1]=(c[k]+c[k+1]+1)>>1"""
    n = c.shape[1]
    o = np.empty((c.shape[0], n*2), dtype=np.int32)
    ci = c.astype(np.int32)
    o[:, 0::2] = ci
    o[:, 1::2] = (ci + np.concatenate([ci[:,1:], ci[:,-1:]], axis=1) + 1) >> 1
    return o

def up2_v_centre(c):
    """chroma height x2, 4:2:0 vertical siting is centred between luma rows:
    out[2k] = (3*c[k] + c[k-1] + 2)>>2 ; out[2k+1] = (3*c[k] + c[k+1] + 2)>>2"""
    ci = c.astype(np.int32)
    up = np.concatenate([ci[:1], ci[:-1]], axis=0)
    dn = np.concatenate([ci[1:], ci[-1:]], axis=0)
    o = np.empty((c.shape[0]*2, c.shape[1]), dtype=np.int32)
    o[0::2] = (3*ci + up + 2) >> 2
    o[1::2] = (3*ci + dn + 2) >> 2
    return o

def do_yuv420(inp, W, H, depth, n, out):
    fw = W*H + 2*(W//2)*(H//2)
    a = np.fromfile(inp, dtype='<u2', count=fw*n)
    sh = 12 - depth
    with open(out, "wb") as fo:
        for k in range(n):
            o = k*fw
            y = a[o:o+W*H].reshape(H, W).astype(np.int32) << sh
            cs = (W//2)*(H//2)
            cb = a[o+W*H:o+W*H+cs].reshape(H//2, W//2)
            cr = a[o+W*H+cs:o+W*H+2*cs].reshape(H//2, W//2)
            cb = (up2_h(up2_v_centre(cb)) << sh)
            cr = (up2_h(up2_v_centre(cr)) << sh)
            for p in (y, cb, cr):
                fo.write(np.clip(p, 0, 4095).astype('<u2').tobytes())
            print("  frame %d" % k, flush=True)

def do_yuv444_16(inp, W, H, f0, n, out):
    """4:4:4 16-bit -> canonical 4:4:4 12-bit.  Streams frame by frame: a 4K
    frame is 49.8 MB and the sources are 28 GB, so nothing is read whole."""
    samples = W * H * 3
    lo, hi = 65535, 0
    with open(inp, "rb") as fi, open(out, "wb") as fo:
        fi.seek(f0 * samples * 2)
        for i in range(n):
            d = np.fromfile(fi, dtype='<u2', count=samples)
            if d.size != samples:
                sys.exit("prep_master: source ran out at frame %d of %d" % (i, n))
            v = (d.astype(np.uint32) + 8) >> 4          # round-half-up
            lo = min(lo, int(v.min())); hi = max(hi, int(v.max()))
            np.clip(v, 0, 4095).astype('<u2').tofile(fo)
    print("%s: %d frames %dx%d 4:4:4/12b from source frame %d, range [%d,%d]"
          % (out, n, W, H, f0, lo, hi))

if __name__ == "__main__":

    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if sys.argv[1] == "dng":
        do_dng(sys.argv[2], int(sys.argv[3]), sys.argv[4])
    elif sys.argv[1] == "yuv444_16":
        do_yuv444_16(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]),
                     int(sys.argv[5]), int(sys.argv[6]), sys.argv[7])
    else:
        do_yuv420(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]),
                  int(sys.argv[5]), int(sys.argv[6]), sys.argv[7])
