# SPEC_GAPS — where the specification did not answer a question

**Created in v5.1 (2026-08-25), and late.** `docs/DANGLING_REFERENCES.md`
recorded this file as *"genuinely missing"* from v5.0: three places cite it
(`docs/HANDOFF_2026-08-04.md`, `harness/spec_decoder.py` and the dangling
register itself) and it did not exist. It is written now from the surviving
record rather than reconstructed from imagination, and where the record is
incomplete this file says so instead of filling the hole.

## What the exercise was

An independent decoder (`harness/spec_decoder.py`) was implemented from
`docs/BITSTREAM.md` **alone**, under a standing reading restriction: when the
document does not answer a question, record the section and the missing fact —
never read the implementation. That is the only test of C8 ("a stable, fully
documented, versioned format so multiple vendors interoperate") that is worth
anything, because an implementer holding the document and nothing else is
exactly the situation C8 describes.

## The gaps

### GAP-1 — the allocation tables were designated normative but not tabulated. **FIXED 2026-08-04.**

`docs/BITSTREAM.md` §6 named `omc_off[4][3][10]`, `omc_off_c444[10]` and
`omc_refine_order[]` as normative and pointed at `src/alloc.c` instead of
printing them. A vendor holding only the specification could not derive
per-band quantiser shifts — that is, **could not decode any stream at all.**

**Fix:** `docs/BITSTREAM.md` carries **Annex A** with all three tables in full
(120 + 10 offsets, 49 refinement steps), transcribed mechanically and verified
against the compiled constants (`omc_refine_steps == 49`, endpoints
spot-checked). §6 now points at Annex A. Verified present in this tree.

### GAP-2 — the NORMATIVE document contradicted its own Annex A. **FIXED in v5.1.**

`docs/HANDOFF_2026-08-04.md` recorded this as a stale comment in `src/codec.c`
and left it for "when next in that file". It is worse than that, and v5.1 found
it while checking: the wrong number is in **`docs/BITSTREAM.md` §9.1 itself** —
the normative specification — which read

> *"always 0 in prior streams, since the refinement schedule has 52 steps"*

while **Annex A.3 of the same document tabulates 49 steps**, and the compiled
`omc_refine_order[]` has 49. A normative document disagreeing with its own annex
about a normative constant is precisely the class of defect this file exists to
catch, and the fact that it was known and deferred for three weeks is the
process lesson.

**Fixed in v5.1**, and the argument is now stated so it cannot rot again: 49 is
less than 128, therefore bit 7 of the `n_steps` byte can never be set by a step
count, therefore it is free for the MV-field flag. The conclusion never depended
on the wrong number.

**Verified mechanically, not by eye.** Annex A.3's table was parsed out of the
document and compared entry-for-entry against `omc_refine_order[]` in
`src/alloc.c`: 49 steps each, **identical**. Re-run it with:

```python
import re
d=open('docs/BITSTREAM.md').read(); i=d.find('### A.3 omc_refine_order')
rows=re.findall(r'\|\s*(\d+)\s*\|\s*(Y|Cb|Cr)\s*\|\s*(\d+)\s*\|', d[i:i+6000])
pmap={'Y':0,'Cb':1,'Cr':2}; doc={int(a):(pmap[b],int(c)) for a,b,c in rows}
docl=[doc[k] for k in sorted(doc)]
s=open('src/alloc.c').read()
m=re.search(r'omc_refine_order\[\]\[2\]\s*=\s*\{(.*?)\n\};', s, re.S)
code=[(int(a),int(b)) for a,b in re.findall(r'\{\s*(\d+)\s*,\s*(\d+)\s*\}', m.group(1))]
assert docl==code and len(code)==49, (len(docl), len(code))
print('Annex A.3 == omc_refine_order[], 49 steps')
```

### GAP-3 — the reading-restricted decode ladder was never completed. **STILL OPEN.**

The session running `harness/spec_decoder.py` hit its limit inside the
verification ladder and **its results were never reported**. So:

> **UNKNOWN: whether `harness/spec_decoder.py` currently decodes any vector
> correctly. Do not assume it works. Do not assume it fails.**

That is v5.0's position and v5.1 does not change it — the v5.1 work was the
artifact fix, and re-running this exercise under the reading restriction cannot
be done by anyone who has read `src/codec.c`, which rules out this session by
construction. **C8 is therefore evidenced but not closed**, and this is the
honest statement of it. The first action on resume is the cheap, read-only one
`docs/HANDOFF_2026-08-04.md` §1.4 describes: establish ground truth by running
the existing decoder against the conformance vectors before writing anything.

**v5.1 makes that materially easier**: `delivery/conformance/` now carries six
**v5-class** vectors. Until v5.1 the folder held only pre-v5 vectors, every one
of which a v5 decoder refuses by design — so there was no v5 stream in the
delivery for an independent decoder to be tested against at all.

## What is NOT in this file

The "four specification mistakes" that `docs/EXECUTIVE_SUMMARY.md` credits the
exercise with finding and fixing. **Only GAP-1 is documented in the surviving
record**; the other three are asserted in the summary and are not itemised
anywhere in the tree. They are not reconstructed here, because inventing them
would be worse than recording their absence — which is the same rule
`docs/DANGLING_REFERENCES.md` applied to this file itself.

**This is an open documentation defect and is now tracked**: either the other
three are recovered from the session record, or `docs/EXECUTIVE_SUMMARY.md`'s
claim is reduced to what the tree can show.
