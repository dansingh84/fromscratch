#!/usr/bin/env python3
"""[A5-LATMODEL] Agent 5 / Task E -- the A2 latency model, corrected.

WHY A NEW ONE.  `.work/sandbox/harness/latency_model.py` disagrees with the
codec.  Checked against src/config.c (`omc_config_latency`, the same arithmetic
`omc_validate_config` enforces), src/codec.c (`OD_CAP_PCT`), tools/omc_enc.c
(the pad-to-slice_h rule) and src/upconv.c (the reach functions), it is wrong
in four places, two of which push the same format in opposite directions:

  1. it charges a banking overdraft of half a slice period.  `OD_CAP_PCT` has
     been 0 since 2026-08-12 and there is no knob ("the prefix bound is
     (k+1)*bits_per_slice, full stop", src/codec.c).  OVERSTATES every format.
  2. it has no resolution-conversion term.  The codec charges
     (reach + 1) * line_time on the default raster-clocked output stage, and
     REFUSES a configuration over 1 ms when a2_strict is set.  UNDERSTATES
     every leg with a rescaler in it -- which is the only place the bar has
     ever been at risk.
  3. it uses slice_h 8 at 1080p.  Both the library default
     (`omc_resolve_slice_h`) and the CLI use 16 above 720 lines.
  4. it uses 1080 coded lines / 135 slices.  1080 is not a multiple of 16, so
     the encoder codes 1088 lines in 68 slices and crops on output.

  Net at 1080p50, the product's commonest format: it reports 0.407 ms where the
  codec's own model reports 0.625 ms.

This file reproduces the codec's arithmetic exactly (verified against the
`latprobe` binary, which calls omc_config_latency() itself), and adds the STAGE
column the old model has no concept of: which stages contribute lines of delay
and which contribute none.  Every stage figure is cited to a file and a
mechanism in the memo; nothing here is a guess.

Usage:  lat_model.py [--stages]
"""
import sys

# name, width, height(true), fps_num, fps_den
FORMATS = [
    ("720p50",     1280,  720,    50, 1),
    ("720p59.94",  1280,  720, 60000, 1001),
    ("720p60",     1280,  720,    60, 1),
    ("1080p50",    1920, 1080,    50, 1),
    ("1080p59.94", 1920, 1080, 60000, 1001),
    ("1080p60",    1920, 1080,    60, 1),
    ("2160p50",    3840, 2160,    50, 1),
    ("2160p60",    3840, 2160,    60, 1),
    ("2160p100",   3840, 2160,   100, 1),
    ("2160p120",   3840, 2160,   120, 1),
    ("4320p50",    7680, 4320,    50, 1),
    ("4320p60",    7680, 4320,    60, 1),
    ("4320p120",   7680, 4320,   120, 1),
]

PIPE_LINES = 2      # src/config.c: the "+ 2 * line_ms" term
UC_REACH = {0: 0, 1: 8, 2: 12}   # omc_uc_analytic_reach_n(levels), src/upconv.c


def slice_h(height, forced=0):
    """tools/omc_enc.c: 8 at 720-class, else 16."""
    return forced if forced else (8 if height <= 720 else 16)


def coded_height(height, sh):
    """tools/omc_enc.c: code at the next multiple of slice_h, crop on output."""
    return (height + sh - 1) // sh * sh


def terms(w, h, num, den, uc_ratio=0, forced_sh=0, batched=False):
    sh = slice_h(h, forced_sh)
    ch = coded_height(h, sh)
    nsl = ch // sh
    frame_ms = 1000.0 * den / num
    line_ms = frame_ms / ch
    slice_ms = frame_ms / nsl
    reach = UC_REACH[uc_ratio]
    if batched:
        conv = ((reach + sh - 1) // sh) * slice_ms
    else:
        conv = (reach + 1) * line_ms if reach else 0.0
    t_cap = sh * line_ms
    t_pipe = PIPE_LINES * line_ms
    total = t_cap + slice_ms + t_pipe + conv
    return dict(sh=sh, ch=ch, nsl=nsl, frame_ms=frame_ms, line_ms=line_ms,
                cap=t_cap, tx=slice_ms, pipe=t_pipe, reach=reach, conv=conv,
                total=total)


def table(uc_ratio=0, forced_sh=0):
    rows = ["| Format | slice_h | coded h | slices | capture | transmit | "
            "pipeline | conversion | **total** | verdict |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    worst = 0.0
    for name, w, h, num, den in FORMATS:
        t = terms(w, h, num, den, uc_ratio, forced_sh)
        worst = max(worst, t["total"])
        rows.append(
            "| %s | %d | %d | %d | %.3f ms | %.3f ms | %.3f ms | %.3f ms | "
            "**%.3f ms** | %s |" % (
                name, t["sh"], t["ch"], t["nsl"], t["cap"], t["tx"],
                t["pipe"], t["conv"], t["total"],
                "PASS" if t["total"] < 1.0 else "**OVER**"))
    rows.append("")
    rows.append("worst case %.3f ms -- %s" %
                (worst, "all formats < 1 ms" if worst < 1.0 else "A2 BREACHED"))
    return "\n".join(rows)


# ---- the stage inventory: which stages cost LINES, and which cost none ----
# lines: expression in sh (slice height) / reach; "0" = contributes no
# algorithmic delay.  Every entry is cited to the code in the memo.
STAGES = [
    # stage,                          lines,     content-dependent?, where
    ("capture wait (slice_h lines)",  "sh",      "no",  "omc_enc_slice reads rows [k*sh, +sh)"),
    ("input un-blend look-ahead",     "2",       "no",  "omc_xsl_unblend: boundary k+1 writes row (k+1)*sh-1, reads (k+1)*sh+1"),
    ("forward DWT vertical support",  "0",       "no",  "omc_slice_fwd_p: 2 V levels, slice-local"),
    ("horizontal DWT (5 levels)",     "0",       "no",  "within a row"),
    ("XSL boundary term (encoder)",   "0",       "no",  "xsl_prep reads slice k-1 COMMITTED rows -- already final"),
    ("plan / cost tables",            "0",       "no",  "compute only; fixed 32 slice passes eager, ~11 lazy"),
    ("lattice candidate scan+verify", "0",       "YES", "compute only; unbounded list (OMC_LOCK_CANDS 4096)"),
    ("emit attempts (overflow)",      "0",       "YES", "compute only; hard cap 40"),
    ("in-gamut repair",               "0",       "YES", "compute only; cap 12 (OMC_GAMUT_DEFPASS), max 16"),
    ("entropy coding (tANS)",         "0",       "no",  "whole-slice reverse walk; no line beyond the slice"),
    ("packetisation",                 "0",       "no",  "slice granularity = the transmit term"),
    ("paced transmission",            "sh",      "no",  "one slice period at the provisioned CBR pipe"),
    ("decode start",                  "0",       "no",  "needs the WHOLE slice payload (backward read from used_bits)"),
    ("decoder entropy+dequant",       "0",       "no",  "inside the slice"),
    ("decoder inverse DWT",           "0",       "no",  "slice-local"),
    ("decoder display blend",         "1",       "no",  "rewrites row k*sh-1; deferred one slice period, net 1 line"),
    ("temporal prediction",           "0",       "no",  "refprev = previous FRAME, complete before slice 0"),
    ("resolution conversion",         "reach+1", "no",  "omc_uc_analytic_reach_n / omc_uc_scale_reach_r"),
    ("colour conversion",             "0",       "no",  "per pixel (src/colour.c)"),
]


def stage_table():
    rows = ["| stage | lines of delay | content-dependent | where / why |",
            "|---|---|---|---|"]
    for s, l, cd, w in STAGES:
        rows.append("| %s | %s | %s | %s |" % (s, l, cd, w))
    return "\n".join(rows)



# ---------------------------------------------------------------- the ONE table
# stage x format, in microseconds, sorted by lines of delay.  Stages that cost
# no lines cost no microseconds of LATENCY -- they are compute, and they appear
# with 0 and a note, because leaving them out of the table is how the project
# ended up with a model that only knows four terms.
LINE_STAGES = [
    # label,                            lines(sh, reach) -> lines
    ("capture wait",                    lambda sh, r: sh),
    ("paced slice transmission",        lambda sh, r: sh),      # = one slice period
    # The codec charges the converter as (reach + 1) lines, where the +1 is the
    # XSL display-blend row (docs/LATENCY.md: "The +1 line is OMC_XSL").  That
    # bundling is why the blend line VANISHES when there is no converter in the
    # path -- `conv = reach ? (reach + 1) * line_ms : 0` in src/config.c.  Here
    # the two are separated: the converter is charged its filter aperture and
    # the blend is charged once, always.  With a converter the two accountings
    # agree exactly; without one, this table is 1 line higher, and that line is
    # real (the blend defers row k*sh-1 whether or not anything is rescaling).
    ("resolution conversion (aperture)", lambda sh, r: r),
    ("input un-blend look-ahead",        lambda sh, r: 2),
    ("decoder display blend (XSL)",      lambda sh, r: 1),
]
ZERO_STAGES = [
    ("forward DWT (2V x 5H)",           "slice-local"),
    ("XSL boundary term (encoder)",     "reads slice k-1 COMMITTED rows"),
    ("plan / cost tables",              "compute; fixed 32 slice passes eager"),
    ("lattice candidate scan + verify", "compute; CONTENT-DEPENDENT, list <= 4096"),
    ("emit attempts (overflow)",        "compute; CONTENT-DEPENDENT, cap 40"),
    ("in-gamut repair",                 "compute; CONTENT-DEPENDENT, cap 12"),
    ("entropy coding (tANS)",           "whole-slice, inside the captured slice"),
    ("packetisation",                   "slice granularity = the transmit term"),
    ("decode start",                    "whole slice payload = the transmit term"),
    ("decoder entropy + dequant + fill","inside the slice"),
    ("decoder inverse DWT",             "slice-local"),
    ("temporal prediction",             "previous FRAME, already complete"),
    ("colour conversion",               "32 clocks, not lines"),
]


def matrix(uc_ratio=0):
    """stage x format, microseconds.  The transmit term is a slice PERIOD, not
    sh line times -- identical only because a slice period is sh lines of the
    CODED raster, which it is by construction (nslices = coded_h / sh)."""
    hdr = ["| stage | lines |"] 
    names = [f[0] for f in FORMATS]
    hdr[0] += " " + " | ".join(names) + " |"
    hdr.append("|---|---|" + "---|" * len(FORMATS))
    rows = list(hdr)
    totals = [0.0] * len(FORMATS)
    for label, fn in LINE_STAGES:
        cells = []
        lines_desc = None
        for i, (name, w, h, num, den) in enumerate(FORMATS):
            t = terms(w, h, num, den, uc_ratio)
            n = fn(t["sh"], t["reach"])
            us = (t["tx"] * 1000.0) if label.startswith("paced") else n * t["line_ms"] * 1000.0
            totals[i] += us
            cells.append("%.1f" % us)
            if lines_desc is None:
                lines_desc = str(n) if label != "paced slice transmission" else "sh"
        rows.append("| %s | %s | %s |" % (label, lines_desc, " | ".join(cells)))
    rows.append("| **TOTAL (us)** | | " +
                " | ".join("**%.1f**" % t for t in totals) + " |")
    rows.append("| **vs the 1000 us bar** | | " +
                " | ".join(("PASS %.0f%%" % (100.0 * t / 1000.0)) if t < 1000
                           else "**OVER**" for t in totals) + " |")
    rows.append("| **margin (us)** | | " +
                " | ".join("%.0f" % (1000.0 - t) for t in totals) + " |")
    rows.append("")
    rows.append("Stages that contribute **no lines and therefore no latency** "
                "(they are compute; see the memo on why that is the half of A2 "
                "actually at risk):")
    rows.append("")
    rows.append("| stage | why zero |")
    rows.append("|---|---|")
    for label, why in ZERO_STAGES:
        rows.append("| %s | %s |" % (label, why))
    return "\n".join(rows)

if __name__ == "__main__":
    if "--stages" in sys.argv:
        print(stage_table())
        sys.exit(0)
    if "--matrix" in sys.argv:
        for r in (0, 1, 2):
            print("\n### stage x format, microseconds -- %s\n"
                  % ("no conversion" if r == 0 else ("2x conversion" if r == 1
                                                     else "4x conversion")))
            print(matrix(r))
        sys.exit(0)
    print("## No conversion (uc_ratio 0)\n")
    print(table(0))
    print("\n## 2x output conversion (uc_ratio 1, reach 8)\n")
    print(table(1))
    print("\n## 4x output conversion (uc_ratio 2, reach 12)\n")
    print(table(2))
    print("\n## No conversion, slice_h forced to 8 everywhere\n")
    print(table(0, forced_sh=8))
    print("\n## No conversion, slice_h forced to 32 everywhere\n")
    print(table(0, forced_sh=32))
