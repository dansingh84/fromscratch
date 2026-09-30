"""Assemble the single self-contained deliverable.

The claim the output makes is the same one it audits: *this document, plus the
pristine omc_v4.7 zip, reproduces everything.*  So it is assembled from the
files on disk rather than transcribed, and it carries a verifier
(Appendix Z) that parses itself back out and rebuilds.

Run:  OMC_TREE=/tmp/fix OMC_PRISTINE=/tmp/pristine/omc_v4.7 \
      python3 repro/mkreport.py > OMC_UC_REVIEW_AND_REBUILD.md
"""

import os
import re
import subprocess
import sys

TREE = os.environ.get("OMC_TREE", "/tmp/fix")
PRIS = os.environ.get("OMC_PRISTINE", "/tmp/pristine/omc_v4.7")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# Files that DO NOT exist in the pristine zip.  Their complete text goes in.
NEW = [
    ("include/omc_uc.h", "the upconverter's public interface"),
    ("include/omc_tf.h", "the temporal filter's public interface"),
    ("src/upconv.c", "the normative upconversion arithmetic"),
    ("src/uc_poly_tab.c.inc", "the published polyphase coefficients"),
    ("src/tfilt.c", "the normative filter arithmetic"),
    ("tests/test_uc.c", "upconverter unit gates"),
    ("tests/test_tf.c", "filter unit gates"),
    ("tools/omc_uc_tool.c", "the standalone conversion tool"),
    ("harness/uc_verify.py", "the 39 verification gates"),
    ("harness/uc_hw_budget.py", "the FPGA budget"),
    ("harness/uc_gallery.py", "the inspection pictures"),
    ("harness/tf_prep.py", "builds the Part II corpus from the footage"),
    ("harness/tf_verify.py", "gates T1-T4 and the quality tables"),
    ("harness/tf_sweep.py", "the gate-1 strictness sweep"),
    ("harness/tf_gen.py", "gate T5, generation robustness"),
    ("harness/tf_hw_budget.py", "the filter's FPGA budget"),
    ("harness/tf_rate.py", "the operating-envelope sweep"),
    ("harness/tf_tune.py", "the unswept-constant sweep"),
    ("ucproto.py", "the independent Python reference model"),
    ("xcheck.py", "the two-implementation cross-check"),
    ("ratcheck.py", "independent verification of the RATIONAL path"),
    ("harness/tf_stats.py", "gate-1's design evidence (was cited, never shipped)"),
    ("include/omc_cc.h", "OMC-CC, the colour converter's public interface"),
    ("src/colour.c", "the normative colour-conversion arithmetic"),
    ("src/cc_tab.c.inc", "the published colour tables -- transfers, primaries, matrices"),
    ("tests/test_cc.c", "colour unit gates, including the double-precision reference"),
    ("tools/omc_tf_tool.c", "standalone driver for the temporal filter"),
    ("tfproto.py", "the independent Python model of OMC-TF"),
    ("tfcheck.py", "OMC-TF cross-check and conformance vectors"),
]

# Files that DO exist in the pristine zip.  A unified diff goes in.
MOD = ["Makefile", "include/omc1.h", "src/internal.h", "src/codec.c",
       "src/config.c", "tools/omc_dec.c", "tools/omc_enc.c",
       # The C8 documentation fix (findings A2/A3) edits BITSTREAM.md, and it
       # was missing from this list until the self-containment audit in section
       # 11.2 was actually RUN against the tree rather than reasoned about.  A
       # document that fixes the bitstream documentation and then does not carry
       # the fix is worse than one that never claimed to.
       #
       # Nothing else under docs/ is here on purpose: a second documentation
       # edit restating what BITSTREAM.md already says was reverted rather than
       # carried.  See Part D.
       "docs/BITSTREAM.md"]

# Measurement programs written for this review.
EXTRA = [
    ("repro/gen_uc_poly_tables.c", "generates the rational phase tables"),
    ("repro/zoneplate_native_scan.py", "the D7 polarity-inversion scan"),
    ("repro/downconv_alias_test.py", "the C6 sinusoid alias instrument"),
    ("repro/build_vmaf.sh", "builds the VMAF toolchain Part II needs"),
    ("repro/mkreport.py", "assembles this document"),
    ("repro/gen_cc_tables.c", "generates the colour tables"),
    ("repro/fill_direction_interaction.py", "OD 11.8's fill/direction table, rebuilt"),
]

LANG = {".c": "c", ".h": "c", ".py": "python", "Makefile": "make"}


def lang_of(path):
    base = os.path.basename(path)
    if base in LANG:
        return LANG[base]
    return LANG.get(os.path.splitext(path)[1], "")


def fence_for(text):
    """A fence longer than any run of backticks inside the text."""
    n = 3
    while "`" * n in text:
        n += 1
    return "`" * n


def emit_file(letter, path, note, body):
    f = fence_for(body)
    print("## Appendix %s — `%s` (%s)\n" % (letter, path, note))
    print("%s%s" % (f, lang_of(path)))
    print(body.rstrip("\n"))
    print(f)
    print()


def appendix_letters():
    """path -> appendix letter, in the order main() emits them."""
    letters = [chr(ord("A") + i) for i in range(25)]
    letters += ["A" + chr(ord("A") + i) for i in range(26)]
    m, idx = {}, 0
    for path, _ in NEW:
        m[path] = letters[idx]; idx += 1
    m["__MOD__"] = letters[idx]; idx += 1
    for path, _ in EXTRA:
        m[path] = letters[idx]; idx += 1
    m["work/rebuild.py"] = "Z"
    return letters, m


def main():
    prose = open(os.path.join(ROOT, "REVIEW_BODY.md"), encoding="utf-8").read()
    # Appendix letters shift whenever a file is added, so the prose refers to
    # appendices by PATH and the letter is substituted here.  A stale hand-typed
    # letter is exactly the failure mode Appendix L hit in the delivery document.
    _, apx = appendix_letters()
    def sub(mo):
        k = mo.group(1)
        if k not in apx:
            raise SystemExit("mkreport: {{APX:%s}} names no appendix" % k)
        return apx[k]
    prose = re.sub(r"\{\{APX:([^}]+)\}\}", sub, prose)
    print(prose.rstrip("\n"))
    print()
    print("---")
    print()
    print("# Appendices — the complete source of everything not in the zip")
    print()
    print("Every file below is either **new** (its full text is here and nowhere")
    print("else) or a **unified diff** against the pristine `omc_v4.7` copy.")
    print("Appendix Z rebuilds the tree from this document alone and runs the gates,")
    print("so the self-containment claim is testable rather than asserted.")
    print()

    # A..Y, then AA, AB, ... -- there are more than 25 appendices now.
    letters, _ = appendix_letters()
    idx = 0
    print("| appendix | file | what it is |")
    print("|---|---|---|")
    for path, note in NEW:
        print("| %s | `%s` | new — %s |" % (letters[idx], path, note))
        idx += 1
    mod_letter = letters[idx]
    print("| %s | the %d modified files | unified diffs against the zip |"
          % (mod_letter, len(MOD)))
    idx += 1
    for path, note in EXTRA:
        print("| %s | `%s` | new — %s |" % (letters[idx], path, note))
        idx += 1
    print("| Z | `work/rebuild.py` | rebuilds from this document and gates it |")
    print()

    idx = 0
    for path, note in NEW:
        body = open(os.path.join(TREE, path), encoding="utf-8").read()
        emit_file(letters[idx], path, "new — " + note, body)
        idx += 1

    diffs = []
    for path in MOD:
        a, b = os.path.join(PRIS, path), os.path.join(TREE, path)
        r = subprocess.run(["diff", "-u", a, b], capture_output=True, text=True)
        d = r.stdout
        if not d.strip():
            continue
        d = d.replace("--- " + a, "--- a/" + path).replace("+++ " + b,
                                                           "+++ b/" + path)
        diffs.append(d)
    joined = "".join(diffs)
    f = fence_for(joined)
    print("## Appendix %s — patches to the files that ARE in the zip\n" % mod_letter)
    print("Apply with `patch -p1` from the root of the unpacked tree.\n")
    print("%sdiff" % f)
    print(joined.rstrip("\n"))
    print(f)
    print()

    for path, note in EXTRA:
        body = open(os.path.join(ROOT, path), encoding="utf-8").read()
        emit_file(letters[idx], path, "new — " + note, body)
        idx += 1

    body = open(os.path.join(HERE, "rebuild.py"), encoding="utf-8").read()
    emit_file("Z", "work/rebuild.py", "new — rebuilds from this document", body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
