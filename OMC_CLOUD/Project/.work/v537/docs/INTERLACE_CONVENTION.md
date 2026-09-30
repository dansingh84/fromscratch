# Interlaced video convention — DEFERRED (re-based shelf design, not scheduled, not implemented)

> **STATUS in v5.0: unchanged.** Nothing in the temporal rebuild or the adversarial repairs touches this convention.


Status: **Deferred by product decision, 2026-07-28; signaling re-based
2026-08-03 to v4.7 rev8 / bitstream minor 7 header currency (still not
implemented).** Interlace is a legacy
format with no presence in the greenfield deployments OMC targets;
implementing and validating it (including sourcing interlaced footage and
interlace-aware review) would spend effort on a shrinking segment and add
permanent silicon/validation surface. This document is retained as a
complete, costed design so the sales answer to a procurement checklist is
"designed, documented, available on request" rather than "no" - and so a
future implementation is a wrapper-layer retrofit, not a redesign. Since the
original decision, bytes 26-27 have been taken into use by the core codec
(byte 26 scan_type reserved-0, byte 27 pixel_flags — see BITSTREAM.md
9.3-9.5), so the signaling in section 3 has been re-based onto the current
header. The ONLY active obligation it leaves on the codebase: stream-header
bytes 28-31 remain reserved-as-zero, byte 26 remains reserved-0
(scan_type), and byte 27 bits 3-7 remain reserved-0 (already true, zero
cost). No code implements this;
nothing in this document changes the core codec (src/ coding paths). It is
written so the entire feature can live in the I/O wrapper and stream-header
metadata, with the progressive coding core untouched and provably unchanged
(golden-stream byte-compare gates).

## 1. Model: field-as-independent-picture

Interlaced content is coded exactly the way JPEG XS codes it in deployed
ST 2110-22 systems (RFC 9134): **each field is an independent coded
picture.** No new coding tools, no cross-field filtering, no field/frame
adaptivity. A "frame" of 1080i59.94 is two coded pictures (top field,
bottom field) at twice the frame cadence.

- Temporal prediction: fields are pictures; the default posture for
  interlaced streams is **stateless (refresh R = 1)** — matching JPEG XS
  like-for-like and avoiding the half-line vertical offset that
  opposite-parity prediction would introduce. Same-parity prediction
  (field N from N−2) is explicitly OUT of this proposal (it would need a
  second reference store and core changes).
- All existing per-picture machinery (CBR slices, CRC, concealment,
  fill/gain, modes) applies to each field unchanged.

## 2. Geometry: the 540-line problem

Field heights must satisfy the existing constraint (multiple of slice_h).

| format | field height | slice_h 8 | action |
|---|---|---|---|
| 480i | 240 | OK | none |
| 576i | 288 | OK | none |
| 1080i | 540 | 540/8 = 67.5 — **not integral** | pad to 544 |

**Padding rule (normative in 4.2):** a field whose height H_f is not a
multiple of slice_h is coded at H_c = next multiple of slice_h (1080i:
544, slice_h = 8). The encoder fills rows H_f..H_c−1 of every plane by
**edge replication of row H_f−1** before coding; the decoder crops output
to H_f. Replicated rows are smooth extensions — measured expectation is
<1% of the field's rate (to be verified in Phase 2 with the padding rows'
actual coded cost).

Rationale for replication over black/gray padding: no artificial edge at
the crop boundary (an edge would ring into the visible rows through the
wavelet), and no wasted bits fighting a step.

## 3. Signaling: stream-header bytes (re-based, 2026-08-03)

**Re-based shelf design — supersedes the original byte layout; still not
implemented.** The 32-byte stream header now uses bytes [0, 28): byte 26
is scan_type (currently always written 0 = progressive) and byte 27 is
pixel_flags (bit 0 RCT, bit 1 correlated fill tile at minor >= 5, bit 2
STATIC fill tile at minor >= 7, bits 3-7 reserved 0 — authority:
BITSTREAM.md 9.3-9.5). Bytes [28, 32) are written as zero and ignored by
all existing decoders. Re-based proposal:

| byte | field | values |
|---|---|---|
| 26 | scan_type | 0 = progressive (default, back-compatible), 1 = interlaced field stream, top field first, 2 = interlaced field stream, bottom field first |
| 27 | pixel_flags | unchanged (in use by the core codec; not touched by this proposal) |
| 28–29 | display_height (LE u16) | true field height before padding; 0 = equal to coded height (progressive streams keep 0) |
| 30–31 | reserved | 0 |

Field order is carried as scan_type code points (1/2) rather than a
separate byte, since byte 27 is no longer available; alternatively a
future implementation may put field_order in a byte 28 bit and keep
scan_type = 1 — to be fixed when the feature is scheduled (display_height
would then move to bytes 29-30).

Back-compatibility: a current (minor 7) decoder reading an interlaced
stream decodes every field correctly as a picture (byte 26 nonzero and
bytes 28+ are ignored today); it merely doesn't crop or weave. An
interlace-aware decoder reading any existing stream sees scan_type 0 =
progressive, identical behavior. The minor version bumps to a future
minor > 7 so conformant implementations know the fields are meaningful.

Frame index parity: even coded-picture indices are first fields, odd are
second fields, in field_order order. The fill animation offsets already
key on the coded-picture index, so fill decorrelates across fields with no
change.

## 4. What is explicitly NOT in this proposal

- Opposite-parity or same-parity temporal prediction (core change; no
  incumbent parity gap to close — JPEG XS is field-intra too).
- Frame-mode coding of interleaved fields (vertical filtering across
  parities smears combing into every band; rejected).
- PsF (progressive segmented frame): carried as plain progressive; needs
  no support.

## 5. Phase-2 validation battery (gate before "supported" is claimed)

1. Golden-stream byte-compare: every existing progressive test stream
   byte-identical after the wrapper lands (proves core untouched).
2. Field round-trip: split → encode → decode → crop → weave equals a
   field-accurate reference path; parity/order tests both settings.
3. Padding cost measurement on real 1080i content (expect <1% of rate).
4. Generation chains on field sequences (A4 gate at field cadence).
5. Slice-loss recovery per field, including loss in padding slices.
6. Spec decoder extended to crop/report scan metadata; byte-exact on
   interlaced streams.
7. Real interlaced footage reviewed on an interlace-aware display path
   (combing is the "unnoticed until much later" artifact class; synthetic
   checks are insufficient).

## 6. Decision record

- 2026-07-28: **deferred** (mandate holder). Not in scope for the first
  hardware target. Reserved bytes 26-31 stay reserved so the design remains
  a compatible retrofit. Revisit only on concrete customer demand, with the
  Phase-2 battery in section 5 as the unchanged acceptance bar.
- 2026-08-03: **re-based, still deferred.** Bytes 26-27 entered core use in
  v4.7 rev8 (byte 26 scan_type reserved-0, byte 27 pixel_flags); section 3
  re-based onto scan_type code points / bytes 28-31, minor bump target
  changed from 2 to a future minor > 7. No implementation, no scope change.
