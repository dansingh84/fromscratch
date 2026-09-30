## 16. F2c — OMC-TF: the inventory, and a correction to the premise

*Read-only inventory of the frozen base `.work/v537`. No tree was modified for this section.*

### 16.1 The premise needs correcting before the job is scoped

The instruction says OMC-TF "is still compiled and linked into the shipping
tree". **It is not.** The filter, its offline tool, its header and its test were
deleted on 2026-09-06 under the same legal review, and the tree records it in
three places:

* `src/config.c:182` — `[G-TFDEL] The OMC-TF rate validator lived here (env OMC_TF).
  OMC-TF was removed from the codec with the old temporal engine (T5) and its
  offline tool, filter and test were deleted 2026-09-06 (legal review action 3).`
* `src/codec.c:2620` — `[G-TFDEL] omc_tf_mode deleted 2026-09-06 with the offline
  OMC-TF tool (legal review action 3); the header's tf_mode bits stay and must be zero`
* `docs/CHANGES_v5_3_5.md:14` — the ledger row: *"OMC-TF deleted: `src/tfilt.c`,
  `tests/test_tf.c`, `tools/omc_tf_tool.c`, `include/omc_tf.h`, Makefile targets,
  `OMC_TF` validator, `omc_tf_mode`"*, marker `[G-TFDEL]`, ledger ref **S5.84**.

I searched for any surviving implementation — `omc_tf`, `tfilt`, `tf_apply`,
`tf_gather`, `tf_strength`, `temporal filter` across `src/`, `include/`,
`tools/` — and **every hit in compiled code is a comment saying it was removed**.
There is no `src/tfilt.c`, no `include/omc_tf.h`, no `omc_tf_mode` symbol.
**There is no OMC-TF code to delete.** F0's shape — rip out a live normative
path, prove byte-identity — does not apply, because nothing executable changes.

### 16.2 What actually remains

| remnant | where | what it is |
|---|---|---|
| `cfg.tf_mode` field | `include/omc1.h:199` | a struct field documented "REMOVED (T5) … Must be 0; streams with the bits set are rejected" |
| header write | `src/codec.c:471` | byte 27 bits 5–6 written 0, with the T5 comment |
| header validate | `src/codec.c:509` | bits 5–6 and bit 7 must be zero, else header error |
| dead envelope comment | `src/config.c:155–181` | 27 lines describing the deleted filter's rate envelope, its PSNR table and `harness/tf_rate.py` |
| tool assignment | `tools/omc_enc.c:421–425` | comment + `cfg.tf_mode = 0;` |
| tool comment | `tools/omc_dec.c:80` | "omc_dec_create() takes the filter state from cfg.tf_mode" — describes behaviour that no longer exists |
| doc section | `docs/BITSTREAM.md:783–814` | §"v4.8 (minor 8) — output conversion and the in-loop temporal filter" |

### 16.3 The one finding that is worth acting on

`docs/BITSTREAM.md:808–814` still carries a **normative instruction to apply the
deleted filter**:

> **`tf_mode` is normative, not advisory.** A decoder MUST apply the signalled
> filter strength. The filter is in-loop, so a decoder that ignored it would
> reconstruct a different picture from the encoder's own reference and drift
> further with every frame, breaking `rt = 0` (C4).

Thirteen lines earlier the same document says the field **MUST be 0** and a
nonzero value **is a header error**. The specification therefore tells an
implementer both that a nonzero `tf_mode` must be rejected and that it must be
obeyed. The code is unambiguous — `src/codec.c:509` rejects — but a third-party
decoder written from the document could implement the paragraph instead of the
table. **That is the interoperability hazard in this item, and it is a
documentation defect, not a code one.**

### 16.4 What F2c reduces to, and what I have not done

The remaining work is housekeeping: delete the `tf_mode` field and its two tool
assignments, delete the dead envelope comment, rewrite `BITSTREAM.md` §v4.8 so
it documents **reserved bits that must be zero** and drops the "MUST apply"
paragraph. The header bits themselves **stay reserved and stay validated** —
removing the rejection would let a v4.8 stream decode silently, which is exactly
the hazard the existing comments warn about.

**I have not made that change.** F2c as instructed assumes code that is not
there, and I am not going to manufacture a deletion to fit the instruction. The
byte-identity gate would be vacuously green because nothing executable moves —
and a vacuous green is the failure mode this project has already been bitten by.
**The decision I am handing back: whether the reduced job is worth its own diff,
gate and package, or whether it should ride with the transform rebuild's
documentation pass.** I have gone on to the transform oracle in the meantime.

### 16.5 Makefile note (as instructed, noted only)

`Makefile:11` defines a single `SRC` list used to link every binary, which is
why `colour.c` is linked into `omc_dec`. Splitting it is a Makefile change; I
have made none.
