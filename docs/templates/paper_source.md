# paper_source — the extraction queue

One row per paper. **`ID` is assigned when the row is appended and never changes.** It is the
key that ties together every artifact for that paper:

```
<ID>_<FirstAuthor>/                       the paper's folder — everything it produces
<ID>_<FirstAuthor>/<ID>_<FirstAuthor>.py  its build script: raw/ -> clean_<ID>
<ID>_<FirstAuthor>/raw/                   the acquired inputs
<ID>_<FirstAuthor>/clean_<ID>.xlsx        and the clean_<ID>_* companions
```

Add new papers at the **end** and take the next free ID. Never renumber, never reuse an ID, and
never reorder existing rows — IDs that drift break every path, filename and provenance row that
already cites them. If a paper is abandoned, leave its row with `Status = dropped`; do not
reclaim the number.

`First author` is the **first** author's surname, never the last author's. Two papers with the
same first author are distinguished by their IDs, so no suffix is needed.

`Status`: `queued` · `in progress` · `done` · `blocked` (needs a human — say why) · `dropped`.

`Source` records **how the paper entered the queue** — the journal sweep that found it
(`J05 2026-10`), the database axis (`D01`), or `ad hoc` for a PMID handed over directly. See
`journals/journals.md`.

| ID  | PMID | First author | Year | Journal | Short title | Source | Status |
|-----|------|--------------|------|---------|-------------|--------|--------|

---

**This file is per-machine and is not in git.** Each computer keeps its own index and starts at
`001`; the IDs here mean nothing on another machine. What is shared is the **PMID**, which is why
it is the second column, why every provenance CSV carries `source_pmid`, and why the tracking
sheet is keyed on it. Before extracting, check the sheet so two machines do not pay for the same
paper twice. `tools/export_index.py` turns this table into rows you can paste straight in.
