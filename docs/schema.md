# The output contract — what `clean_<ID>` must look like

**The single definition of the output format.** It used to be written out in three places, which
is how they drifted. Extraction, screening and the audit all read this one file:
`procedures/extract-paper.md` produces it, `procedures/screen-journal.md` keys its locator notes
to these column names, `procedures/audit-provenance.md` verifies it, and `AGENTS.md` carries the
five invariants in short form because they have to stay loaded at all times.

---

## The `clean` sheet — exactly ten columns

One `.xlsx` per paper, sheet named `clean`, one row per unique (TCR clonotype, peptide) pair:

| Va | Ja | CDR3a | Vb | Jb | CDR3b | Antigen | MHC | pMHC_species | TCR_species |
|---|---|---|---|---|---|---|---|---|---|
| TRAV21*01 | TRAJ6*01 | CAVRPLYGGSYIPTF | TRBV6-5*01 | TRBJ2-2*01 | CASSYVGNTGELFF | AMDLIISTL | A*02:01 | Human | Human |

**Ten columns, never eleven.** That is what lets papers merge. Attribution, assay, outcome and
score all live elsewhere — see below — precisely so this sheet never widens. No `NA` in any column.

### Conventions

- **IMGT gene names.** Append an allele (`*01`) **only if the source states the allele.** If the
  source gives only `TRAV21`, write `TRAV21`. Never invent allele precision — which does mean
  different papers sit at different precision, and that is correct.
- **Bare CDR3 amino-acid strings**, no gene prefix. Every CDR3 begins with the conserved cysteine
  at IMGT position 104.
- **The peptide goes in `Antigen`.** `MHC` carries the allele without the `HLA-` prefix
  (`A*02:01`, not `HLA-A*02:01`). A class-II heterodimer that needs both chains is written
  `DQA1*05/DQB1*02` — see `playbook/judgement.md` §18.
- **`Human` and `HomoSapiens` are the same term.** Either spelling is fine in the species columns;
  no normalization needed.
- **`pMHC_species` describes where the peptide actually comes from** — `Human`, `Synthetic`,
  `CMV`, `HIV-1`, `Bacterial`. Decided **once per peptide *source***, never peptide by peptide.
  The vocabulary is open by necessity; flag a new value to the user. `playbook/judgement.md` §10
  and §17 are where this gets mis-applied.

### `Va`, `Ja` and `CDR3a` are mandatory

**An extraction that cannot supply the α chain is not worth producing.** A paper that looks
β-chain-only is a signal to dig harder, not to emit `NA`. `playbook/figures.md` §1 covers where
the α chain hides and how to get it out.

Beyond being required, the α chain **resolves identity ambiguity that β cannot.** CDR3β is not a
unique TCR key: distinct receptors — especially engineered variants sitting alongside the
wild-type panel they came from — can share a CDR3β while carrying different α chains and
*contradictory* binding labels. Deduplicating on β alone silently merges them.

**So dedupe on at least (`CDR3a`, `CDR3b`, `Antigen`)**, and assert that key is unique across the
paper's panel before deduplicating (`playbook/checks.md` **C5**).

---

## The `provenance` sheet — where every value came from

Built by `lib/provenance.py`. **Never hand-roll these columns**: four papers hand-rolling them
produced four incompatible vocabularies, and a merged table could then not be filtered by source
at all.

Per clean row it emits a `<column>_source` for all ten schema fields, plus:

| column | values |
|---|---|
| `origin` | `file` · `figure` · `text` · `external`, joined with `+` when a row draws on several |
| `extrapolated` | derived — `no` only when every field came from a machine-readable file of *this* paper |

What each origin means:

- **`file`** — a machine-readable supplement of **this** paper (`.xlsx` / `.csv` / `.tsv`).
- **`figure`** — read off a figure image or panel.
- **`text`** — this paper's prose: Methods, Results, a main-paper table, a figure legend.
- **`external`** — another paper, VDJdb, PDB, IMGT, or a data repository.

**Anything read off a figure or a main-paper table is extrapolated** and must cite its exact
location (`Fig. 2a`, not "a figure"). Only `file` is non-extrapolated — a main-paper table is
prose someone typeset, not a file you can re-read mechanically.

`Prov.row()` **raises** if any of the ten fields was never attributed, so a missing source fails
the build instead of shipping blank. `check_provenance(clean, prov, "<ID>")` is **C12** in
`playbook/checks.md`. Use `Prov` for row-by-row scripts, `finalize()` for column-wise ones.

C12 checks attribution is **present**. `procedures/audit-provenance.md` checks it is **true** —
different jobs, run at different times.

---

## Everything else a paper produces

Per paper, named by its `ID` (`AGENTS.md` holds the indexing rules):

| file | holds |
|---|---|
| `clean_<ID>.xlsx` | sheets `clean` + `provenance` + `source_notes` |
| `clean_<ID>_provenance.csv` | the same `provenance` frame, as CSV |
| `clean_<ID>_<what>.csv` | anything that does not fit the ten columns |

`source_notes` is prose, one row per field group: the judgement calls, the threshold quoted from
Methods, what was dropped and why. It ships **inside the workbook**, which is where a reader will
actually find it — not in the build script's comments.

**Keep assays in separate files.** A functional activation assay and a binding screen are
different evidence, and the schema has no column to tell them apart once merged.

---

## Known gaps in this format

Both bite on merge. Decide before extending:

- **No outcome column**, so the format is implicitly positives-only. Library screens measure orders
  of magnitude more non-binders than binders, and those are the most valuable rows for training.
  They live in `clean_<ID>_*` companions with an explicit `Binding_Outcome` until the schema gains
  one.
- **No provenance column in `clean` itself.** No PMID, assay or score survives into the ten
  columns. Once several papers merge, rows become untraceable and cross-source duplicates
  undetectable — the same clonotype arrives from several papers via different assays. The
  companion provenance CSV is the only thing that makes a pooled table auditable.

A third pressure is now visible: `pMHC_species` has outgrown `Human`/`Synthetic`
(`playbook/judgement.md` §17). Fixing that vocabulary is a schema decision, not a per-paper one.

**Scale note.** `.xlsx` caps at 1,048,576 rows and screen data routinely exceeds that once
negatives are included. Use CSV or Parquet at that scale.
