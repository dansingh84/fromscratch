"""Retrain OMC tANS table groups on the broadened corpus (bucket 3e).

Differences from train_tables2.py (which produced the v3.0 tables):
  1. The transform mirror now matches the shipped codec exactly: (9,7)-M on
     horizontal levels 1-2 (proto.py was all-5/3 when the v2 tables were
     trained).
  2. The corpus adds what the codec actually codes since v3:
       - INTER statistics: coefficient-domain deltas between consecutive
         frames (co-located, MV 0) for every multi-frame master - the proxy
         for the quantized-delta distributions the v2 training never saw;
       - the 64-frame program feed (real camera deltas, pans, cut frames);
       - the synthetic gradient ramp (G2 material).
  3. Same clustering (Lloyd under total cross-entropy, 16 groups x 4 ctx).

Emits include/tables.h + src/tables.c ONLY when run with --emit; default run
reports the projected coding cost of old vs new tables on the training set so
the decision to freeze is measured, not assumed.

Run: python3 harness/train_tables3.py [--emit]
"""

import argparse
import json
import os
import sys

import numpy as np

from common import MASTERS_DIR, SCRATCH, SEQUENCES, read_yuv
from proto import quant, slice_fwd2
from train_tables2 import LL_CAP, NCTX, NSYM, OFF, band_hists, emit, lloyd

L = 1024
K = 16


def tile_hists(plane, h, Q, acc, ref_plane=None):
    """Accumulate per-band context histograms for one plane; if ref_plane is
    given, statistics are of the coefficient-domain DELTA (inter proxy)."""
    for y0 in range(0, h - 15, 16):
        tile = plane[y0:y0 + 16].astype(np.int32) - 512
        bands = slice_fwd2(tile)
        if ref_plane is not None:
            rbands = slice_fwd2(ref_plane[y0:y0 + 16].astype(np.int32) - 512)
        for b in range(10):
            s = max(0, min(15, Q + OFF[b]))
            if b == 0:
                s = min(s, LL_CAP)
            arr = bands[b] - rbands[b] if ref_plane is not None else bands[b]
            acc[b] += band_hists(quant(arr, s), dpcm=(b == 0))


def collect():
    mani = json.load(open(MASTERS_DIR + "/manifest.json"))
    tuples = []

    def add_frame(frame, h, prev=None, qs=(3, 4, 5, 6)):
        for Q in qs:
            for p in range(3):
                acc = [np.zeros((NCTX, NSYM), dtype=np.int64) for _ in range(10)]
                tile_hists(frame[p], h, Q, acc,
                           ref_plane=None if prev is None else prev[p])
                for b in range(10):
                    if acc[b].sum() > 0:
                        tuples.append(acc[b].astype(np.float64))

    # 1. masters: intra frame 0 + inter delta frame1-vs-frame0
    for name in SEQUENCES:
        w, h = mani[name]["w"], mani[name]["h"]
        fr = read_yuv(f"{MASTERS_DIR}/{name}_422_10.yuv", w, h, w // 2)
        add_frame(fr[0], h)
        if len(fr) > 1:
            add_frame(fr[1], h, prev=fr[0])
        print("collected", name, len(tuples), flush=True)

    # 2. program feed: cut-frame intra + steady/pan inter deltas
    prog = os.path.join(SCRATCH, "program.yuv")
    if os.path.exists(prog):
        fr = read_yuv(prog, 1920, 1056, 960)
        for i in (0, 32):              # cut frames, intra
            add_frame(fr[i], 1056, qs=(3, 5))
        for i in (3, 19, 35, 40, 51, 56):  # steady + pan, inter
            add_frame(fr[i], 1056, prev=fr[i - 1], qs=(3, 5))
        print("collected program", len(tuples), flush=True)

    # 3. gradient ramp (G2 material), intra
    w, hh = 1920, 512
    x = np.linspace(0, 1, w)
    y = np.linspace(0, 1, hh)[:, None]
    Y = (256 + 300 * (0.6 * x[None, :] + 0.4 * y)).astype(np.uint16)
    Cb = (512 + 60 * x[None, :] * np.ones((hh, 1))).astype(np.uint16)
    Cr = (512 - 40 * y * np.ones((1, w))).astype(np.uint16)
    add_frame((Y, Cb[:, ::2].copy(), Cr[:, ::2].copy()), hh, qs=(3, 5))
    print("collected ramp", len(tuples), flush=True)
    return tuples


def table_cost(tuples, counts):
    """Total bits to code the training set with table groups `counts`
    (best group per tuple, mirroring the encoder's best_group)."""
    probs = counts / counts.sum(axis=-1, keepdims=True)
    logs = -np.log2(np.maximum(probs, 1e-12))  # [K][NCTX][NSYM]
    total = 0.0
    for t in tuples:
        costs = (logs * t[None, :, :]).sum(axis=(1, 2))
        total += costs.min()
    return total


def load_current_counts():
    import re
    src = open(os.path.join(os.path.dirname(__file__), "..", "src", "tables.c")).read()
    m = re.search(r"omc_tans_counts\[.*?\] = \{(.*?)\n\};", src, re.S)
    rows = re.findall(r"\{([0-9, ]+)\}", m.group(1))
    a = np.array([[int(v) for v in r.split(",")] for r in rows], dtype=np.float64)
    return a.reshape(K, NCTX, NSYM)


def cents_to_counts(cents):
    out = np.zeros((K, NCTX, NSYM))
    for j in range(K):
        for x in range(NCTX):
            c = np.maximum(1, np.round(cents[j][x] * L)).astype(int)
            c[np.argmax(c)] += L - c.sum()
            out[j][x] = c
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emit", action="store_true")
    args = ap.parse_args()
    tuples = collect()
    print(len(tuples), "band tuples")
    cents = lloyd(tuples)
    new_counts = cents_to_counts(cents)
    old_counts = load_current_counts()
    cost_old = table_cost(tuples, old_counts)
    cost_new = table_cost(tuples, new_counts)
    print(f"training-set cost: old tables {cost_old/8/1024:.0f} KB, "
          f"new tables {cost_new/8/1024:.0f} KB "
          f"({(cost_old-cost_new)/cost_old*100:.2f}% saved)")
    if args.emit:
        emit(cents)
        print("emitted include/tables.h + src/tables.c")
    else:
        print("dry run - re-run with --emit to write tables")


if __name__ == "__main__":
    sys.setrecursionlimit(10000)
    main()
