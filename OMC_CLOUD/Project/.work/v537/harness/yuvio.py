#!/usr/bin/env python3
"""yuvio.py -- shared planar-YUV reader for the session-4 instruments.

One reader, so that every map in h/flat15.py and h/line15.py sees exactly the
same pixels and a bug in the geometry cannot make two maps disagree.

Layout: planar Y, Cb, Cr, uint16 little-endian, one file, frames consecutive.
4:2:2 -> chroma is W/2 x H.   4:4:4 -> chroma is W x H.
"""
import numpy as np

def planes(path, W, H, f, fmt='422', depth=10):
    """Return (Y, Cb, Cr) as float64 arrays on the file's own code scale."""
    cw = W // 2 if fmt == '422' else W
    per = W * H + 2 * cw * H
    a = np.fromfile(path, dtype='<u2', count=per, offset=f * per * 2)
    if a.size < per:
        raise SystemExit("%s: short read at frame %d (%d of %d)" % (path, f, a.size, per))
    y = a[:W * H].reshape(H, W).astype(np.float64)
    cb = a[W * H:W * H + cw * H].reshape(H, cw).astype(np.float64)
    cr = a[W * H + cw * H:].reshape(H, cw).astype(np.float64)
    return y, cb, cr

def nframes(path, W, H, fmt='422'):
    import os
    cw = W // 2 if fmt == '422' else W
    return os.path.getsize(path) // ((W * H + 2 * cw * H) * 2)

def upchroma(c, W, fmt):
    """Chroma to luma raster (nearest / pixel replication -- no invented detail)."""
    return np.repeat(c, 2, axis=1)[:, :W] if fmt == '422' else c

def rgbish(y, cb, cr, W, fmt, depth=10):
    """A cheap, monotone, EXACTLY-invertible-enough opponent->RGB for colour
    measures.  Not a colorimetric transform and never used as one: it exists so
    that 'colour flatness' is measured on axes a viewer perceives rather than on
    Cb/Cr, which are already decorrelated.  BT.709 non-constant-luminance."""
    mid = 1 << (depth - 1)
    u = upchroma(cb, W, fmt) - mid
    v = upchroma(cr, W, fmt) - mid
    r = y + 1.5748 * v
    b = y + 1.8556 * u
    g = y - 0.1873 * u - 0.4681 * v
    return r, g, b
