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

Use the source organism as stated — `Human`, `Synthetic`, `CMV`, `HIV-1`, `Bacterial` — and keep
deciding it per *source*, never per peptide (§10). The vocabulary is open by necessity, so record
every value used and flag new ones to the user: fixing it is a schema decision, not a per-paper
one. Check with `checks.md` **C8**.

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
