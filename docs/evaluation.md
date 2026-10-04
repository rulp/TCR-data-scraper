# Evaluation — how to split this data for training

Read on demand. Nothing here is needed to extract a paper or to screen the literature.

**These headings are deliberately named, not numbered.** `§N` in this project always means a
`REPORT.md` section; this file stays out of that namespace so a citation can never be ambiguous.

---

## Where the format falls short

Moved — the gaps in the `clean_<ID>` schema are part of the output contract and live with it, in
`docs/schema.md`. They were written out here and in the extraction procedure as well, and the
three copies had started to drift.

---

## Evaluation note

When splitting data for training, **split by TCR clonotype, not by row.** Generalization to
a new TCR has been shown to track functional distance — divergence in peptide recognition
profile — rather than CDR3 sequence similarity, so random row splits badly overstate
performance on this kind of data.

Wang 2026 (PMID 42129507) is the worked example: it ships the authors' own `train`/`valid`/`test`
assignment, which an extraction should carry into the provenance CSV as `published_split`. Note that their split is per *peptide* within a TCR, so
it measures peptide generalization, not generalization to an unseen receptor; the paper's own
leave-one-TCR-out analysis is the one that speaks to the latter. **Do not reuse
`published_split` as a clonotype-level split.**
