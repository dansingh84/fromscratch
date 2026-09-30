#!/usr/bin/env python3
"""xsdepth8.py pack|unpack IN OUT W H FMT NFRAMES

The 8-bit arms are stored in a <u2 CONTAINER like every other arm, but
SVT-JPEG-XS reads and writes PACKED u8 when --input-depth 8.  Without this
conversion the encoder reads two source samples as one and every 8-bit number
on the board is garbage.

  pack   : arm  (<u2 container, values 0..255) -> SVT input  (u8)
  unpack : SVT decode (u8)                     -> arm shape  (<u2 container)
"""
import sys, numpy as np

def planes(w, h, fmt):
    cw = w if fmt == '444' else w // 2
    ch = h if fmt in ('444', '422') else h // 2
    return w * h + 2 * cw * ch

def main():
    a = sys.argv[1:]
    if len(a) != 7: raise SystemExit(__doc__)
    mode, src, dst, w, h, fmt, nf = a[0], a[1], a[2], int(a[3]), int(a[4]), a[5], int(a[6])
    n = planes(w, h, fmt) * nf
    if mode == 'pack':
        x = np.fromfile(src, dtype='<u2', count=n)
        if x.size != n: raise SystemExit('FAIL short read %d/%d' % (x.size, n))
        if x.max() > 255: raise SystemExit('FAIL: sample %d > 255 -- this is not an 8-bit arm' % x.max())
        x.astype(np.uint8).tofile(dst)
    elif mode == 'unpack':
        x = np.fromfile(src, dtype=np.uint8, count=n)
        if x.size != n: raise SystemExit('FAIL short read %d/%d' % (x.size, n))
        x.astype('<u2').tofile(dst)
    else:
        raise SystemExit(__doc__)

main()
