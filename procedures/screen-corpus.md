---
name: screen-corpus
description: Build the extraction queue — screen journals and reference databases en masse to find papers that could yield a clean_<ID> dataset, then append the survivors to paper_source.md. Use for literature sweeps, corpus building, or "find me papers that…". Do NOT use when a specific PMID is handed over for extraction; that is extract-paper.
---

# Screening the literature for extractable papers

**Scope.** This is for building the queue. Given a specific PMID, stop — use `extract-paper`
instead. Do not run these searches, do not go looking for companion papers, and do not append
anything to `paper_source.md` beyond what was asked for. Following a *citation out of a paper
already in hand* — to recover a TCR sequence that paper only names — is extraction work and is
always in scope there.

**Screening one journal at a time?** Use **`screen-journal`**, which is the operational procedure
built on this document — it runs the gates below against a single `J##` from `journals/journals.md`.
This file stays the corpus-level strategy: the funnel economics, the asymmetric extractability rule
and the search terms. Those rules live here only, and `screen-journal` cites them.

## The funnel

A full extraction costs on the order of 150–300k tokens. Screening a few hundred candidates by
extracting them would spend nearly all of that discovering that a paper has no usable data. So
the pile is narrowed by a series of gates, cheapest first, and expensive work only ever touches
survivors.

| Gate | What it does | Cost per paper |
|---|---|---|
| Harvest | queries below ∪ PMIDs cited by the reference databases ∪ citation expansion. Rejects nothing. | free |
| Metadata filter | drop reviews, editorials, errata, out-of-window | free, batched |
| Acquire | PMC full text + machine-readable supplements only (`.xlsx .csv .tsv .txt .zip`) | free, time only |
| **Probe** | script scans what was downloaded and sorts into yes / unclear / no | **zero model tokens** |
| Judge | only the *unclear* pile, batched ~20 papers per call, reading a compact card — never the paper | ~45 tokens |
| Promote | survivors get an ID in `paper_source.md` | — |

Target: screening the whole corpus should cost about what **one** extraction costs. Measured
scale — narrow queries over a 2-year window return 121, 15 and 49 PMIDs; a union of ~8 such
queries is a few hundred. This is hundreds, not thousands, so do not over-engineer the gates.

## What makes a paper extractable — the asymmetric rule

The obvious probe is wrong. **"Contains peptide strings AND CDR3 strings" would have rejected
a real paper.** Jones 2026 (PMID 41058174) contains zero CDR3 strings and zero `TRAV`/`TRBV` tokens; its
TCR sequences came from VDJdb and PDB, because the paper names its receptors and cites them.

The real condition is asymmetric:

- **Peptides must come from the paper.** A peptide table, in a supplement, a main table, or a
  figure. Nothing external supplies this.
- **TCR identity only has to be resolvable** — printed in the paper, *or* a named clone that
  resolves to a paired αβ entry in VDJdb/PDB/IMGT, *or* sequences in a cited paper.

So the probe hard-gates on peptides and soft-gates on TCRs, with named-clone resolution as a
parallel route to acceptance. The strongest single signal is **column density**, not token
counts: a spreadsheet column where ≥80% of non-null cells match `^[ACDEFGHIKLMNPQRSTVWY]{8,11}$`
with ≥20 distinct values is a peptide column. Prose token counting drowns in false positives —
`ACTIVATED` and `CANDIDATE` are 8–11 letters over the amino-acid alphabet, so an
uppercased-English stoplist is mandatory.

## Gate rules

- **Figure-only papers are auto-queued only on a cheap signal**: a figure caption that explicitly
  promises sequences ("CDR3α and CDR3β sequence alignments") **and** a machine-readable peptide
  table already present. Everything else figure-related is **parked in a list for human
  approval** — never auto-extracted, never silently dropped. Reading one figure costs 30–40k
  tokens, so vision is a budgeted step, not an automatic one.
- **"Reject" means "parked with a reason", not "discarded"** — until the probe's false-negative
  rate has been measured. The ~607 PMIDs cited by VDJdb are a free labelled positive set: run the
  probe over them and measure. Until the false-negative rate on known-good papers is low, nothing
  leaves the ledger permanently.
- **No PMC access is its own state**, not a rejection. Collapsing "no evidence" into "no access"
  silently discards the closed-access half of the corpus.
- **Papers already fully curated in a reference database** need no extraction — but note that
  those databases are positives-only and drop the paper's own threshold semantics, so mark them
  deferred rather than done. Papers in a database with **β chains only** are the highest-value
  targets in the corpus: a curator already verified the peptide side, and the missing half is
  exactly what `playbook/figures.md` §1 is good at recovering.
- **Never load the candidate ledger into context.** It is a queryable store; print a summary.
  `paper_source.md` stays the small human queue of papers that passed.

## Planned: a local TCR-name index

Not built yet, and worth building before the first large batch. One index built once from VDJdb +
PDB + IMGT, mapping clone name → `Va|Ja|CDR3a|Vb|Jb|CDR3b` + sources, turns the ~15-tool-call
sequence chase into a local lookup on *every* future paper. The same clones recur constantly
across this literature — 1G4, 1G4TS, DMF5, A6, JM22, LC13. It also doubles as the probe's
named-clone resolver, which is the rule above that saves papers of that shape.

---

## Search terms

Grouped so terms can be combined. **The platform axis is the strongest predictor that a
paper ships a reusable per-peptide table.**

**Platform / assay:** `PresentER` · `yeast display pMHC library` · `T-Scan`/`TScan` · `SABR` ·
`mammalian epitope display` · `combinatorial peptide library` / `positional scanning` ·
`deep mutational scanning` · `TetTCR-seq` · `dextramer`/`multimer sorting` · `barcoded pMHC multimer`

**Readout:** `log2 fold change depletion screen` · `NFAT reporter` · `CD69 upregulation` ·
`CD137`/`4-1BB` · `IFN-γ ELISpot` · `CD107a degranulation` · `cytotoxicity assay`

**Biology:** `TCR cross-reactivity` · `off-target recognition` · `on-target off-tumor toxicity` ·
`affinity-enhanced TCR` · `molecular mimicry` · `TCR promiscuity` · `neoantigen-specific TCR` ·
`autoantigen` · `CD4/CD8 co-receptor`

**Computational:** `TCR specificity prediction` · `TCR–pMHC binding prediction` ·
`protein language model TCR` · `TCR repertoire clustering` (GLIPH, TCRdist)

**MeSH:** `Receptors, Antigen, T-Cell` · `Peptide Library` · `Cross Reactions` ·
`Histocompatibility Antigens Class I` · `Immunotherapy, Adoptive`

**Mine databases for source papers** instead of searching blind — VDJdb, McPAS-TCR, IEDB,
TCR3d, ATLAS, and 10x dextramer application notes all carry per-entry citations, which is a
prefiltered list of papers that published usable pairs.

```
("T-cell receptor"[tiab] AND cross-reactiv*[tiab] AND (library[tiab] OR screen*[tiab]))
("peptide library"[tiab] OR "yeast display"[tiab]) AND (TCR[tiab] OR "T cell receptor"[tiab]) AND HLA[tiab]
(TCR[tiab] AND off-target[tiab] AND (toxicity[tiab] OR specificity[tiab])) AND 2020:2026[dp]
```

Use `datetype=edat` rather than `pdat` for the date window. Records get indexed late, and a
publication-date window silently misses them.
