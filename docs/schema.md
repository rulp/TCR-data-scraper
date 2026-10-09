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
- **`Antigen` is the 20 standard amino acids and nothing else, which puts chemically modified
  epitopes out of scope.** A peptide whose activity depends on a residue the alphabet cannot
  write — citrulline, a phospho-serine, a methylated lysine — does not get a row, and is not
  back-mutated to its parent residue to obtain one. Deamidation is *not* affected: Q→E and N→D
  give standard residues. `playbook/judgement.md` §29 has the boundary and the cost.
- **Murine MHC keeps its locus prefix: `H2-Db`, `H2-Kb`, `H2-IAg7`** — one token, hyphen after
  `H2` and nowhere else, whatever the paper writes. Unlike `HLA-`, the prefix cannot be dropped:
  a bare `Db` collides with the human DP/DQ/DR series, and `H-2Db` would be the only value in the
  column whose hyphen falls inside the locus name. Class II follows the same shape, so the mouse
  heterodimer is `H2-IAb`, not `IAb`. There is no `*` allele field to append.
- **`Human` and `HomoSapiens` are the same term.** Either spelling is fine in the species columns;
  no normalization needed.
- **`pMHC_species` describes where the peptide actually comes from.** Decided **once per peptide
  *source***, never peptide by peptide. The vocabulary is open by necessity, so **flag a new value
  to the user before emitting it** — that is the only gate on it. `playbook/judgement.md` §10 and
  §17 are where this gets mis-applied.

  In use so far, every one of them user-approved: `Human` · `Mouse` · `CMV` · `EBV` · `VZV` ·
  `HBV` · `HCV` · `Human coronavirus` · `SARS-CoV-2` · `Influenza A virus` · `Influenza B virus`.
  `Synthetic` and `Bacterial` are reserved for a library peptide and a bacterial proteome and have
  not been needed yet. Two conventions this list encodes, both worth copying:

  - **Name the virus, not the disease or the serotype family**, at the precision the paper itself
    uses. `SARS-CoV-2` and `Human coronavirus` are deliberately separate values, because the
    seasonal hCoV epitopes in a cross-reactivity panel are a different peptide source from the
    pandemic strain's and the papers treat them that way.
  - **A host-proteome peptide takes the host**, so a somatic mutant of a human gene is `Human` and
    a murine self or neoantigen is `Mouse` — not the tumour, the cell line or the disease.

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
(`playbook/judgement.md` §17). It stands at eleven values over sixteen papers and will keep
growing, because it is a free-text species label doing the work of a controlled vocabulary —
nothing stops `Human coronavirus` and `HCoV-OC43` coexisting, or a merge treating them as
unrelated. Fixing it is a schema decision, not a per-paper one: the exit is a reference list in
this file that values are checked against, with the user's approval as the only way to extend it.
Until then the approval step above *is* the control, and it only works if it is actually asked.

- **No modification field on `Antigen`**, so modified epitopes are excluded rather than
  represented (§29, decided 2026-10-08). Unlike the two gaps above this one is a deliberate
  narrowing, not an oversight — but it has the same shape, and the same exit: a field here would
  let the excluded papers back in, and they are listed by PMID in the journals' `## Failed`
  tables so they can be found without a re-sweep.

**Scale note.** `.xlsx` caps at 1,048,576 rows and screen data routinely exceeds that once
negatives are included. Use CSV or Parquet at that scale.
