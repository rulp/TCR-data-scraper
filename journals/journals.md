# journals — the harvest axis

The front end of the pipeline. Papers enter the queue by **sweeping one journal at a time** over
a bounded date window, rather than by one broad literature search. One journal is a unit of work
small enough to finish, check and resume.

**This file is the list and the rules that govern it.** It is the only thing a session reads
before starting a sweep. How a sweep actually runs — the three gates, the wave protocol, the pass
rule, what gets written — is `procedures/screen-journal.md`. How this list was built, and the
evidence behind its counts, is `journals/method.md`.

```bash
python3 journals/probe.py J12          # gates A+B; resumable, probes only what is new
```

A journal's working state lives in its own folder and is never loaded whole:

```
journals/
├── journals.md                  this file — the numbered list and its rules
├── method.md                    how the list was built: the query, the evidence
├── probe.py                     gates A+B — harvest and probe a journal, zero model tokens
└── J12_Nat_Biotechnol/          created when J12's sweep STARTS, not before
    ├── sweep.md                 run log: query, window, date, count at each gate
    ├── candidates.tsv           every PMID + signals + verdict — append-only, never read whole
    ├── cards/<PMID>.md          the mechanical card, written by probe.py
    ├── screened.md              THE LIST — passing papers, author + PMID + what is there
    ├── notes/<PMID>.md          the locator: where each schema column comes from
    ├── NEEDS_HUMAN.md           what is still missing after the screen tried to fetch it:
    │                            one entry per file, with its destination and why a human
    ├── incoming/<PMID>/         those files once fetched -- by the screen's step 6 or by
    │                            hand -- waiting for an ID. Step 0 of the extraction moves
    │                            them into papers/<ID>_<Author>/raw/
    └── xml/<PMID>.xml           cached PMC XML (gitignored)
```

## Rules

- **`J##` is assigned on append and is permanent.** Never renumber, never reuse, never reorder.
  Folder names derive from it, exactly as paper `ID`s work in `paper_source.md`.
- **`Priority` controls sweep order, not `J##`.** Re-prioritising a journal must never cause a
  renumber. Sweep P1 top-down, then P2, then P3, and stop whenever the yield stops justifying it.
- **Folder name** = `J##_` + the NLM `[ta]` abbreviation, spaces to `_`, dots removed.
  `Nat Biotechnol` → `J01_Nat_Biotechnol`.
- **`Window` defaults to the last 2 years and is overridable per journal.** Widening is a recorded
  decision: change the cell, say why in that journal's `sweep.md`, and re-sweep only the added
  years. `journals/method.md` has the recall evidence for why this column exists — a 2-year
  window would have missed the two most data-rich papers in the corpus.
- **`Status`**: `not started` · `in progress` · `swept` · `skipped` (say why in the Notes
  column). `Machine` names the computer that did it, `Last swept` the date.
- **This file is shared across machines, and it is the only tracked file you edit.** Three rules:
  1. **`git pull` before you claim a journal, and push the status change immediately** — before
     the sweep, not after. That is what stops the other machine picking the same one, and it is
     also what keeps merges trivial: if you pull first, your edit is the only one in flight.
  2. **Touch only the cells of the row you are sweeping.** Never the `Notes`, counts or priority
     of a row someone else is working on.
  3. **Never re-align or reformat the table.** The columns are deliberately left ragged. Padding
     them rewrites all 40 rows and guarantees a conflict — measured, not assumed.

  **If you do get a conflict here, it is one or two lines and the fix is to keep both edited
  rows.** Git needs three unchanged lines between edits to merge them silently, so two machines
  sweeping *adjacent* journals — `J01` and `J02`, which is exactly what working down the P1 list
  looks like — will conflict even though the edits do not overlap. That is a loud, ten-second
  fix, and it is the trade this layout accepts in exchange for progress living in the list you
  already read.
- **Counts are a dated snapshot**, not live. They exist so a session knows the expected volume
  before starting, and so growth since the last sweep is visible. `journals/method.md` has the
  `curl` command that refreshes them.
- **`candidates.tsv` is a queryable store, never read into context whole.** Query it and print a
  summary. It is append-only so a sweep can be resumed mid-journal.
- **Passing a screen does not assign an `ID`.** `screened.md` is the waiting list; a paper gets its
  permanent `ID`, its `paper_source.md` row and its root-level folder when it enters an extraction
  batch of 5. This keeps `paper_source.md` the small active queue rather than a list of hundreds.
- **Promoted papers do NOT live here.** Once promoted, a paper's folder is created under
  `papers/` as `papers/<ID>_<FirstAuthor>/`. Paper folders are **never** nested under a journal: nesting would make a
  paper's path depend on where it was published and break every path already cited in provenance.
  `paper_source.md` stays this machine's single index, which is what makes a paper found twice —
  once by journal, once by a database citation — dedupe for free on PMID. Across machines the
  same job is done by the shared tracking sheet, also keyed on PMID.

## The list

Snapshot: counts taken **2026-10-03**, window `2024/01/01:2026/12/31`. Total `Broad` = 827.

| J## | Journal | NLM `[ta]` | Window | Broad | Plat | Priority | Status | Machine | Last swept | Notes |
|-----|---------|-----------|--------|-------|------|----------|--------|---------|------------|-------|
| J01 | Nature Communications | `Nat Commun` | 2024–2026 | 84 | 6 | P1 | in progress | KQ447KXJVT | 2026-10-07 | highest broad count in P1 |
| J02 | Journal for ImmunoTherapy of Cancer | `J Immunother Cancer` | 2024–2026 | 76 | 2 | P1 | not started | — | — | strong data mandate |
| J03 | PNAS | `Proc Natl Acad Sci U S A` | 2024–2026 | 45 | 4 | P1 | not started | — | — |  |
| J04 | Science Advances | `Sci Adv` | 2024–2026 | 34 | 3 | P1 | not started | — | — |  |
| J05 | Molecular Therapy | `Mol Ther` | 2024–2026 | 32 | 4 | P1 | not started | — | — | known-good venue |
| J06 | Immunity | `Immunity` | 2024–2026 | 30 | 0 | P1 | not started | — | — | Plat 0 is a query artefact |
| J07 | Science Immunology | `Sci Immunol` | 2024–2026 | 17 | 2 | P1 | not started | — | — |  |
| J08 | Nature | `Nature` | 2024–2026 | 16 | 0 | P1 | not started | — | — |  |
| J09 | Nature Immunology | `Nat Immunol` | 2024–2026 | 15 | 0 | P1 | not started | — | — |  |
| J10 | Cell | `Cell` | 2024–2026 | 8 | 0 | P1 | not started | — | — | known-good venue; its best papers predate a 2-year window |
| J11 | Science | `Science` | 2024–2026 | 7 | 0 | P1 | not started | — | — |  |
| J12 | Nature Biotechnology | `Nat Biotechnol` | 2024–2026 | 7 | 2 | P1 | not started | — | — | known-good venue |
| J13 | Cancer Immunology Research | `Cancer Immunol Res` | 2024–2026 | 28 | 1 | P2 | not started | — | — |  |
| J14 | Journal of Clinical Investigation | `J Clin Invest` | 2024–2026 | 25 | 1 | P2 | not started | — | — |  |
| J15 | Cell Reports | `Cell Rep` | 2024–2026 | 20 | 1 | P2 | not started | — | — |  |
| J16 | Cell Reports Medicine | `Cell Rep Med` | 2024–2026 | 18 | 1 | P2 | not started | — | — |  |
| J17 | Blood | `Blood` | 2024–2026 | 18 | 2 | P2 | not started | — | — |  |
| J18 | eLife | `Elife` | 2024–2026 | 13 | 0 | P2 | not started | — | — |  |
| J19 | Clinical Cancer Research | `Clin Cancer Res` | 2024–2026 | 13 | 1 | P2 | not started | — | — |  |
| J20 | Journal of Experimental Medicine | `J Exp Med` | 2024–2026 | 12 | 0 | P2 | not started | — | — |  |
| J21 | Science Translational Medicine | `Sci Transl Med` | 2024–2026 | 11 | 0 | P2 | not started | — | — |  |
| J22 | Cancer Cell | `Cancer Cell` | 2024–2026 | 9 | 0 | P2 | not started | — | — |  |
| J23 | Nature Medicine | `Nat Med` | 2024–2026 | 8 | 0 | P2 | not started | — | — |  |
| J24 | Cell Reports Methods | `Cell Rep Methods` | 2024–2026 | 6 | 1 | P2 | not started | — | — | methods-heavy, good density |
| J25 | Nature Cancer | `Nat Cancer` | 2024–2026 | 5 | 0 | P2 | not started | — | — |  |
| J26 | Nature Methods | `Nat Methods` | 2024–2026 | 4 | 1 | P2 | not started | — | — |  |
| J27 | Cell Systems | `Cell Syst` | 2024–2026 | 4 | 1 | P2 | not started | — | — |  |
| J28 | Frontiers in Immunology | `Front Immunol` | 2024–2026 | 142 | 13 | P3 | not started | — | — | highest volume on BOTH axes; P3 on venue quality, not on yield |
| J29 | Journal of Immunology | `J Immunol` | 2024–2026 | 29 | 1 | P3 | not started | — | — |  |
| J30 | Briefings in Bioinformatics | `Brief Bioinform` | 2024–2026 | 29 | 5 | P3 | not started | — | — | computational; datasets often on GitHub, not in the paper |
| J31 | European Journal of Immunology | `Eur J Immunol` | 2024–2026 | 23 | 2 | P3 | not started | — | — |  |
| J32 | Bioinformatics | `Bioinformatics` | 2024–2026 | 13 | 0 | P3 | not started | — | — |  |
| J33 | PLOS Computational Biology | `PLoS Comput Biol` | 2024–2026 | 6 | 1 | P3 | not started | — | — |  |
| J34 | Structure | `Structure` | 2024–2026 | 5 | 1 | P3 | not started | — | — | structural; pairs usually resolvable via PDB |
| J35 | Immunology & Cell Biology | `Immunol Cell Biol` | 2024–2026 | 5 | 1 | P3 | not started | — | — |  |
| J36 | Nucleic Acids Research | `Nucleic Acids Res` | 2024–2026 | 4 | 0 | P3 | not started | — | — | database issues — may announce a TCR resource |
| J37 | Protein Science | `Protein Sci` | 2024–2026 | 2 | 0 | P3 | not started | — | — |  |
| J38 | Nature Machine Intelligence | `Nat Mach Intell` | 2024–2026 | 2 | 1 | P3 | not started | — | — |  |
| J39 | Genome Biology | `Genome Biol` | 2024–2026 | 2 | 0 | P3 | not started | — | — |  |
| J40 | Nature Structural & Molecular Biology | `Nat Struct Mol Biol` | 2024–2026 | 0 | 0 | P3 | not started | — | — | 0 for this window; keep listed, re-check on widening |

## Adding a journal

Append at the end, take the next free `J##`, fill `Broad` and `Plat` with the command in
`journals/method.md`, and set a priority. Do not insert a journal into the middle of the table to keep it tidy — the number
is the identity, and the Priority column already carries the ordering.
