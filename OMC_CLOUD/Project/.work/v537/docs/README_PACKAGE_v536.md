# OMC-1 v5.3.6 — package contents (2026-09-08)
- `codec/` — the v5.3.6 source tree (encoder, decoder, tests, tools, harness, docs, conformance vectors) **and the built Linux x86-64 binaries in `codec/bin/`** (md5 in `codec/BINARIES_20260908.md5`; rebuild with `make all`, run the suites with `make test`). Start with `codec/docs/CHANGES_v5_3_6.md` (what landed, what was not and why, known defects, every gate) and `codec/docs/V536_ADVERSARIAL_CHECK.md` (the review of this package: ledgers vs tree, docs vs code, build-from-zip).
- `project_docs/` — `LEDGER_SANDBOX_v2.md` (the working ledger; read the newest H.* hand-off header first), `LEDGER_v5_3_5.md` (the development ledger since v5.3, with the v5.3.6 section), `WORK_QUEUE.md`, `LANDING_REGISTER.md`, `UNIMPLEMENTED_SUCCESSES.md`; `findings_ledgers/` — the five agents' findings ledgers and the ledger of the outside adversarial review (the inputs to this release); `historical/` and `root_docs/` as in v5.3.5.
- `expert/` — the higher expert's reply to memo 007, the memos to the codec expert and the legal team, the IP review; `external_review_v535/` — the outside adversarial review of v5.3.5 (three documents, as text).
- `agent_success_ledgers/`, `agent_notes/`, `agent_diffs/` — the five agents' ledgers, instruments and every delivered diff.
- `communication_agent_messages/`, `communication_memos_to_agents/` — the full memo traffic both ways.
- `prompts/` — the owner's task prompts. `logs/v536_gates/` — the gate scripts and outputs for this build.
- `queued_diffs/` — accepted code NOT in v5.3.6 (Agent 1's region-search diffs; see CHANGES §C).
Footage, decoded pictures and images are excluded throughout; the only streams are the conformance vectors.
