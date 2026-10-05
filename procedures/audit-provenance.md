---
name: audit-provenance
description: Verify that every row in every clean_<ID>.xlsx really comes from the source it records. Runs audit.py, dispatches blind figure transcriptions, investigates contradictions, writes AUDIT.md. Use for "audit the data", "check the sources are real", or after a batch of extractions. Not for building or extracting.
---

# Auditing recorded sources

`checks.md` **C12** asserts an attribution is *present*. This asserts it is *true*. The audit
imports nothing from any build script: it re-reads `raw/`, re-fetches external records, and
re-transcribes figures.

```bash
uv run --with pandas --with openpyxl --with pypdf python audit.py            # everything
uv run --with pandas --with openpyxl --with pypdf python audit.py --papers <ID>
```

Inside a venv built from `requirements.txt` the same commands are just `python audit.py …`
(`SETUP.md`). `audit.py --help` lists every flag, and it refuses an unknown one.

It writes `AUDIT.md` and exits non-zero if anything is **contradicted**. It never edits
`clean_*.xlsx` or `clean_*_provenance.csv`.

## Verdicts

| verdict | meaning | what to do |
|---|---|---|
| `verified` | found where the source says | nothing |
| `mislocated` | real, but not in the file cited | fix the **source string**, not the value |
| `judgement` | an annotation decision, not a quotable string | nothing — see below |
| `unverifiable` | no machine route; the reason is recorded | read the reason; some are fixable |
| **`contradicted`** | claimed to be in the paper's materials, and is nowhere | **investigate before anything else** |

**`pMHC_species` and `TCR_species` are always `judgement`.** `Human`, `Mouse`, `Chicken` appear
nowhere to match against — they record a decision about provenance, not a string from the paper.
The audit covers the other eight columns strictly. Do not report the corpus as "fully verified";
say which columns were verified.

## The blind figure protocol

A value that exists only in an image can only be checked by reading the image again. That is worth
nothing if the reader already knows the answer, so it runs in two phases:

1. `audit.py --figures` writes a task card per figure to `audit/tasks/`. **The card names the
   image and what to transcribe, and nothing else.** It never contains the recorded value.
2. Dispatch **one subagent per card**, 3–5 in parallel — they are read-only and independent. Give
   each agent only its card. Each writes its reading to `audit/reads/<id>.json`. With no subagents
   available, do the readings one at a time in a session that has not seen the workbook; the
   requirement is blindness, not parallelism.
3. Re-run `audit.py`. It diffs each transcription against the recorded value and assigns verdicts.

**Never paste a recorded value into a transcription prompt, and never let the agent read the
workbook, the provenance CSV, the build script, or the paper's text.** An agent shown the answer
confirms the answer. If a prompt leaks the value, that figure's verdict is void — delete the read
and redo it.

Readings are cached. Re-running the audit reuses `audit/reads/` and does not re-dispatch agents;
delete a read to force a fresh transcription.

## Investigating a contradiction — do this yourself

Never delegate it, and **never edit `clean` data to make the audit pass.** A contradiction has at
least four causes, and they have different fixes:

- **The source string is wrong** — the value is real but cited to the wrong place. Fix the string.
- **The value is wrong** — a transcription or typing error. Fix the value, and say so in
  `source_notes`.
- **The source was reissued** — the publisher or database changed the record under us. Record what
  it used to say, what it says now, and which one the row reflects. This is a `REPORT.md` section.
- **The audit is too literal** — the same fact spelled differently. Observed and already handled:
  `DRB1*11:01` vs `DRB1*1101`, and a table writing `J43` where the schema writes `TRAJ43`. If you
  find a new class, fix `variants()` in `audit.py` rather than the data.

Decide which, state the evidence, then act. "I re-ran it and it passed" is not an investigation.

## Prove it can fail

An audit that has only ever passed has demonstrated nothing. Before trusting a run after any change
to `audit.py`, re-run the negative control: copy a paper folder to a scratch directory, corrupt one
CDR3 residue, swap one peptide for another paper's, and repoint one source string at a file that
does not hold the value. Then:

```bash
uv run --with pandas --with openpyxl --with pypdf python audit.py --root <scratch> --papers <ID>
```

It must report the first two as `contradicted` and the third as `mislocated`, and exit non-zero.
The real workbooks are never touched; delete the scratch copy afterwards.
