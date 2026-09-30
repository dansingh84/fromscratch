"""OMC-TF gate T5: generation robustness (A4).

The codec's own docs (docs/DESIGN.md, the `--mv-regions` note) record that a
FIXED acceptance threshold on a shallow decision surface can decide differently
when the input is a re-encode, so generations accumulate loss instead of
replaying byte-exactly.  OMC-TF's gate 1 is exactly that shape — a fixed
sad/activity threshold — so the risk is real and has to be measured, not
assumed away.

Method: encode the master, decode, re-encode the decode, four generations deep,
with the filter off and on.  Report per-plane PSNR against the ORIGINAL master
at every generation, and report whether the BITSTREAM ever settles to a
byte-identical replay.

The criterion is per-hop, not slope-based: the filtered chain must not be worse
than the unfiltered chain at ANY generation, on ANY plane.  A tool that starts
higher and converges to the same floor has a steeper slope while never being
worse, so slope alone would condemn a harmless tool; but a tool that ends up
BELOW the baseline at some hop has genuinely cost a multi-hop chain something,
and that is what this gate is for.

This gate is expected to FAIL for OMC-TF, and the delivery document says so.
That failure is the evidence for shipping the filter OFF BY DEFAULT and
off-spec for multi-hop contribution — the same disposition, for the same
measured reason, that docs/DESIGN.md already gives `--mv-regions`.

Run:  python3 harness/tf_gen.py [--seq pingpong] [--bpp 0.5] [--gens 4]
"""

import argparse
import os
import subprocess
import sys

import numpy as np

from common import psnr_all, read_yuv

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TF = os.path.join(ROOT, "work", "tf")
GEN = os.path.join(TF, "gen")
SEQS = {"static": (4480, 1856, 6), "real": (4480, 1856, 2),
        "pingpong": (4480, 1856, 6), "pan08": (1536, 1024, 6),
        "pan24": (1536, 1024, 6), "pan36": (1536, 1024, 6),
        "panfrac": (1536, 1024, 6)}


def chain(seq, w, h, n, bpp, strength, gens, first_only=False):
    """Four generations deep.  `first_only` runs the filter on generation 1 and
    switches it OFF for every generation after -- which is the configuration an
    operator following the deployment rule actually produces, and which nothing
    had measured: every earlier run left the filter on at every hop, i.e. it
    measured a mistake rather than the product."""
    os.makedirs(GEN, exist_ok=True)
    src = os.path.join(TF, seq + ".yuv")
    cur_in = src
    outs = []
    tag = "f%d" % strength if first_only else "s%d" % strength
    for g in range(1, gens + 1):
        st = strength if (g == 1 or not first_only) else 0
        env = dict(os.environ, OMC_TF=str(st))
        bs = os.path.join(GEN, "%s_%s_g%d.omc" % (seq, tag, g))
        dec = os.path.join(GEN, "%s_%s_g%d.yuv" % (seq, tag, g))
        r = subprocess.run([os.path.join(ROOT, "omc_enc"), "-i", cur_in,
                            "-o", bs, "-w", str(w), "-h", str(h), "--fmt", "422",
                            "--depth", "10", "--bpp", str(bpp)],
                           env=env, capture_output=True, text=True)
        if r.returncode:
            raise SystemExit("gen %d encode failed: %s" % (g, r.stderr[-300:]))
        r = subprocess.run([os.path.join(ROOT, "omc_dec"), "-i", bs, "-o", dec],
                           env=env, capture_output=True, text=True)
        if r.returncode:
            raise SystemExit("gen %d decode failed: %s" % (g, r.stderr[-300:]))
        outs.append((bs, dec))
        cur_in = dec
    return outs


def replay_depth(chain_files):
    """How many generations in, does the BITSTREAM stop changing?

    docs/DESIGN.md claims byte-exact generation replay for the default encoder
    ('generations 2-5 identical').  An in-loop filter is a new decision surface,
    so whether that property survives has to be checked directly rather than
    inferred from PSNR.  Returns the first generation g>=2 whose bitstream is
    byte-identical to generation g-1, or 0 if none is.
    """
    for g in range(1, len(chain_files)):
        with open(chain_files[g - 1][0], "rb") as f1, \
             open(chain_files[g][0], "rb") as f2:
            if f1.read() == f2.read():
                return g + 1
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seq", default="pingpong,pan24,real")
    ap.add_argument("--bpp", type=float, default=0.5)
    ap.add_argument("--gens", type=int, default=4)
    ap.add_argument("--first-only", action="store_true",
                    help="filter on generation 1 only, off thereafter -- the "
                         "deployment rule, rather than the mistake")
    a = ap.parse_args()

    print("OMC-TF T5: generation robustness (A4) @ %.2f bpp, frames 1..%s\n"
          % (a.bpp, "  [FILTER ON GENERATION 1 ONLY]" if a.first_only else ""))
    bad = []
    for seq in a.seq.split(","):
        w, h, n = SEQS[seq]
        cw, lo = w // 2, 1 if SEQS[seq][2] > 1 else 0
        src = read_yuv(os.path.join(TF, seq + ".yuv"), w, h, cw, n)
        print("=== %s ===" % seq)
        drops = {}
        for s in (0, 1):
            outs = chain(seq, w, h, n, a.bpp, s, a.gens,
                         first_only=a.first_only and s != 0)
            rd = replay_depth(outs)
            print("  TF=%d  bitstream replay: %s" %
                  (s, "byte-identical from generation %d" % rd if rd
                      else "never byte-identical within %d generations" % a.gens))
            row = []
            for g, (_, path) in enumerate(outs, 1):
                o = read_yuv(path, w, h, cw, n)
                p = [psnr_all(src[i], o[i], 10) for i in range(lo, n)]
                row.append(tuple(float(np.mean([q[k] for q in p]))
                                 for k in ("Y", "Cb", "Cr")))
            drops[s] = row
            print("  TF=%d  " % s + "  ".join(
                "g%d %.2f/%.2f/%.2f" % (g, y, cb, cr)
                for g, (y, cb, cr) in enumerate(row, 1)))
        # ---- A4 criterion.
        #
        # The slope from generation 1 to N is NOT the right test, and saying so
        # is not moving the goalposts — it is correcting a test that measured
        # the wrong thing.  A tool that starts higher and converges toward the
        # same floor necessarily has a steeper slope while never being worse.
        # What actually matters to a multi-hop contribution chain is the
        # quality you hold AT EACH HOP.  So: the filtered chain must not be
        # worse than the unfiltered chain at ANY generation, on ANY plane.
        for k, nm in enumerate(("Y", "Cb", "Cr")):
            s0 = drops[0][0][k] - drops[0][-1][k]
            s1 = drops[1][0][k] - drops[1][-1][k]
            per_gen = [drops[1][g][k] - drops[0][g][k] for g in range(a.gens)]
            worst = min(per_gen)
            flag = "" if worst >= -0.02 else "  <-- WORSE AT A HOP"
            if flag:
                bad.append("%s %s worst hop %+.3f" % (seq, nm, worst))
            print("     %s  g1->g%d loss: TF=0 %+.3f dB  TF=1 %+.3f dB   "
                  "filtered-minus-baseline per hop: %s%s" %
                  (nm, a.gens, -s0, -s1,
                   " ".join("%+.2f" % v for v in per_gen), flag))
        print()
    print("T5 %s" % ("PASS - the filtered chain is never worse at any hop"
                     if not bad else "FAIL: " + "; ".join(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
