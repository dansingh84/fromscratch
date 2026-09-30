# Pre-registered predictions — baseband interchange matrix
Written 2026-08-17, BEFORE any baseband matrix run, on build: T5 tree at
commit d067333 plus the gamut-report instrumentation (verified hash-neutral
against the recorded §10.3 md5: 1c81c776... reproduced).

Claim under test: "pad-free geometry + in-gamut content ⇒ pure-baseband
generation exactness" — i.e. the CDR's extra information over legal-range
display baseband is load-bearing ONLY through (a) pad rows and (b)
out-of-legal-range committed samples, and the 2048 bias is cosmetic.

P1. Every pad-free cell of the §10.3 matrix (14 cells: all 720p, all
    2048×1152 including both option rows, 4096×2160 sh16, both 4480×1856)
    PASSES genchain_bb at the same generation depths as §10.3, with
    measured oob=0.
P2. The two long chains re-run over baseband (720p 20 generations,
    2048×1152 12 generations at 0.5 bpp) PASS with oob=0.
P3. Every padded cell (1080-as-1088, 2160-as-2176@sh32) FAILS baseband on
    the current build with fail=pixels-gen2 (the pad rows are not
    re-derivable from cropped baseband). [To be run as the negative arm
    before the pad fix; expected to flip to PASS after minor 11.]
P4. The rail-heavy synthetic clip (hard-clipped whites/blacks, full-range
    ramp) measures oob>0 at 10-bit and FAILS baseband at pixels-gen2 while
    PASSING the same configuration over CDR interchange (liveness arm: the
    harness can see a baseband break; the failure is confined to the gamut
    condition, not the harness).
Falsification branches, armed:
- Any pad-free in-gamut cell failing ⇒ a third load-bearing difference
  exists; trace it before writing the section (candidate suspects: display
  projection ordering vs boundary blend at barrier phases; RCT rounding;
  mid-grey init of unwritten planes).
- Rail clip PASSING baseband with oob>0 ⇒ the oob counter or the clip is
  not measuring what it claims; fix the instrument first.
- Rail clip measuring oob=0 ⇒ the clip is not rail-heavy enough; harden it
  before drawing any conclusion (a liveness arm that cannot fire proves
  nothing).
