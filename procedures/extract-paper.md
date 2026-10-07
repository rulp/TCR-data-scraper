---
name: extract-paper
description: Extract the TCR–pMHC dataset from one published paper into the clean_<ID> schema files. Use whenever a PMID, PMCID, DOI or paper is handed over to be extracted, or when a queued paper comes off paper_source.md. Holds the six-step procedure and the validation rules; the output contract itself is docs/schema.md.
---

# Extracting one paper

You are turning one published paper into `clean_<ID>.xlsx` plus its provenance and companion
files. `AGENTS.md` holds the indexing rules that name everything you write.

**Where papers come from.** Extraction runs on papers that **passed a journal screen**, taken
**1–5 at a time** so a human can check each batch before the next starts. The pass list is
`journals/<J##>_*/screened.md`; a paper gets its permanent `ID` and its `paper_source.md` row at
the moment it enters a batch, not when it passed the screen. A PMID handed over directly is still
extracted the same way — it just has no locator.

**Read `playbook/judgement.md` before making any annotation decision.** It is where every error
recorded so far has happened. The other two playbook files are lookup: `playbook/figures.md` when
sequences have to come out of an image, `playbook/fetching.md` when acquiring files or fighting
the environment. `REPORT.md` is the section index, and `docs/schema.md` is the output contract.

## What to delegate

Keep in this session, never delegate and never downgrade: threshold semantics and the
reconciliation against the paper's self-reported counts; `pMHC_species`; control-label
resolve-vs-drop; allele precision; which rows are a separate assay; and all `source_notes` prose.

Delegate to a subagent when it keeps bulk tool output out of this context — figure transcription
above all (see `playbook/figures.md`), file acquisition, and chasing a TCR sequence through
external databases. **A subagent's return payload is a claim, not a fact**: anything from one
that reaches output data must either be covered by an assertion in the build script or arrive
with verbatim evidence you check yourself.

---

## 1. What you are producing

**Read `docs/schema.md`.** It is the output contract — the ten columns, the IMGT and allele
conventions, why the α chain is mandatory, the provenance vocabulary, and the known gaps in the
format. It is one file so that extraction, screening and the audit cannot drift apart, and it is
short.

The three things that most often go wrong at this step, each covered there in full:

- **Allele precision is governed by what the source states**, never by matching another file's
  formatting. `TRAV21` stays `TRAV21`.
- **`pMHC_species` is decided once per peptide *source*,** not per peptide.
- **Anything off a figure or a main-paper table is extrapolated** and cites its exact location.

---

## 2. Extraction procedure

**Write a new build script for every paper. Never adapt an existing one.** No two groups
format their tables the same way — column names, table layout, label conventions, and
threshold semantics all differ. Prior scripts are references for the *sequence of steps*,
nothing more.

**A plain `.py`, not a notebook.** `<ID>_<FirstAuthor>.py` lives *inside* the paper's folder
next to `raw/`, takes nothing but `raw/`, and writes the `clean_<ID>` files beside itself.
Resolve its paths relative to the script, never to the working directory:

```python
HERE = os.path.dirname(os.path.abspath(__file__))
RAW  = os.path.join(HERE, "raw")
OUT  = HERE
```

so `uv run … python <ID>_<FirstAuthor>/<ID>_<FirstAuthor>.py` works from the repo root and from
anywhere else. It exists so that a changed rule
is a re-run instead of a re-extraction — thresholds get revised, publishers reissue
supplementary files, and at this corpus size re-deriving every paper by hand is not an option.
Keep it to that job:

- **No narrative in the script.** Every judgement call, caveat and discrepancy belongs in the
  `source_notes` sheet, which ships inside the workbook where a reader will actually find it.
  Comments in the script are for *why this line does what it does* — a threshold's quote from
  Methods, a cross-reference to `REPORT.md` — not a retelling of the extraction.
- **Turn the checks you ran into assertions.** Any count you reconciled against the paper, any
  dedup key you proved unique, any figure transcription the machine-readable file arbitrated —
  assert it. That is what stops a later edit from silently drifting, and it costs one line each.
- **Record the fetch commands in the module docstring** so `raw/` can be rebuilt from scratch.

### Step 0 — take the paper into the batch

Three things happen at this moment and nowhere else, because this is where a paper stops being
a candidate: it gets its permanent **`ID`**, its **`paper_source.md` row**, and its **root-level
folder**. `journals/journals.md` owns the rule; this is where it is performed.

```bash
python3 tools/new_paper.py --pmid <PMID> --from <J##>     # or --author/--year/--journal ad hoc
python3 tools/new_paper.py --pmid <PMID> --from <J##> --dry-run
```

It takes `max(existing) + 1` — never `count + 1`, because a dropped paper keeps its row and its
number — refuses a PMID already in the index, creates `<ID>_<FirstAuthor>/raw/`, and **moves
across anything already fetched into `journals/<J##>_*/incoming/<PMID>/`**. Files the screen
listed in `NEEDS_HUMAN.md` are therefore already in `raw/` by the time Step 1 runs; check there
before concluding a blocker is still blocking.

### Step 1 — inventory where the data actually is

**If the paper came from a journal screen, this step is already done.** Look for
`journals/<J##>_*/notes/<PMID>.md`; if it exists, read it instead of rediscovering, and spot-check
only the entries it marks low confidence. That locator names where each schema column comes from,
what is blocked, and which playbook sections apply — it is the output of `procedures/screen-journal.md`
and exists precisely so this step is not paid for twice. Treat `unknown` as unknown, and correct the
locator in place if you find it wrong.

Otherwise, do this before writing any code. **Read the data-availability statement**, and do not assume
the supplement holds the dataset. Observed locations, all in real papers:

| Location | Notes |
|---|---|
| Supplementary spreadsheets | sometimes everything; sometimes nothing |
| **Main-paper figures** | often the *only* home of TCR sequences — see `playbook/figures.md` §1 |
| GitHub / Zenodo | frequently has a ready-to-train CSV the paper never mentions |
| Dryad | large raw data; downloads are gated, see `playbook/fetching.md` §11 |
| Google Drive | often linked only from a repo README, not the paper — `playbook/fetching.md` §4 |
| Hugging Face | model weights, sometimes the training data too |
| Cited prior papers | where reused TCRs' sequences usually live |

Pull the PMC full-text XML first and list the figure captions — captions state what each
panel contains, which is the fastest way to find out whether the sequences are in an image.

```bash
# PMID -> metadata and PMCID
curl -sS "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id=<PMID>&retmode=json"
# PMCID -> full text XML (figure captions, Methods, data-availability statement)
curl -sS "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id=<PMCID-digits>&retmode=xml"
# Elsevier supplementary files, by the article PII from the publisher URL
curl -sSL "https://ars.els-cdn.com/content/image/<PII>-mmcN.xlsx" -o mmcN.xlsx
```

### Step 2 — get the peptide/label table

The paper's primary screen output. Apply **the paper's own threshold**, quoted from its
Methods, not a threshold of your own. Record the exact rule in `source_notes`.

Where a published file has labels pre-applied, check whether the raw per-replicate or
per-round counts are also available; without them the threshold cannot be varied or audited.

### Step 3 — get the TCR sequences

Search in this order, stopping when complete: full text → attached machine-readable files →
**figure images** → cited source papers. Library-screen papers typically identify a TCR by
name only and leave its sequence to a citation.

### Step 4 — validate before writing

**Load `playbook/checks.md` now.** It carries every test below as an assertion ready to paste
into the build script, with a pointer to the `judgement.md` section explaining what to do when
one fires. Non-negotiable, because published data contains junk:

- **Amino-acid alphabet check** on every peptide and CDR3 (`ACDEFGHIKLMNPQRSTVWY` only) and
  a length window — 8–11 for class-I peptides, 13–25 for class II (`judgement.md` §18).
  Published positive sets have been found to contain control labels and masked placeholders —
  see `playbook/judgement.md` §5.
- **A CDR3 must also begin with the conserved cysteine** and be 8–22 long. The alphabet check
  alone passes real junk: `HPEGKLIF` and `CAVFF` are both all-legal letters and neither is a
  CDR3 — see `judgement.md` §16.
- **Check `pMHC_species` against the peptide's stated source.** If the peptide is not human, it
  must not say `Human` — see `judgement.md` §10 and §17.
- **Cross-check any figure transcription** against a machine-readable file that duplicates
  part of the same figure. An exact match on the overlapping part validates the rest.
- **Assert the dedup key is unique** across the paper's TCR panel before deduplicating.

Write each of these as an `assert` in the build script, not as a one-off check you run and
then discard — they are what makes a later re-run trustworthy.

### Step 5 — emit

Three data artifacts per paper, written by `<ID>_<FirstAuthor>.py`:

1. `clean_<ID>.xlsx` — sheets **`clean` + `provenance` + `source_notes`**, no `NA` in any column.
2. `clean_<ID>_provenance.csv` — the same `provenance` frame, as CSV.
3. Any companion set that does not fit the schema — measured negatives, a second assay —
   as CSV, with an explicit outcome column.

**Every row must say where it came from, and `docs/schema.md` defines how.** Build the
`provenance` frame with `lib/provenance.py` — `Prov` for row-by-row scripts, `finalize()` for
column-wise ones — and never hand-roll those columns. `Prov.row()` raises if any of the ten
fields was never attributed, so a missing source fails the build instead of shipping blank.
Finish with `check_provenance(clean, prov, "<ID>")`, which is **C12** in `playbook/checks.md`.

Two constraints that are easy to break here: **the `clean` sheet stays exactly ten columns**, and
**assays stay in separate files** — a functional activation assay and a binding screen are
different evidence, and the schema has no column to tell them apart once merged.

### Step 6 — record what you could not solve

`AGENTS.md` requires a pass over `REPORT.md` after every batch. The moment to collect the
material is now, while the dead ends are still in front of you.

Add a `REPORT.md` section for each problem that survived the extraction — a file behind a
gate, a mapping the authors never published, a threshold that does not exist, junk in a
published column — stating what was tried, what the next session should do instead, and which
paper it was observed in. Append the next free number, add its row to the index table, never
renumber.

Nothing is also an answer: if every problem was handled by the procedure as written, say so
and leave the file alone. The test is whether a future session would waste time rediscovering
it.

When the blocker is a single file a human can fetch in a browser, **name that file exactly** —
in `source_notes` and to the user. "The supplement is unreachable" cannot be acted on;
"download `NIHMS1947859-supplement-6.pdf` into `<ID>_Dezfulian/raw/`" can.
