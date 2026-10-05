---
name: screen-journal
description: Screen one journal's papers for extractable TCR-pMHC data and write the per-journal list. Runs the mechanical probe, then a model screen in waves, producing a locator note per passing paper that extract-paper consumes. Use when given a J## journal id, "screen journal X", or "what should we extract next". Do NOT use when handed a specific PMID to extract; that is extract-paper.
---

# Screening one journal

You are deciding which papers in **one journal** could yield a `clean_<ID>.xlsx`, and recording
*where the data is* so extraction never has to rediscover it. You are **not** extracting, and you
are **not** downloading supplementary files.

`journals/journals.md` holds the journal list and the rules that govern it. `docs/schema.md` is
the output contract these papers must be able to fill — the locator you write below is keyed to
its ten column names.

## The three gates

| Gate | What | Model tokens |
|---|---|---|
| A harvest | `esearch` the journal + window, drop non-research types | none |
| B probe | one PMC XML per paper -> a card, scored `likely`/`unclear`/`unlikely` | none |
| **C screen** | **you** — read the cards, write a locator per paper | the only real cost |

Gates A and B are one command. Run it first, always:

```bash
python3 journals/probe.py J12          # resumable; re-running probes only what is new
```

It writes `candidates.tsv`, `cards/<PMID>.md`, `xml/<PMID>.xml` and `sweep.md` into the journal's
folder. **The XML is already on disk** — read it from there, never re-fetch it.

## Waves, not whole journals

**Screen ~20 papers at a time, highest-scoring unscreened first.** Do not screen a whole journal up
front: a deep screen on a paper that then sits unextracted for months is the one genuinely wasted
cost in this design, and extraction runs 5 papers at a time. Keep the screened list a little ahead
of extraction, no further.

Pick a wave with a query, never by loading the ledger:

```bash
awk -F'\t' 'NR>1 && ($5=="likely"||$5=="unclear")' journals/J12_Nat_Biotechnol/candidates.tsv \
  | sort -t'	' -k6,6nr | head -20 | cut -f1,3,5,6,7
```

**Never read `candidates.tsv` whole into context.** It is a queryable store; print a summary.

## Delegating a wave

Screening is read-only and the papers are independent, so **run 3–5 subagents in parallel**, one
paper each. They read cached XML from disk and never touch NCBI, so parallelism costs nothing
against the rate limit. Give each agent the card path, the XML path, and the locator template
below; ask for the finished locator as its return payload.

Beyond ~5 the bottleneck is your own review, not compute.

**Extraction is different and must not be parallelised this way** — `playbook/judgement.md` forbids
delegating judgement calls. A batch of 5 papers is a human review unit, not 5 extraction agents.

## The pass rule

**Use the asymmetric rule in `screen-corpus`** — peptides must come *from the paper*; TCR identity
only has to be *resolvable*. It is written there; do not restate or re-derive it here.

- **PASS** — the paper supplies its own peptide data, and α+β identity is resolvable: printed in
  the paper, or a named clone that resolves to a paired entry in VDJdb/PDB/IMGT, or sequences in a
  paper it cites.
- **PARK** — figure-only with no cheap signal, no PMC access, or a TCR route we have not indexed.
  Parked *with a reason*, re-checkable later. This is the default when you are unsure.
- **FAIL** — the paper supplies no peptide data of its own. The only verdict that ends a paper.

Three traps the cards are built to expose:

- **`!! NO TCR SEQUENCE EVIDENCE`** means zero `TRAV`/`TRBV`, zero CDR3-like strings and zero
  occurrences of "CDR3". Any clone names on that card may be *citations rather than the paper's own
  receptors*. Both outcomes are real: Jones 2026 (PMID 41058174) carries this flag and is a genuine
  PASS because the 1G4 TCR is its subject; Householder 2025 (PMID 40705894) carries it and was
  correctly dropped (`judgement.md` §21),
  because 1G4 appears only as a structural benchmark. **Decide which, and say so in the locator.**
- **`peptide-like tokens`** is the weakest signal on the card. It is regex over body text against a
  stoplist, and English leaks through. Never pass a paper on that number alone.
- **A screen's library unit is usually not an epitope** (`playbook/judgement.md` §14). A paper
  tiling the proteome in 56-mers still has to name its validated pairs somewhere.

## What you write

### 1. `notes/<PMID>.md` — the locator (PASS and PARK only)

This is the real output. It is keyed to the ten schema columns so `extract-paper` can skip its
discovery step entirely. Be specific enough to act on: a sheet name, a column letter, a panel.

```markdown
# 38016469 -- Dezfulian 2023 · PMC10841602
Verdict: PASS   Confidence: medium

| Column | Where | Form | Conf |
|---|---|---|---|
| Va/Ja/CDR3a | Table S4C | xlsx | high |
| Vb/Jb/CDR3b | Table S4C | xlsx | high |
| Antigen | Fig. S6F/S6G, minimal epitope | figure | medium |
| MHC | Fig. S6B/S6C legend, allele-level | figure | medium |
| pMHC_species | Methods, library design | text | high |
| TCR_species | human donors, Results para 1 | text | high |

## Blockers
- NIHMS1947859-supplement-6.pdf -- holds Fig. S6; PMC /bin/ is gated (REPORT.md section 13)

## Notes
- class II (DR/DQ): section 18 applies -- widen the length window, MHC is a heterodimer
- no stated hit threshold: section 15 applies
- expect ~6 rows
```

Cite the playbook sections that will apply. Handing extraction the right sections up front is half
the value of screening.

**Say "unknown" when it is unknown.** A confident guess about where the α chain lives costs the
extraction more than a blank, because it will be trusted.

### 2. `screened.md` — the list

The human-facing list for this journal. One row per PASS, newest work at the bottom:

```markdown
| PMID | Author | Year | What is there | Conf | Blockers |
|---|---|---|---|---|---|
| 42129507 | Wang | 2026 | yeast-display library + paired TCRs, PDB 9PBG/9PBH | high | none |
```

Keep PARK rows in a second table under `## Parked`, with the reason. Parked is not discarded.

### 3. `NEEDS_HUMAN.md` — the shopping list

Anything you cannot fetch. One block per file, precise enough to action without rereading the paper:

```markdown
## 38016469 Dezfulian -- NIHMS1947859-supplement-6.pdf
- why: holds Fig. S6F/S6G, the only place the minimal epitopes appear
- try: https://pmc.ncbi.nlm.nih.gov/articles/PMC10841602/  (supplementary list)
- put it in: <ID>_Dezfulian/raw/
- blocks: Antigen and MHC columns -- without it the paper yields 4 rows instead of 6
```

The user has institutional access and can fetch these in one sitting. **State what the file
unblocks**, so they can judge whether it is worth the trip. This is how
`NIHMS1947859-supplement-6.pdf` was resolved for Dezfulian 2023.

### 4. Append to `sweep.md`

Which wave ran, when, and the verdict counts.

### 5. Update this journal's row in `journals/journals.md`

**This is the one tracked file a screen edits, and it is how the other machine knows.** Set
`Status`, `Machine` and `Last swept` on that journal's row — `in progress` when the sweep starts,
`swept` when the journal is finished, `skipped` with a reason in `Notes`.

Claim it **before** you sweep, not after, and push that change: its whole purpose is to stop a
second computer starting the same journal. Touch only that row's cells, and never re-align the
table — `journals/journals.md` has the rules and why they matter.

## Do not

- **Do not download supplementary files.** The inventory on the card is enough to judge. Fetching
  is extraction's job, where a human is present to unblock a gated file. Fetching here means
  downloading for papers that may never be extracted.
- **Do not assign an `ID` or touch `paper_source.md`.** IDs are assigned when a paper enters an
  extraction batch. `screened.md` is the waiting list.
- **Do not extract.** If a locator is easy to write, write it and stop.
- **Do not edit another journal's row**, and do not reformat `journals/journals.md`. One row, its
  own cells, nothing else.
- **Do not promote a paper you could not open.** `no PMC access` is PARK, never FAIL — collapsing
  "no evidence" into "no access" silently discards the closed-access half of the corpus.
