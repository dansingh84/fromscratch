#!/usr/bin/env python3
"""ants.py - the temporal-stability ("ants") instrument, all three planes.

The defect: areas the SOURCE holds still and flat, that the DECODE does not.
A viewer reads that as crawling texture -- the "ants" REPORT.md 18.5-18.7
records as the one thing that gave the codec away.

Method, following REPORT.md 18.6-18.7 and generalised off luma:

  * split every plane into 16x16 blocks;
  * a block QUALIFIES when the source holds it both FLAT (per-frame standard
    deviation <= flat) and STATIC (mean |frame-to-frame difference| <= still),
    in every frame and every frame pair;
  * over the samples of qualifying blocks, report
       tail  = P(|frame-to-frame difference| > 6 codes)   <- the ant count
       boil  = mean |frame-to-frame difference|            <- the average motion
    for the decode AND for the source itself.

The source's own column is the TARGET, not zero: real footage has grain and it
moves, and a codec quieter than its own source has removed texture rather than
fixed anything.  The block count is printed with every figure because a
percentage computed over three blocks is not evidence.

Thresholds are in 10-bit code values and scale with the coded depth.

  ants.py <master.yuv> <decode.yuv> <W> <H> <422|444> <depth>
          [--flat F] [--still S] [--strict] [--json out.json]
"""
import sys, json
import numpy as np

a = sys.argv[1:]
master, decode, W, H, fmt, depth = a[0], a[1], int(a[2]), int(a[3]), a[4], int(a[5])
flat_t, still_t, jout = 12.0, 6.0, None
i = 6
while i < len(a):
    if a[i] == '--flat': flat_t = float(a[i+1]); i += 2
    elif a[i] == '--still': still_t = float(a[i+1]); i += 2
    elif a[i] == '--strict': flat_t, still_t = 4.0, 2.0; i += 1
    elif a[i] == '--json': jout = a[i+1]; i += 2
    else: i += 1

B = 16
sc = 2.0 ** (depth - 10)          # thresholds are quoted at 10-bit
flat_t *= sc; still_t *= sc
tail_t = 6.0 * sc
Wc = W if fmt == '444' else W // 2
fw = W * H + 2 * Wc * H

m = np.fromfile(master, dtype='<u2')
d = np.fromfile(decode, dtype='<u2')
nf = min(m.size // fw, d.size // fw)
if nf < 2:
    print("ants: need at least 2 frames"); sys.exit(2)
m = m[:nf * fw].reshape(nf, fw).astype(np.float32)
d = d[:nf * fw].reshape(nf, fw).astype(np.float32)

def blocks(x, h, w):
    """(frames, H, W) -> (frames, nby, nbx, B*B), dropping any partial edge"""
    nby, nbx = h // B, w // B
    x = x[:, :nby * B, :nbx * B]
    return x.reshape(x.shape[0], nby, B, nbx, B).transpose(0, 1, 3, 2, 4) \
            .reshape(x.shape[0], nby, nbx, B * B)

names, out = ["Y", "Cb", "Cr"], {}
print("plane  blocks   decode tail%%  boil    source tail%%  boil    (flat<=%.0f still<=%.0f, "
      "tail at |d|>%.0f codes)" % (flat_t, still_t, tail_t))
for p in range(3):
    pw = W if p == 0 else Wc
    off = 0 if p == 0 else W * H + (p - 1) * Wc * H
    ms = m[:, off:off + pw * H].reshape(nf, H, pw)
    ds = d[:, off:off + pw * H].reshape(nf, H, pw)
    mb, db = blocks(ms, H, pw), blocks(ds, H, pw)
    # source qualification
    sd = mb.std(axis=3)                       # (frames, nby, nbx)
    mv = np.abs(np.diff(mb, axis=0)).mean(axis=3)   # (frames-1, nby, nbx)
    ok = (sd.max(axis=0) <= flat_t) & (mv.max(axis=0) <= still_t)
    n = int(ok.sum())
    if n == 0:
        print("%-6s %6s   %s" % (names[p], 0, "no verdict -- the source has no flat, static block here"))
        out[names[p]] = {"blocks": 0}
        continue
    dd = np.abs(np.diff(db, axis=0))[:, ok, :]     # (frames-1, nblocks, B*B)
    md = np.abs(np.diff(mb, axis=0))[:, ok, :]
    r = {"blocks": n,
         "dec_tail": float((dd > tail_t).mean() * 100.0), "dec_boil": float(dd.mean()),
         "src_tail": float((md > tail_t).mean() * 100.0), "src_boil": float(md.mean())}
    out[names[p]] = r
    print("%-6s %6d   %10.2f %7.3f   %10.2f %7.3f" %
          (names[p], n, r["dec_tail"], r["dec_boil"], r["src_tail"], r["src_boil"]))
out["_cfg"] = {"flat": flat_t, "still": still_t, "tail": tail_t, "frames": nf, "block": B}
if jout: json.dump(out, open(jout, "w"), indent=1)
