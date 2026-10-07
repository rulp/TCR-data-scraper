# TCR-data-scraper: extracting TCR training data from papers

## What this is for

T cells recognise disease using a **T-cell receptor (TCR)**. Each receptor binds a short
**peptide** held up by an **MHC** molecule. Which receptor binds which peptide is the thing we
want to predict — and to train a model to predict it, you need a lot of examples of receptors
paired with the peptides they actually bind.

Those examples exist, but they are scattered across hundreds of papers, in different formats:
some in spreadsheets, some only inside a figure image, some only in a sentence in the Methods.

**This pipeline collects them into one clean table.** Every row is one receptor paired with one
peptide it recognises, always in the same ten columns, no matter which paper it came from.

The hard part is not collecting — it is *not being wrong*. A fabricated row is worse than a
missing one, because a model trained on it learns something false and nobody can tell. So most
of the machinery here exists to make mistakes visible: every value records where it came from,
and a final audit goes back and checks that it really is there.

## What comes out

One spreadsheet per paper, `clean_<ID>.xlsx`, with three tabs:

| tab | what's in it |
|---|---|
| `clean` | the data — exactly ten columns, one row per (receptor, peptide) pair |
| `provenance` | for every row, where each value came from |
| `source_notes` | the judgement calls made while extracting, in plain English |

The ten columns are `Va, Ja, CDR3a, Vb, Jb, CDR3b, Antigen, MHC, pMHC_species, TCR_species` —
the alpha chain, the beta chain, the peptide, the MHC allele, and what species the peptide and
the receptor come from.

A fresh copy starts empty. One paper typically yields anywhere from a handful of rows to
tens of thousands, depending on whether it published a screen or just a validated panel.

## The four steps

Each step is separate on purpose, so you can check the work before moving on.

### 1. Pick a journal

`journals/journals.md` lists 40 credible journals, ranked `P1` (do these first) to `P3`.
Each has a date window, usually the last 2 years, and a rough count of how many candidate
papers it holds. Open the file and pick the next one that says `not started`.

### 2. Screen that journal for useful papers

```bash
python3 journals/probe.py J01
```

This does the free part: it finds every candidate paper in that journal and downloads one
summary document each, then scores them. It costs nothing but time, and you can stop and
re-run it — it picks up where it left off.

Then ask your AI agent to **screen the journal**. It reads the scored summaries and decides which
papers can actually yield data, writing the result to that journal's folder:

- `screened.md` — the list of papers worth extracting, with author and PMID
- `notes/<PMID>.md` — for each one, *where in the paper* each piece of data lives
- `NEEDS_HUMAN.md` — files it could not download, with exact names and where to put them

**You will sometimes need to help here.** Some papers are paywalled. `NEEDS_HUMAN.md` tells you
exactly which file to fetch with your institutional access, where to save it, and what it
unblocks so you can decide whether it is worth the trip.

Expect most papers to fail this screen. For the test journal, 7 candidates produced 1 usable
paper. That is normal and it is the point — screening is cheap, extraction is not.

### 3. Extract the papers that passed

Ask your agent to **extract** papers from `screened.md`, **1 to 5 at a time**. Small batches are
deliberate: you get to look at each batch before the next one starts.

Each paper gets its own folder at the top level — `007_Smith/` for paper 007 — containing
the files it was built from (`raw/`), a script that builds it, and the output spreadsheet.

To rebuild a paper from scratch at any time:

```bash
uv run --with pandas --with openpyxl python 007_Smith/007_Smith.py
```

Nothing is done by hand. If a rule changes later, you re-run the script instead of redoing the
paper.

### 4. Audit — check the data is really where it says it is

```bash
uv run --with pandas --with openpyxl --with pypdf python audit.py
```

This is the safety net. For every value, it goes back to the source that value claims to come
from and looks for it. It writes `AUDIT.md` and **fails loudly** if anything is missing.

Values that exist only inside a figure get checked by having someone re-read the figure
**without being told the expected answer** — otherwise they would just agree with it.

Results are one of:

- **verified** — found where it says it is
- **mislocated** — the value is real but points at the wrong file (fix the note, not the data)
- **judgement** — a decision, not a quote (the two species columns; these can't be string-matched)
- **unverifiable** — no way to check automatically, and it says why
- **contradicted** — *not where it claims to be.* **Stop and investigate.**

A run that ends in **0 contradicted** is the result you want. Anything else is a finding, not
a failure of the audit.

**Never edit the data to make the audit pass.** A contradiction can mean the note is wrong, the
value is wrong, or the source changed — and those have different fixes.

## Where things live

```
journals/            the journal list, and one folder per journal you've screened
007_Author/ …        one folder per paper: raw files in, spreadsheet out
paper_source.md      this computer's list of papers, with their permanent IDs
AUDIT.md             the latest audit result
playbook/            hard-won lessons: what goes wrong and what to do about it
REPORT.md            index to the playbook — every numbered section lives here
procedures/          the four step-by-step procedures the agent follows
docs/schema.md       what the output must look like — the ten columns
lib/provenance.py    shared code so every paper records sources the same way
AGENTS.md            instructions for the AI agent (not meant for people)
SETUP.md             installing and running it on another computer
```

## Four rules that will bite you

1. **IDs are permanent.** Once a paper is `007`, it is `007` forever — the number is in file
   names and in provenance records. Add new papers at the end; never renumber or reuse, even
   for a paper that got dropped.
2. **A paper's folder holds everything that paper produces**, build script included, and it
   sits at the top level — never inside a journal folder.
3. **IDs are local to this computer.** If you run this on a second machine, its `001` is a
   different paper. The PMID is what the two have in common — which is why the shared tracking
   sheet is keyed on it, and why you should check that sheet before extracting. See `SETUP.md`.
4. **Don't delete anything from `raw/`.** The build scripts read from it, and the audit checks
   against it. If a file is gone, the paper can no longer be verified. Nothing under a paper
   folder is in git, so back it up yourself.

## When something goes wrong

`REPORT.md` is the index to everything that has already gone wrong and been solved — gated
downloads, sequences hidden in figures, junk in published tables, papers that never state their
own threshold. Check there before burning time on a problem that is already written up.

If you hit something new that a future session would waste time rediscovering, add a section.
That is what keeps the pipeline from relearning the same lesson.
