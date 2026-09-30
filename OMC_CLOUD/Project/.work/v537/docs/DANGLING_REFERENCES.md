# Dangling references in the OMC v5.1 tree

**What this is.** Every path this tree cites that does not exist in it, found by
scanning all source, header, Makefile, script and documentation files for
in-tree path references and testing each for existence. Adversarial review item
7.9 asked for this register; it exists so that a reader who follows a citation
and finds nothing knows it is a known gap rather than a missing delivery.

**How to regenerate it.** The scan is nine lines of Python and is reproduced at
the end of this file, so the list can be re-derived rather than trusted.

## Current state (v5.1, 2026-08-25): 144 distinct in-tree paths referenced, 1 genuinely missing

**Two apparent misses are scanner artefacts, not defects.** The scan's regex ends
at a known source extension, so `patches/v51_codec.c.patch` and
`patches/v51_omc1.h.patch` are matched as `patches/v51_codec.c` and
`patches/v51_omc1.h`, which do not exist. Both patch files are present. The scan
is left as written rather than special-cased, and the artefact is recorded here
so the next reader does not chase it.

**v5.1 re-ran the scan.** The reference count rose from 91 to 142 (the v5.1
documents and harness cite more of the tree) and **`docs/SPEC_GAPS.md`, recorded
below as "genuinely missing", now exists** — it was written in v5.1 from the
surviving record, and it says explicitly where that record is incomplete rather
than reconstructing it. One citation remains unresolved and it is deliberate.

### The v5.0 state, kept for the record: 91 referenced, 2 missing

| cited path | cited by | assessment |
|---|---|---|
| `delivery/clips_5s/CLIPS_MEMO.md` | `docs/LETTER_TEAM_A.md` | **Deliberately absent.** `delivery/` holds viewing material, and the five-second clip set is footage rather than code. It is not shipped in the source zip because the zip is the codec, not the corpus. The memo describes clips the recipient is expected to already hold. |
| `docs/SPEC_GAPS.md` | `docs/HANDOFF_2026-08-04.md`, `harness/spec_decoder.py` | **RESOLVED in v5.1 — the file now exists.** The v5.0 assessment read: **Genuinely missing.** The independent-decoder exercise found four specification mistakes (recorded in `docs/EXECUTIVE_SUMMARY.md` under "The format is fully written down"), and this file was where they were to be listed. The findings themselves survive in `docs/BITSTREAM.md` and in the handoff document; only the summary index is absent. Recorded rather than reconstructed, because inventing its contents would be worse than noting its absence. |

## What this scan does NOT cover

- **External tools.** The harness calls `python3`, a C compiler, and for the
  perceptual measurements `vmaf` with a model file. Those are environment
  requirements, not in-tree references, and they are listed in
  `docs/OMC_V5.md` section 9.
- **Paths built at run time.** Output paths, temporary files and anything
  assembled by string concatenation are not detectable by a static scan and are
  not claimed to be covered.
- **References out of the tree.** Citations to documents that were never part of
  this delivery (design notes, meeting records) are out of scope.

## Identifier references, which the path scan cannot see

The scan above tests **paths**. A citation can also name an *entry* inside a
document, and one of those was dangling:

- **`XSL-RATE-OFF`** is cited by `docs/XSL.md:96` and
  `docs/HANDOFF_BIT_EXACTNESS.md:360` as an entry in `OPEN_DECISIONS.md`. No
  such entry exists; the entry those documents mean is **`A4-XSL`**. It was an
  earlier working name that the register was renamed away from without the two
  citing documents following.
  **Resolved additively:** `OPEN_DECISIONS.md` now records `XSL-RATE-OFF` as an
  alias of `A4-XSL`, so the citation resolves. The two v4-era documents were
  **not** edited — they are the record as written, and this delivery does not
  rewrite history to tidy a pointer.

This class is not covered by the automated scan, and no claim is made that
`XSL-RATE-OFF` was the only instance. A general identifier-level scan would need
to know each document's own heading conventions; it has not been built.

## One reference created and then satisfied

`docs/OMC_V5.md` was cited by `include/omc1.h`, `src/codec.c` and
`tools/omc_enc.c` before it was written. It now exists, and the scan above
confirms it.

## The scan

```python
import os, re
refs = {}
for root, dirs, files in os.walk('.'):
    if any(x in root for x in ('.git', '__pycache__')):
        continue
    for f in files:
        if not (f.endswith(('.c','.h','.md','.inc','.sh','.py')) or f == 'Makefile'):
            continue
        p = os.path.join(root, f)
        t = open(p, errors='replace').read()
        for m in re.finditer(
                r'\b((?:src|tests|tools|docs|include|repro|delivery|harness)'
                r'/[A-Za-z0-9_./-]+\.(?:c|h|md|py|sh|inc|json|txt))\b', t):
            refs.setdefault(m.group(1), set()).add(p)
for r in sorted(r for r in refs if not os.path.exists(r)):
    print(r, '<-', ', '.join(sorted(refs[r])))
```
