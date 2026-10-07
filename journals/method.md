# How the journal list was built

**Read-once provenance.** Nothing here is needed to sweep a journal — that is
`procedures/screen-journal.md` — or to pick the next one, which is `journals/journals.md`. This
file exists so the list's numbers can be reproduced and challenged instead of trusted.

## What counts as credible

Judged operationally — by whether a paper from this venue can actually be extracted — not by
reputation or impact factor:

1. **MEDLINE-indexed**, so it is reachable by `[ta]` and has a stable PMID.
2. **Mandates a data-availability statement.** This is the single strongest predictor that the
   per-peptide table exists at all.
3. **Hosts supplementary files at a stable URL**, or deposits to a repository that does.

A high-volume venue that meets all three stays on the list at low priority rather than being cut
on prestige: it is still extractable, it is just a worse use of a sweep until the better ones are
done.

## The harvest query

Broad on purpose. The probe, not the search, is what rejects papers — a narrow query cannot be
audited for what it silently dropped.

```
("T cell receptor"[tiab] OR TCR[tiab])
  AND (epitope[tiab] OR peptide[tiab] OR pMHC[tiab] OR HLA[tiab] OR antigen[tiab])
  NOT review[pt]
  AND "<NLM [ta]>"[ta]
# the window is NOT a term clause -- it is passed as parameters:
#   &datetype=edat&mindate=<from>&maxdate=<to>
```

**The window is `edat`, never `[dp]`.** `procedures/screen-corpus.md` is the rule: records get
indexed late, so a publication-date window silently misses exactly the newest papers — the ones a
sweep is run to find. `datetype` only takes effect alongside `mindate`/`maxdate`, which is why the
window sits in the parameters rather than the term. The two agreed on `[dp]` until 2026-10-06 and
were consistently wrong together; on J01 over 2024–2026 both forms return 84, because a window
whose end is in the future gives late indexing time to catch up — the divergence appears at the
leading edge, which is where it matters.

Reproduce a count:

```bash
curl -sS -G "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&rettype=count&retmode=json&datetype=edat&mindate=2024/01/01&maxdate=2026/12/31" \
  --data-urlencode 'term=("T cell receptor"[tiab] OR TCR[tiab]) AND (epitope[tiab] OR peptide[tiab] OR pMHC[tiab] OR HLA[tiab] OR antigen[tiab]) NOT review[pt] AND "Nat Commun"[ta]' 
```

**`Broad`** is that query's count. **`Plat`** is the same query with the peptide/epitope clause
replaced by the platform/assay terms from `procedures/screen-corpus.md` (`yeast display`,
`peptide library`, `T-Scan`, `PresentER`, `SABR`, `dextramer`, `cross-reactiv*`, …).

**`Plat` ranks, it never rejects.** Across all 40 journals it returns only 55 papers for
2024–2026, and returns **0** for Cell, Nature, Science and Immunity — venues that demonstrably
publish this work. It is a density hint, nothing more.

### Recall check — why `Window` is a column

Run 2026-10-03 against four papers known to carry extractable TCR–pMHC data. The query found
**4 of 4** when the window covered them:

| Paper | PMID | Journal | Result |
|---|---|---|---|
| Jones 2026 | 41058174 | Mol Ther | found, 1 of 32 |
| Wang 2026 | 42129507 | Nat Biotechnol | found, 1 of 7 |
| Kula 2019 | 31398327 | Cell | found, 1 of 2 — **outside a 2-year window** |
| Dezfulian 2023 | 38016469 | Cell | found, 1 of 4 — **outside a 2-year window** |

The query is sound; **the window is the limiter.** A 2-year default would have missed both T-Scan
papers, which were the most data-rich of that batch. Two years is a throughput choice, so treat a
`Window` widening as a normal move on a journal that yields well, not an exception.

## Why the mechanical probe is affordable

One `efetch` per paper yields the full body, the complete supplementary file inventory with
extensions, the data-availability statement and every figure caption — enough to judge a paper
without a model reading it, and enough to name a gated file exactly. Measured across 12 journals,
**95% of candidates are in PMC**, so this covers almost everything. That measurement is what makes
gate B, not the model, the thing that rejects papers.

## Other harvest axes — namespace reserved, not built

Journals are one axis and they miss things structurally. These share the same `sweep.md` +
`candidates.tsv` shape and the same promote-to-`paper_source.md` path, under their own prefixes:

- **`D##` — reference-database citations.** VDJdb cites ~607 PMIDs; McPAS-TCR, IEDB and TCR3d
  carry their own. A prefiltered list of papers already known to have published usable pairs, with
  no journal or date restriction — likely better yield per paper screened than any journal sweep,
  and it reaches the pre-2024 work this window excludes.
- **`P##` — preprint servers.** bioRxiv has no `[ta]` and this field preprints heavily, so the
  journal axis cannot see it at all.

