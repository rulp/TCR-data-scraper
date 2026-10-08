# REPORT — troubleshooting playbook for paper extractions

Problems hit while extracting published TCR datasets, with the solution where one exists.
**This file is an index.** The content lives in `playbook/`, split so a session loads only the
part its task needs. Section numbers are permanent and never reused, so every existing citation
— in build scripts, in `source_notes` sheets of already-shipped workbooks — still resolves to
exactly one place.

| § | Topic | Lives in | Load it when |
|---|---|---|---|
| 1 | TCR sequences exist only inside a figure image | `playbook/figures.md` | transcribing a figure |
| 2 | Validating a figure transcription | `playbook/figures.md` | transcribing a figure |
| 3 | Labels in a figure, values in a file | `playbook/figures.md` | transcribing a figure |
| 4 | Bulk data behind a Google Drive interstitial | `playbook/fetching.md` | acquiring raw files |
| 5 | Placeholder and control strings in positive sets | `playbook/judgement.md` | **every extraction** |
| 6 | CDR3β collisions between distinct TCRs | `playbook/judgement.md` | **every extraction** |
| 7 | Row limits | `playbook/fetching.md` | emitting a large screen |
| 8 | Local tooling | `playbook/fetching.md` | environment trouble |
| 9 | Control labels are sequences to resolve | `playbook/judgement.md` | **every extraction** |
| 10 | `pMHC_species` is a property of the source | `playbook/judgement.md` | **every extraction** |
| 11 | IGNORE — gated data repositories | `playbook/fetching.md` | before retrying a gated download |
| 12 | IGNORE — supplementary documents from PMC | `playbook/fetching.md` | before retrying a PMC document |
| 13 | Why PMC documents fail — the proof-of-work gate | `playbook/fetching.md` | a PMC supplement is the blocker |
| 14 | Screen tables keyed by an opaque peptide ID | `playbook/judgement.md` | a screen has no peptide column |
| 15 | Papers that state no hit threshold at all | `playbook/judgement.md` | **every extraction** |
| 16 | A CDR3 that passes the alphabet check but is junk | `playbook/judgement.md` | **every extraction** |
| 17 | `pMHC_species` values beyond Human and Synthetic | `playbook/judgement.md` | **every extraction** |
| 18 | MHC class II papers break class-I assumptions | `playbook/judgement.md` | the paper is CD4+ / HLA-II |
| 19 | Resolving a PMID; what the PMC APIs give you | `playbook/fetching.md` | screening, or acquiring from PMC |
| 20 | One receptor, several papers, several names | `playbook/judgement.md` | **every extraction** |
| 21 | A paper with no T cell receptor in it at all | `playbook/judgement.md` | a screen card flags no TCR evidence |
| 22 | Peptides in the paper that are not the paper's peptides | `playbook/judgement.md` | **every extraction**; screening |
| 23 | A receptor whose binding does not depend on the peptide | `playbook/judgement.md` | SPR/structure with no activation |
| 24 | IGNORE — GEO accession pages behind a reCAPTCHA | `playbook/fetching.md` | checking a GSE/GSM from a script |
| 25 | One deposit, several datasets — answer the question you asked | `playbook/fetching.md` | a deposit or archive is the blocker |
| 26 | A data-quality flag encoded as text colour | `playbook/judgement.md` | parsing a table out of a PDF |
| 27 | An epitope cited by position, never printed | `playbook/fetching.md` | the antigen is a range, not a sequence |
| 28 | The V and J genes are not in the paper | `playbook/judgement.md` | a mandatory gene column has no stated value |
| 29 | Chemically modified epitopes are out of scope | `playbook/judgement.md` | an epitope carries a non-standard residue |
| 30 | Both chains published, and never paired | `playbook/judgement.md` | the supplement lists alpha and beta separately |
| 31 | A deposit publishing the strict IMGT CDR3, not the junction | `playbook/judgement.md` | CDR3s arrive without their leading cysteine |
| 32 | Reconstructing an analysis: check the paper's own count first | `playbook/judgement.md` | the specificity call has to be recomputed |
| — | Decisions that recur | `playbook/judgement.md` | **every extraction** |
| — | The checks, as runnable assertions (C1–C13) | `playbook/checks.md` | **before writing any output** |
| — | Verifying recorded sources are real | `audit.py` + `procedures/audit-provenance.md` | after a batch of extractions |

**§1–§10, §13–§23, §25, §26 and §29–§32 are solved or have a stated workaround** — reuse the method. **§11, §12 and
§24 are marked IGNORE**: they cannot be resolved without a human, so do not burn time
re-attempting them.

`playbook/judgement.md` is mandatory for every extraction and holds the *reasoning*;
`playbook/checks.md` holds the matching *tests* and is loaded at Step 4, before anything is
written. `figures.md` and `fetching.md` are lookup. `docs/schema.md` holds the output contract itself and
is not part of this numbering.

When a section's content is a test, it belongs in `checks.md`; when it is a decision, it belongs
in `judgement.md`. Sections keep one number across both.

## Adding to this file

`AGENTS.md` requires a pass over this file after **every batch of papers**. Add a section for
each problem that could not be solved inside the extraction, with what was tried and what the
next session should do instead. Append the next free number, add its row to the table above, and
never renumber — build scripts and shipped `source_notes` sheets cite these numbers by value.

`docs/evaluation.md` uses named headings, not numbers, so it stays out of this namespace; `§N`
unqualified always means a section of this file.
