# Playbook — judgement calls

**Mandatory reading for every extraction.** These are the places where real errors have
happened, plus the decisions that recur. This file is the *reasoning*: why each rule exists and
what to do when one fires. The tests themselves live in **`playbook/checks.md`**, as assertions
to paste into the build script — load that at Step 4. Sections keep their original `REPORT` numbers;
`REPORT.md` is the index.

None of this may be delegated to a subagent or a cheaper model. A subagent that did not make
the decision will write a plausible rationale into `source_notes` rather than the real one.

**Keeping this file small.** It is loaded on every extraction, so its size is a tax on every
paper. Three rules, enforced when adding a section: the *test* goes in `checks.md`, never here;
the worked example is a single `Observed:` line naming the paper, not a narrative; and a section
that is purely operational — with no decision to make — does not belong in this file at all.
A section that cannot be stated in about fifteen lines of reasoning is usually two sections.

---

## 5. Placeholder and control strings in published positive sets

Published data contains junk in the sequence column, and it is usually labeled positive:

- control labels instead of sequences (a gene or construct name where a peptide belongs);
- masked strings (`XXXXXXXXX`, `SFLPLLXXX`) in machine-learning training files;
- bare integers.

Seen in **multiple independent papers**, so treat it as the norm. **Apply an amino-acid
alphabet check and a length window at every extraction**, not as a per-paper patch. A
strip-and-uppercase is not validation.

The check tells you a row is junk; it does not tell you what to do with it. **§9** covers that —
a control label is usually recoverable and is usually the paper's best positive.

## 6. CDR3β collisions between distinct TCRs

Engineered CDR3β variants of a wild-type TCR can coincidentally reproduce the CDR3β of other
real TCRs in the same panel. Those receptors then share a β chain while differing in α — and
carry **conflicting labels** for the same peptides, since they were profiled in separate
selections.

Deduplicating on β alone silently merges them and destroys the conflict.

**Solution: carry the α chain and dedupe on (`CDR3a`, `CDR3b`, `Antigen`).** The colliding
receptors differ in α, so the composite key separates them. **Assert key uniqueness across
the panel in the build script** — if it fails, the schema is losing receptors.

## 9. Control labels are sequences to resolve, not rows to keep

The alphabet check (§5) flags a non-sequence string in the peptide column. What happens next is
a decision, and dropping the row is usually the *wrong* half of it:

- **If the paper says what the control encodes, replace the label with the sequence.** Screens
  name their positive controls (`NYESO1`, `MART1`, `WT`, `PHA`, a construct name) and the
  Methods or Results almost always state the peptide behind the name. That row is usually the
  paper's strongest positive — the on-target pMHC — so losing it costs the one pair you were
  most sure of.
- **Only if nothing states the sequence, drop the row** and record what was dropped.
- **Never emit the label.** A row whose `Antigen` is `NYESO1` cannot be trained on, cannot be
  deduplicated against the same pMHC arriving from another paper, and silently defeats every
  downstream alphabet check.

**Resolving a label changes the row count, and that is correct.** The same pMHC often appears as
a sequence in one supplementary table and as a label in another, so resolving merges two source
rows into one schema row — the format is *one row per unique (TCR clonotype, peptide) pair*, not
one row per screen hit. Expect the clean sheet to be shorter than a naive union of the per-table
hit lists, and say so in `source_notes`: give the mapping, name the tables it merged, and state
the resulting count. Otherwise the next reader diffs against a hit-list total, sees one row
missing, and assumes data was lost.

## 10. `pMHC_species` is a property of the peptide's source, not of the peptide

**Observed mistake.** In a proteome-derived PresentER library, one control peptide (`LAMWITQC`,
an 8mer variant of the on-target NY-ESO-1 epitope) was marked `Synthetic` because the paper
called it a "variant" — i.e. because it looked designed. Correct answer: `Human`, like every
other peptide in that library. Its sibling control `LLMWITQC` had been marked `Human`, so one
peptide in a single set carried a different origin from the rest of it.

**Method.** Decide `pMHC_species` **once per peptide source**, then apply it to every peptide
that came from that source:

1. Find the statement of provenance — the library-design paragraph in Methods, or, for peptides
   imported from a cited paper, that paper's own description of where they came from.
2. `Synthetic` only when the source *states* a randomized or display-selected origin: yeast
   display, phage/mammalian epitope display, positional-scanning or combinatorial libraries,
   randomized minigene pools. Those sequences are not proteome entries even when some match
   human genes.
3. `Human` for anything the source describes as proteome-derived — **including** designed
   analogues inside it: anchor-modified variants, truncations, single-residue mutants, on-target
   controls. "The authors modified it" is a fact about design history, not about provenance, and
   this column records provenance.
4. A set with genuinely mixed provenance is split **by the stated source** — never by your own
   reading of what a sequence looks like.

**Symptom to check before emitting** (`checks.md` **C8**). Group the output by peptide source
and look at `pMHC_species`. One peptide disagreeing with its siblings is almost always an inferred value,
not a sourced one. A worked split: in one paper the whole proteome-derived screen library was
`Human` while nine off-targets imported from a cited yeast-display study were `Synthetic` —
two sources, two values, no per-peptide judgement calls.

The general form of this error: **a rule written for a category got applied to an individual
member on the strength of an inference.** `AGENTS.md` says to record what the source states;
that applies to the annotation columns, not just to the sequence columns.

## 14. Screen tables keyed by an opaque peptide ID

A screen's tables can be complete, machine-readable and still useless: every row is
`peptide number, count, count, count`, and **no number-to-sequence map is published**. Detect it
with `checks.md` **C6** before planning the extraction.

Do not reconstruct the identifiers from the library description — the ordering is an artefact of
the authors' cloning, and a guessed mapping mislabels every row silently.

**A second trap in the same papers: the library unit is usually not an epitope.** Screens tile
the proteome in 56-, 90- or 15–18-aa fragments, and a fragment does not belong in `Antigen`. The
minimal epitope is a separate result, often figure-bound.

Such a paper can still yield its validated TCR/epitope pairs — the ones named in a Methods
peptide list or an activation panel. Say in `source_notes` that the screen itself was not
converted, and why. *Observed: Kula 2019, PMID 31398327.*

**The same trap wearing different clothes: a reactivity label that names a protein.** Single-cell
papers often publish a per-cell `Ag_reactivity`-style column holding `SLA`, `PDCE2`, `CYP2D6`,
`FLU`. It is tempting because it sits right beside clean paired CDR3/V/J and looks like the
antigen column the schema wants. It is not: the cells were selected against a whole protein or a
pool, so the label is the *assay*, not the epitope. **Attributing them to a named epitope the
paper cites elsewhere is fabrication**, even when the paper discusses exactly one epitope -- it
turns one citation into as many rows as there are cells. If no per-cell epitope mapping is
published **for that dataset**, those rows fail here no matter how good their TCR side is.
*Observed: Cardon 2025 (PMID 39880819) -- its Figure 2 experiment has 725 clean paired clonotypes
and not one usable antigen; assigning the 305 SLA-reactive ones to Sepsecs187-197 would be an
inference the paper never makes.*

**But scope the verdict to the dataset, not the paper** -- see fetching.md 25. The same deposit's
Figure 4 is a tetramer sort on a single defined epitope and yields 31 perfectly good rows. A paper
can carry a protein-label dataset and an epitope-defined one side by side, and failing the whole
paper on the first one you open throws the second away.

## 15. Papers that state no hit threshold at all

Some papers have no threshold to quote. Confirm with `checks.md` **C7**: if `threshold` never
appears and the only quantitative sentences are definitional or visual, the calls were made by
eye from the figures.

**Do not invent one, and do not borrow one from another paper.** Two honest options: emit only
the pairs the paper validates by a named assay, or ship the continuous measurement with an
explicit `Binding_Outcome = "NOT CALLED - paper states no threshold"`.

A p-value column with no stated cutoff is the same situation, as is a Methods section describing
FDR correction when the tables carry only fold enrichment — the rule cannot be reapplied from
what was published. *Observed: Kula 2019 (PMID 31398327) and Dezfulian 2023 (PMID 38016469).*

## 16. A CDR3 that passes the alphabet check but is still junk

§5 covers non-amino-acid strings. The subtler case is a string of **entirely valid residues**
that is still not a CDR3: `HPEGKLIF` (no leading cysteine, published as a real CDR3α) and
`CAVFF` (five residues). A strip-and-uppercase check passes both.

Every CDR3 carries a conserved cysteine at IMGT position 104, so the leading `C` is as much a
validity check as the alphabet — `checks.md` **C2**. When it fires, §9 governs what happens
next; a truncated record cannot be repaired by guessing the missing residues.

Assert the malformed value is *still present* when re-reading a published file, so a corrected
reissue announces itself instead of silently changing the row count.
*Observed: Dezfulian 2023 (PMID 38016469) Table S4C, and a VDJdb record cited by Kula 2019
(PMID 31398327).*

## 17. `pMHC_species` values beyond Human and Synthetic

The original two values do not cover the corpus: peptides have come from CMV pp65, HIV-1 Gag, an
*E. coli* YeiH epitope and a Bacteroidales receptor — in papers whose other peptides are human.

**If the peptide is not human, do not write `Human`.** The column records provenance, and
flattening a microbial epitope into `Human` states something false; a model trained on the merged
table then cannot separate self from microbial ligands, which is what several of these papers
exist to study.

Use the source organism as stated — `Human`, `Mouse`, `Synthetic`, `CMV`, `HIV-1`, `Bacterial` —
and keep deciding it per *source*, never per peptide (§10). The vocabulary is open by necessity,
so record every value used and flag new ones to the user: fixing it is a schema decision, not a
per-paper one. Check with `checks.md` **C8**.

**`Mouse` is a value, added 2026-10-07 for a murine self or tumour peptide** presented on H2 —
`docs/schema.md` has the allele spelling. The trap is that a mouse experiment is not a mouse
*peptide*: most murine TCR work presents an LCMV, influenza or model peptide such as OVA on a
murine MHC, and those stay `LCMV`, `Influenza A virus` and `Synthetic`. `pMHC_species` reads the
peptide's origin, never the mouse the assay ran in, and never the species of the MHC beside it —
which is exactly the field `TCR_species` is for.

## 18. MHC class II papers break class-I assumptions

A CD4+/HLA-II paper violates two things the class-I papers made look universal:

- **Length window.** Class-II epitopes run 13–25 residues; an `8 <= len <= 11` assertion rejects
  every valid row. Widen it per paper (`checks.md` **C3**) and say so, rather than loosening it
  globally.
- **`MHC` is a heterodimer.** DR fits one column (`DRB1*03:01`); DQ and DP need both chains
  (`DQA1*05/DQB1*02`). Write the pair and record the convention.

Expect the restriction to be stated serologically in the text ("HLA-DR3") while the allele-level
construct appears only in a figure legend. Quote the legend, and mark the serology-to-allele step
as the inference it is. *Observed: Dezfulian 2023, PMID 38016469.*

## 20. The same receptor arrives from several papers under several names

Clone names are not identifiers. Across one batch, three different failures of the same kind:

- **A citing paper misspells the clone.** Kohlgruber 2024 writes `TCR3898-2` 13 times; the paper it
  cites writes `TCR-3598_2` 31 times and never `3898`. Same antigen, same allele, same
  characterisation — one clone.
- **A paper names clones by PDB accession.** `6MNO` and `6MNG` are structures, not clones
  (TCR 6235 and TCR 4738). Their own source paper then transposes `4738`/`4378` internally.
- **The same database record reaches you twice under different aliases.** VDJdb clone `JG-33`
  arrived as Kula 2019's `NLV3` and again as Kohlgruber 2024's `NLV3`.

So **resolve a clone to a record, then compare records — never compare names.** Check the corpus
before resolving externally: the chains may already be curated under a different `tcr_id`, which
is cheaper and keeps the two rows consistent.

The consequence that matters: **a clone dropped once must stay dropped.** Record every drop and
its reason, and check that record before resolving a clone you have seen before. VDJdb `JG-33` is
the worked case: its CDR3α is the five-residue `CAVFF`, which fails §16 on sight, and meeting the
same record again under another alias does not make it valid. Equally, a near-miss id is not a
match — verify the digits.
*Observed: Kula 2019, Dezfulian 2023 and Kohlgruber 2024.*

## 21. A paper with no T cell receptor in it at all

The α-chain invariant says a β-only paper is a signal to dig harder. There is a different case it
is easy to confuse with that one: **the paper reports no gene-encoded receptor at all**, and no
amount of digging will produce one. Recognising it early saves the dig and is a clean FAIL.

Three signals, and you want all three before concluding it:

- The binding module is **not a TCR framework** — a de novo designed scaffold, an antibody Fab, a
  nanobody, a TCR *mimic*. Methods will say so.
- The full text returns **zero** hits for `TRAV`, `TRAJ`, `TRBV`, `TRBJ` and `CDR3`. This is what
  the screen card's `!! NO TCR SEQUENCE EVIDENCE` flag reports.
- The structure, if there is one, has **no polymer entity annotated as a TCR α or β chain** —
  check the entities, not the title.

**The trap is the comparator.** These papers routinely name a real TCR as a structural benchmark,
with no sequence of their own. Do not emit a row for it. The pairing is not this paper's result,
and if that receptor is already in the corpus from its own paper, emitting it again duplicates one
receptor under a second PMID — exactly the cross-source double-count the provenance CSV exists to
prevent. The same flag therefore has two opposite outcomes, and the comparator is what separates
them: a paper whose *subject* is a named TCR passes; a paper that only *cites* one fails.

*Observed: Householder 2025, PMID 40705894 — a designed four-helix minibinder against
NY-ESO-1/A\*02:01 (PDB 9MIN, five entities, none a TCR chain), naming 1G4 only as a comparator.*

## 22. The paper contains peptides; that does not make them the paper's peptides

The hard gate is that **peptides come from the paper**. Half of one 20-paper wave failed it while
showing strong peptide signals, in four classes. Recognising them early is the difference between
a two-minute read and a 150-300k-token extraction that yields nothing.

- **Computational re-analysis.** Every peptide and TCR record is a download -- IEDB, VDJdb,
  CEDAR, the 10x dextramer panel, a prior paper's supplement. Tell: Methods has no wet-lab
  section at all, only "Preparation of the ... dataset" paragraphs.
- **Specificity assigned by database matching.** Subtler, and it passes a naive check: the paper
  sequences its own receptors, then labels them by matching CDR3s against VDJdb/IEDB. The TCRs
  are real and the peptides are real, but the *pairing* is a lookup. Extracting it re-imports
  database rows under a new PMID -- the cross-source double-count the provenance CSV exists to
  prevent.
- **Non-peptidic antigen.** MAIT/MR1 with riboflavin metabolites (5-OP-RU, Ac-6-FP), or CD1 with
  lipids. MR1 and CD1 are monomorphic, so `MHC` has no allele and `Antigen` has no sequence. The
  schema structurally cannot hold these.
- **Antigen-agnostic repertoire.** Bulk or single-cell TCR against a whole protein, a PPD, a
  pathogen lysate or whole cells. The paper usually says outright that the epitopes are unknown.

All four are **FAIL**, not PARK: no amount of fetching produces the missing column. The binder
that is not a TCR at all is the fifth class and has its own section, **§21**.
*Observed: Drost 2024, Foster 2026, Kain 2026, Walkenhorst 2024, Turner 2026, Perriot 2025,
Keller 2024, Lee 2026 and Nielsen 2025 -- all Nat Commun, one wave.*

## 23. A receptor whose binding does not depend on the peptide

A TCR can bind pMHC with real, measured affinity while the peptide contributes nothing to the
specificity -- it contacts the MHC helices only, and does not activate T cells. The SPR numbers
are genuine, so every automatic check passes, and the rows look exactly like positives.

They are not. A specificity model trained on them learns that this receptor binds those peptides,
when what the paper demonstrated is the opposite: that it binds *regardless of* them.

**This project excludes them. The decision is settled -- do not re-litigate it per paper.**
A receptor whose binding does not depend on the peptide is useless for the model this dataset
trains, so the paper FAILs on this section alone, however good the rest of it looks. Record the
FAIL with the reason so a later wave does not pay to re-screen it, and keep the locator note if
one was already written -- it shows the paper was understood rather than skipped.

Do not ship the rows in a companion CSV "just in case" either. That was the other defensible
answer before the call was taken; it is not now.

The tell is in the paper's own framing: a structure paper reporting that the TCR "does not contact
the peptide", paired with a functional figure showing no CD69 or no cytokine.
*Observed: Lim 2025 (PMID 40199885), the G9 TCR on HLA-DQ2.5/DQ2.2 -- screened PASS, then FAILed
on this section once a human read it. Six SPR rows, all real affinities, none of them specificity.*

## 26. A data-quality flag encoded as text colour

A supplementary table can mark its own bad rows in a way no text extraction can see. Menon 2024
(PMID 38684663) ends Supplementary Tables 6-9 with a one-line legend: **"Red denotes truncated
CDR3 regions."** The colour is the only thing separating a complete CDR3 from a fragment, and
`pypdf` -- like every text extractor -- returns the characters without it. A parser reads a
truncated sequence as a clean one.

**Look for the legend.** A table that colour-codes anything says so in a caption or a footnote,
usually in one short sentence under the table. Read those lines before parsing, not after; they
are the only warning you get.

**Then assume the flag is invisible and catch the rows another way.** For a CDR3 the shape
validator does most of the work -- a truncation at the N-terminus loses the conserved cysteine,
which `checks.md` C2 already rejects. That is what caught `SCGEGGNKLVF` here. **It is not a
complete defence**: a truncation at the *other* end leaves a sequence that still starts with `C`
and still passes the alphabet and length tests, so some fraction of red rows ship looking clean.

Two things make the residue recoverable rather than invisible:

- **Cross-check against a machine-readable file** that covers the same cells, even one that
  cannot replace the table. Menon's Source Data holds the same clonotypes as *nucleotide*
  sequences with no V/J column -- useless as a source, decisive as a check. Translating every
  cell in three frames and searching for the transcribed CDR3s put 237/286 alpha and 381/397
  beta cells on a PDF sequence; the ~17% of alpha cells that miss are the best available
  estimate of how many truncated rows the shape validator did not catch.
- **Assert the hit rate**, not just the parse. A rate is the only quantity that moves when a
  transcription silently degrades.

If the colour matters more than this -- a table where the flag marks *which rows are positives*
rather than which are damaged -- the table is not extractable from text at all, and the figure
route in `figures.md` applies instead.

## Decisions that recur

Resolve these per paper and record the choice in `source_notes`:

1. **`pMHC_species` for library-derived peptides.** Randomized display libraries with fixed
   anchor positions are not proteome sequences, so `Synthetic` is accurate — even though
   validated hits often map to real genes. `Human` would overstate their origin. Decide it per
   *source*, not per peptide, and do not flip it for designed analogues sitting inside a
   proteome-derived set — see **§10**.
2. **Positives only, or positives plus negatives.** The schema is positives-only, so the
   measured negatives go in a companion CSV. For a large screen this is the difference
   between thousands of rows and millions.
3. **Allele-level vs gene-level V/J** — governed by what the source states, never by matching
   another file's formatting.
4. **Combined training files** that re-list TCRs already present individually must be
   excluded from the pool, or those receptors are double-counted.

## 28. The V and J genes are not in the paper

Three papers in one batch printed CDR3s, or deposited chains, and no IMGT gene call anywhere:
a patent-sourced panel, a structural paper with zero `TRAV`/`TRBV` strings in its full text, and
a mechanism paper that named its V genes but not its J genes and cited another paper for the rest.
`Va`, `Ja`, `Vb` and `Jb` are mandatory, so "not stated" is not an answer — and neither is a guess.
**The mandatory-column invariant says what a shipped row contains; it is not a licence to
manufacture one.** The refusal rule at the end of this section is the half that makes the rest
safe. Read it before you start matching, not after a call comes out thin.

**Look for a stated gene before assigning one.** In order of how much it is worth:

| Where | What it gives |
|---|---|
| the paper's Methods | occasionally the whole call, with alleles — take it |
| a **patent's prose**, not its sequence listing | "FR1, FR2 and FR3 … corresponding to a TRAV 26-2 chain … those of a TRBV19 chain". The listing has only sequences; the description names the genes. Seen once, US12018062 — a place to look, not a rule about patents |
| the **cited** paper | often repeats the same gap — check, do not assume |
| the cited paper's **structures** | the end of the chase. A PDB entry carries whole chains |
| RCSB entity names | `T cell receptor beta variable 6-5` is an annotation someone else derived, carrying no score. Cross-check your own call against it. It has not been caught wrong here — it has also never been the evidence |

**Assigning it: match against the IMGT reference, one ungated download** (fetched 2026-10-07; it
is a plain file, so if the name moves look for the current one under `download/GENE-DB/`):

```
https://www.imgt.org/download/GENE-DB/IMGTGENEDB-ReferenceSequences.fasta-AA-WithoutGaps-F+ORF+inframeP
```

This is a hand-rolled ungapped matcher standing in for **IMGT/V-QUEST**, which is the
authoritative tool and which handles the indels that separate some V genes inside one family.
Nothing here has needed it yet. A call that lands near the threshold is the reason to go and run
it, rather than the reason to argue about the threshold.

Three things about the matching, all learned the hard way:

- **Do not anchor at position 0.** A crystallised construct begins `MAKEVEQ…` where the germline
  begins `KNEVEQ…`, and a prefix match then scores the *correct* gene at 1/92. Score the best
  ungapped offset instead — `range(-5, 12)` has covered every construct seen. With the offset the
  same chain scores 87/92.
- **Cut the chain at the end of FR4 before calling J:** `A[:A.index("GKGTKLSVIP") + 10]`. The
  suffix match runs against the whole J-REGION, and a deposited chain continues on into the
  constant domain, so an **untrimmed chain scores 0/15 against every J gene**. That fails the
  margin test instead of producing a wrong call, which is the right way round — but it presents as
  an ambiguous paper rather than as a forgotten step, so check the cut before believing the
  ambiguity.
- **Require the margin over the best OTHER GENE, not the runner-up.** Sometimes the runner-up is
  a second allele of the same gene — `TRBJ2-7*02` differs from `*01` by one residue — and a plain
  runner-up test then rejects a call that is not ambiguous at all. It is not always so: in two of
  these three papers the runner-up was a different gene.

### The thresholds, and what is actually under them

```python
assert top >= FLOOR and top > best_other_gene + 5
```

Every gene call made in J01, with controls measured by scoring a chain as something it is not:

| Call | How it was settled | Score | Best other gene | Margin |
|---|---|---|---|---|
| TRAV26-2 (Han) | patent prose, match corroborates | 90/92 | TRAV26-1 at 62 | 28 |
| TRBV19 (Han) | patent prose, match corroborates | 94/95 | TRBV28 at 55 | 39 |
| TRAV12-2 (Murugesan) | derived | 87/92 | TRAV12-3 at 65 | 22 |
| TRBV6-5 (Murugesan) | derived | 90/95 | TRBV6-9 at 81 | 9 |
| TRBV6-2 (Wang) | **refused**; the papers' own text used instead | 93/95 | TRBV6-3 at 93 | **0** |
| TRAJ28 (Han) | derived | 20/21 | TRAJ50 at 5 | 15 |
| TRAJ39 (Murugesan) | derived | 16/20 | TRAJ51 at 3 | 13 |
| TRBJ1-6 (Wang) | derived | 15/17 | 7 | 8 |
| TRBJ1-1 (Murugesan) | derived | 14/15 | TRBJ1-2 at 7 | 7 |
| TRAJ28 (Wang) | derived | **12**/21 | 5 | 7 |
| TRBJ2-7 (Han) | derived | **13**/15 | TRBJ1-6 at 7 | **6** |
| *α chain scored as a β chain* | control | 18/96 | 17 | 1 |
| *MHC heavy chain scored as a V* | control | 11/89 | 11 | 0 |
| *MHC heavy chain scored as a J* | control | 2/20 | 2 | 0 |

Han is PMID 42288475, Murugesan 39578466, Wang 41315272 — named by author and PMID, not by
paper ID, which means something only on the machine that assigned it.

**The margin is the test that works.** Real calls separate by 6–39; a chain that is not the thing
being called separates by 0–1. An order of magnitude, measured — which is why the margin and not
the raw score is what decides.

**The margin threshold has one residue of headroom.** The tightest real call in the corpus,
TRBJ2-7 on Han's unmutated parent β, clears `> other + 5` with a margin of 6. Why 5 and not some
other number: the best other *gene* scores 3–7 on every J call above, because that is the length
of the `FG.GT..` tail every J gene shares. A margin past 5 means the match has run beyond the
conserved motif into gene-specific residues. Hold the number as that statement, not as a constant
someone tuned.

**The absolute floor is weaker than it looks.** The Han script uses `>= 12`, and the two lowest real
scores in the table are 12 and 13. A floor set at the observed minimum has not been shown to
exclude anything — it describes this corpus rather than testing the next one. Keep it as a cheap
guard against a degenerate match; do not read it as independent evidence. **V needs no floor**: a
V-REGION is 89–96 residues, a real call takes 87–94 of them, and a wrong chain takes 11–18.

### The refusal rule

Exactly three outcomes. There is no fourth.

1. **A source states the gene** → use the source, at the precision the source states. The match is
   a cross-check and is recorded as one. Han's patent names TRAV26-2 and TRBV19 and the match
   agrees by 28 and 39, but the provenance cites the patent, because that is where the call came
   from.
2. **Nothing states it, and the margin clears** → derive it, `origin="external"`, and put the
   numbers in the provenance string: the gene, the score over the reference length, the best other
   gene and its score. A reader must be able to judge the call without redoing it.
3. **Nothing states it, and the margin fails** → **the row does not ship.** Write it to
   `clean_<ID>_unresolved.csv` with its top three candidates and their scores, assert the count,
   and say so in `source_notes`. A dropped row that is counted and explained is a result; a
   dropped row that is silent is data loss. This is **C13**.

Three things that are never a fourth outcome:

- **Do not widen the threshold to admit the data in hand.** It is a floor, not a dial. When the
  calls in front of you fail it, the honest readings are "this chain needs better evidence" and
  "these are genuinely two genes" — never "5 was too strict". The threshold is worth changing on
  evidence about the *method*; it is never worth changing to raise a row count.
- **Do not take the top hit because it is probably right.** Wang's β chain matches TRBV6-2\*01 and
  TRBV6-3\*01 at 93/95 each. Which one sorts first is an artefact of the sort, not a finding.
- **Do not fill a mandatory column with a guess in order to keep the row.** A row that cannot
  supply all four gene calls is not a row missing a field; it is not a row.

Branch 1 is the usual way out of branch 3 and is worth exhausting first. Wang's tie was settled
because the *papers* state TRBV6-2, not because the structure was re-examined; the match's job
there was to prove the structure could not decide, which is why that assert stays in the script.

**J comes from FR4**, which is short (`FGKGTKLSVIP`, `FGPGTRLTVT`) but distinctive. In the one
engineered panel seen here, affinity maturation rewrote the junction and left FR4 untouched. That
is an observation about Immunocore's panel, not a law: a framework-engineered, murinised or
J-swapped construct would break it, and the thing to check is that FR4 still *matches a germline J
exactly* before resting an inheritance argument on it.

**Write the gene, not the allele**, unless a source states the allele. The top two alleles often
differ by one residue on an engineered chain, which is not a basis for choosing between them.
Mixing a stated `TRAV19*01` with a derived `TRAJ28` in one row looks inconsistent and is correct:
precision follows the source, per `docs/schema.md`.

**An engineered receptor does not corroborate its own J.** Where the maturation reached into the
J-derived end of CDR3, each variant's match drops far enough to stop distinguishing neighbouring
genes — 12/21 and 10/15 on Han's variants, against 20/21 and 13/15 on the parent. Establish the
call on the unmutated parent and assert that every variant still carries the parent's FR4
*exactly*; that is the real evidence for inheritance. Restating the weaker per-variant match would
dress an inherited call up as an independent one.

**Expect the audit to call these `unverifiable`, and leave them that way.** A gene call is an
assignment about a sequence, not a string quoted from a file; having the IMGT reference in `raw/`
proves the gene exists, not that this chain is it. `unverifiable` is the honest verdict, and the
provenance string should carry the numbers so a reader can judge the call without redoing it.

**A format the audit cannot read is worse than a missing file.** When `audit.py` gained an
R-deposit reader, a conversion bug made it return its own error message as the file's "text"; the
file then indexed as readable-but-empty and 53 fields that really were in it were reported
**contradicted** rather than unverified. A reader that half-works inverts the audit's most serious
verdict, so check a new one by asking whether a value you know is in the file comes back.

## 29. Chemically modified epitopes are out of scope

**Decided 2026-10-08 by the user.** Raised by Loh 2024 (PMID 39043656), whose four HLA-DR4
epitopes each carry a citrulline. The rule it settles is general and binds every paper after it.

**If the residue the receptor reads cannot be written in the 20-letter alphabet, the row does not
ship.** The test is representability, not the word "modification":

| Out of scope | In scope |
|---|---|
| citrulline, phospho-Ser/Thr/Tyr, methyl- and acetyl-lysine, nitrotyrosine, cysteinylation, glycosylation, any non-natural library residue | **deamidation** — Q→E and N→D produce *standard* residues, so a deamidated gliadin peptide is an ordinary 20-letter string |
| a spliced or trans-spliced peptide whose sequence the paper does not print in full | a sequence that is unusual but writable, however exotic its origin |

**The decision is per row, not per paper.** A paper that assays a modified epitope *and* its
unmodified counterpart ships the counterpart and drops the other. Only a paper whose epitopes are
all modified yields nothing, and that is the case that reaches a verdict.

### Why out rather than encoded

Three failures, in order of how expensive they are to undo:

1. **Writing the parent residue fabricates data.** The modification is usually the specificity
   itself. Back-mutating cit→R produces a peptide that was never assayed and labels it bound —
   and because the dedupe key is (`CDR3a`, `CDR3b`, `Antigen`) (§6), a later paper that measures
   the true arginine peptide and sees nothing collides with it *exactly*, leaving two identical
   rows with opposite answers and no field that separates them.
2. **A 21st letter only helps a reader who knows it.** Every downstream consumer that encodes 20
   amino acids has to be taught the symbol, and it would have to be decided once for all
   modifications rather than per paper.
3. **An `Antigen_modification` column widens the sheet**, which `docs/schema.md` says it does not
   do.

### What to do with one

- **Extraction.** Drop the rows. Not to `clean_<ID>_unresolved.csv` — that file is **C13**, for a
  value that exists and could not be settled. These values are settled and outside the contract.
  Count them, assert the count, and name the modification in `source_notes`. If *every* epitope is
  modified the paper yields no rows at all and its `paper_source.md` row becomes
  `Status = dropped`.
- **Screening.** This is a **FAIL**, not a PARK. The verdict rule in `screen-journal.md` is worded
  for it. Parking would be waiting on a schema decision that has already been taken.
- **Record the PMID and the modification in the journal's `## Failed` table anyway.** This rule is
  the one in the playbook most likely to be reversed: if the schema ever gains a modification
  field, these papers are recoverable with a `grep` over the failed tables instead of a re-sweep.
  Loh is the first entry, and its TCR side is complete (paired αβ, 56 CDR3s, PDB 8TRR/8TRQ/8TRL),
  so it would come back cheaply.

**What this costs, stated plainly:** the autoimmunity literature where the modification *is* the
finding — citrullination in rheumatoid arthritis, phosphopeptides in cancer — is now out of the
corpus. That is the accepted price of a peptide column a model can read without a legend.

## 30. Both chains published, and never paired

*Observed in Liu 2025 (PMID 41034205).* Its Supplementary Data 2 is better than most: 56 public
TCRalpha and 29 public TCRbeta clonotypes, each with **V and J**, so section 28 never fires. The
cells were tetramer-sorted on one named 15-mer, so the antigen is defined per cell. Every one of
the ten columns has a source.

**And it yields no rows**, because the two lists are keyed only by epitope. The authors have the
pairing -- Methods filter cells to 1a1b or 2a1b -- but no published artifact carries it.

**Do not pair them.** 56 alphas and 29 betas against three epitopes is 1624 receptors that were
never observed, each one indistinguishable in the output from a real one. This is worse than a
missing row: the dedupe key is (`CDR3a`, `CDR3b`, `Antigen`) (§6), so an invented pairing is a
fresh unique key that nothing downstream can detect.

Before concluding, check in this order -- a public clonotype list is often not the only artifact:

1. **Source Data, sheet by sheet.** A paired-repertoire figure (a circos, a clonotype network)
   usually has one. In this paper it did not: the Source Data workbook had sheets for Figures 1,
   4 and 6 and none for Figure 2, which is where the pairing figure was.
2. **The Supplementary Information PDF**, even when the locator calls it figure-bound.
3. **A sequence archive.** Raw FASTQ is not a route: re-running the authors' aligner is a
   different extraction, not this one.

A circos is not a rescue even when transcribed. It gives TRAV-TRBV **gene** pairing frequencies,
never CDR3 to CDR3.

**What to do instead.** Ship the chains as a `clean_<ID>_unpaired_chains.csv` companion with
their V, J, epitope, allele and species, set the paper to `Status = blocked` in
`paper_source.md`, and assert in the build script that the sheet still has no joining column --
so a reissue that adds one fails the build instead of going unnoticed.

## 31. A deposit that publishes the strict IMGT CDR3, not the junction

*Observed in Malone 2025 (PMID 41407706).* Its GEO metadata gives `tcra = AEDWNARLM`, and
`docs/schema.md` requires every CDR3 to begin with the conserved cysteine. Nothing is wrong with
the deposit: **IMGT CDR3 is positions 105-117**, which excludes C104 and the F or W at 118, while
this corpus -- like VDJdb and 10x -- writes the **junction**, 104-118 inclusive.

So the conversion is `"C" + cdr3 + <the J germline's conserved residue>`, and it is definitional
rather than inferred. Two things make it safe to automate:

- **The trailing residue is not always F.** Take it from the J gene's own IMGT germline: TRAJ33
  ends in W, and TRAJ35's FR4 opens on a cysteine. Hard-coding `F` corrupts a few percent of rows
  silently.
- **The frame is checkable.** A junction normally ends on residues that are still J germline, so
  measure the overlap between the CDR3's tail and the germline before FR4. In that paper 83% of
  rows overlap by three or more residues. Assert it **corpus-wide, never per row** -- a heavily
  trimmed J legitimately leaves no germline residue at all, so a per-row gate would discard real
  receptors.

Confirm the column really is the strict form before converting: count how many strings start with
`C` (0.3% there), and check a beta chain, where prepending `C` should produce the canonical
`CAS...` in most rows (79% there). If instead most strings already start with `C`, the column is
already a junction and prepending another one is corruption.

A few J germlines carry no `[FW]G.G` anchor at all. Those rows cannot be closed in frame: they go
to `clean_<ID>_unresolved.csv` with the reason, under **C13**.

## 32. Reconstructing an analysis: check it against the paper's own count first

*Observed in Ghoreyshi 2026 (PMID 42337259).* It deposits everything except the answer: the
tetramer barcode code, per-cell barcode counts, and 10x contigs with V, J and CDR3 already
called. What it never publishes is which TCR it assigned to which peptide, and Methods give only
the clonotype-level rule (">90% tetramer binding consensus") with no per-cell rule -- no
normalisation, no cutoff, no tie-break. That is §15.

The temptation is to reimplement, because every input is right there. **Before shipping a single
row from a reconstruction, reproduce a number the paper states.** Here the paper's Table 1 reports
94 TCR cases for the experiment; the deposit's filtered contigs for it hold 532 cells of which 45
carry both chains, giving 5 clonotypes and 3 that clear the stated consensus. Three against
ninety-four is not a near miss, it is a different pipeline, and the three rows would have looked
perfectly clean in the output.

The check costs one count and it is the difference between a reconstruction and a guess wearing
the paper's name. Candidates for it: a per-dataset n, a per-epitope n in a results table, a
clonotype total, a cell total. If none is stated, there is nothing to check against and the
reconstruction should not ship at all.

When the check fails, §15's second option still applies: ship the continuous measurement in a
companion with `Binding_Outcome = "NOT CALLED - paper states no threshold"`, so the work survives
for whoever obtains the authors' assignment. 322 paired clonotypes with gene calls and raw
tetramer counts left that paper in a state where one file would finish it.

## 33. Two ways the §28 matcher silently returns the wrong gene

*Observed in Notti 2025 (PMID 41402338) and Ma 2025 (PMID 39833157).* §28's matcher is sound and
its margin rule holds. Both of these are mistakes in how it is *driven*, and both fail the same
ugly way — not with an error, but with a confident call that is wrong, or with a margin that
collapses and makes a perfectly resolvable paper look ambiguous.

**The offset window is calibrated on crystallography constructs, and a cryo-EM paper breaks it.**
§28 says to score the best ungapped offset over `range(-5, 12)`, which covers a construct that
begins at or near the germline. A full-length membrane-embedded construct does not: it carries its
signal peptide, and 1G4's TCRα begins `METLLGLLILWLQLQWVSS` — nineteen residues — before
`KQEVTQIPAALSVPEG`. Inside the window the correct gene scores **13/90 and loses**; TRAV41 and
TRAV35 tie for first at 13 and the margin is 0, which presents as "this paper's chains are
ambiguous". Unbounded, the same chain scores **93/93 for TRAV21 with a margin of 50**.

Scan every offset. It is a maximum over a superset of the window's offsets, so it cannot return a
worse answer, and on chains this size it costs microseconds. Treat `range(-5, 12)` as a historical
note, not a parameter.

**For J, the margin lives in the FR4 cut — and a free-offset scorer destroys it.** V genes are
long and idiosyncratic, so they separate however they are scored. J genes are 15–20 residues of
which the last 10–12 are the conserved `[FW]G.GT..` framework that *every* J in the locus shares.
All the discriminating signal is in the few residues at the 5' end, inside the junction.

So a J has to be matched **anchored at the end of FR4**, with every candidate judged at the same
anchor. Cut the chain there and compare suffixes. Ma's TCR3 β is the demonstration: anchored,
TRBJ2-7 scores 14/15 and the best other gene is TRBJ1-6 at 7, a margin of **7** — a clean call.
Let each J gene slide to its own best offset instead and TRBJ2-3 climbs to 12 by aligning on the
shared `QYFGPGTRLTVT` tail, the margin falls to **2**, and the row is refused under C13 for no
reason. Scoring the *untrimmed* chain is the other half of §28's warning and is worse still:
everything scores 0 and nothing resolves.

Take the cut from the CDR3's own position — `dom.index(cdr3) + len(cdr3) + 10` for α and `+ 9` for
β — rather than from a motif search. A greedy `[FW]G.G[A-Z]{6,12}` regex overruns FR4 into the
constant domain, which reintroduces exactly the failure the cut was meant to prevent.

**Both of these look like an ambiguous paper rather than a forgotten step.** When a margin comes
out low, re-check the offset range and the cut before believing the ambiguity.

## 34. One clone under two names in the same paper

*Observed in Finnigan 2024 (PMID 38459027).* Its Fig. 2a — the only table carrying any CDR3 —
prints `34BB3` and `46A2D8`. Fig. 2c, Fig. 2d, the Results text and the Source Data workbook all
print `34AE3` and `46AD8`. Eleven of the thirteen clone names agree; two do not, and nothing in
the paper acknowledges it.

This matters more than a cosmetic slip, because the clone name is usually the **join key between
the sequence table and the measurement table**, and the measurement is often what decides whether
a row exists at all. Here Fig. 2d's per-receptor EC50 against the wild-type peptide is what
separates a cross-reactive receptor's second row from a non-responder's absent one, and 46AD8 is
the clone the Results single out as completely cross-reactive. Joining it to the wrong receptor
would have attached a real positive to the wrong sequence, and nothing downstream would have
noticed.

**Join on the name, then check the join covered everything.** A set difference in both directions
costs one line and is the whole detection method: if either side has leftovers, the paper is
inconsistent and you have found it before it found you.

**Derive the repair, do not hand-write it.** Pair the leftovers by whatever the paper gives you
that is independent of the name — here the leading digits, elsewhere the target antigen or the
row order — and assert the resulting map. A hard-coded `{"34BB3": "34AE3"}` is correct today and
silently wrong the moment a reissued figure renames a third clone; a derived map fails the build
instead.

**A name that resolves against nothing public is still worth checking against the paper.** These
are internal lab IDs (§20), so no database adjudicates them. The paper is the only authority, and
it disagrees with itself.

## 35. A deposit that reports a gene pair it could not separate

*Observed in DiLisio 2026 (PMID 41872174).* Cell Ranger writes an unresolved V call as a compound:
`TRBV12-2+TRBV13-2`. It is not a gene name and it is not a dual-gene name either — `TRAV38-2/DV8`
and `TRAV6-7/DV9` are single IMGT genes that happen to carry two labels, and those are written
verbatim. A `+` is the aligner stating that it could not tell two genes apart.

Writing it into `Vb` is what **C13** exists to prevent, so it never ships. The resolution is in two
steps:

- **If the same junction pair is observed anywhere with a single-gene call, take that call.** It is
  the same receptor and the question is which gene it is, not how often it was seen.
- **Otherwise the row cannot supply a mandatory column** and goes to `clean_<ID>_unresolved.csv`,
  counted and explained.

**Resolvedness beats support, and this is the trap.** The obvious implementation collapses
duplicate junction pairs by keeping the best-supported call — which is what you want for the
ordinary case, where a near-identical duplicated gene like `TRAV10D` against `TRAV10N` splits a
clonotype's cells 90 to 1. But in all three contested pairs here the *compound* call was the
better-supported one (28 against 1, 20 against 10, 2 against 1), so sorting by cell count alone
ships the compound into the clean sheet. Sort on resolvedness first and support second.

Then assert the invariant positively — no shipped gene call contains a `+`. The sort is an
argument that it cannot happen; the assertion is what catches the next aligner that spells its
ambiguity some other way.
