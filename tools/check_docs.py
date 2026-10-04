#!/usr/bin/env python3
"""Fail if any repo path cited in a document does not exist.

The routing in AGENTS.md is only worth anything if every path in it resolves. This is the
guard that makes renaming a document safe: run it after any move.

    python3 tools/check_docs.py

Standard library only. Exits 1 on the first category that fails.
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SKIP_DIRS = {".git", "raw", "__pycache__", ".venv", "venv", "node_modules"}

# A repo path inside backticks: `playbook/checks.md`, `audit.py`, `lib/provenance.py`.
# Anchored on a known extension so prose like `clean` or `--papers` is not mistaken for one.
PATH = re.compile(r"`([A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:md|py|txt|tsv|csv|xlsx|json|sh))`")
# Placeholders stand for a family of files, not one file.
PLACEHOLDER = re.compile(r"<|\*|\bN\b")
# Named as examples of a problem, not as files of ours.
EXEMPT = {"inspect.py", "csv.py"}

# Paper IDs are assigned PER MACHINE and start at 001 on each, so a concrete one in a
# tracked file is meaningless to anyone else and goes stale the moment the workspace
# differs. The toolkit must speak in <ID>. Catches `001_Jones/`, `clean_003.xlsx`,
# `clean_002_provenance.csv`, "paper 004", "Paper 006".
LOCAL_ID = re.compile(r"\b\d{3}_[A-Z][a-z]+|\bclean_\d{3}\b|\b[Pp]apers? \d{3}\b")
# Where a concrete number is legitimately illustrative rather than a live reference.
ID_OK = {"README.md", "AGENTS.md"}

# Files the PIPELINE CREATES at runtime, in the gitignored workspace. The docs must be
# able to name them even though a clean clone has none of them yet.
RUNTIME = re.compile(r"^(paper_source\.md|AUDIT(_partial)?\.md|candidates\.tsv|sweep\.md"
                     r"|screened\.md|NEEDS_HUMAN\.md|clean_\w+\.(xlsx|csv))$")


def walk():
    for base, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for n in names:
            if n.endswith((".md", ".py")):
                yield os.path.join(base, n)


def main():
    dangling, claude_refs, local_ids = [], [], []
    stubs = os.path.join(".claude", "skills")
    # A document may name a file by basename alone -- `sweep.md`, `candidates.tsv`,
    # `checks.md` -- meaning "the one of those", of which there is a copy per journal or
    # per paper. Accept any basename that exists somewhere in the repo.
    basenames = {os.path.basename(f) for f in walk()}
    for base, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        basenames.update(names)

    for f in walk():
        rel = os.path.relpath(f, ROOT)
        text = open(f, encoding="utf-8").read()

        if rel == os.path.join("tools", "check_docs.py"):
            continue                      # this file names the patterns it looks for

        for cited in set(PATH.findall(text)):
            if PLACEHOLDER.search(cited) or cited.startswith(("http", "~")):
                continue
            if cited in EXEMPT:
                continue
            if RUNTIME.match(os.path.basename(cited)):
                continue                  # created at runtime; absent from a clean clone
            if "/" not in cited and cited in basenames:
                continue                  # named by basename; a copy exists somewhere
            # A bare filename may be a sibling of the citing file or sit at the root.
            here = os.path.join(os.path.dirname(f), cited)
            if os.path.exists(os.path.join(ROOT, cited)) or os.path.exists(here):
                continue
            dangling.append((rel, cited))

        if rel not in ID_OK:
            for m in LOCAL_ID.findall(text):
                local_ids.append((rel, m))

        # CLAUDE.md is gone; .claude/skills/ may be named only by the stubs themselves,
        # by AGENTS.md's layout tree, and by SETUP.md's note about what it is for.
        if re.search(r"\bCLAUDE\.md\b", text):
            claude_refs.append((rel, "CLAUDE.md"))
        if stubs in text.replace("/", os.sep) and rel not in (
                "AGENTS.md", "SETUP.md", "README.md") and not rel.startswith(".claude"):
            claude_refs.append((rel, ".claude/skills"))

    bad = False
    if dangling:
        bad = True
        print("Cited paths that do not exist:")
        for rel, cited in sorted(set(dangling)):
            print("  %-40s -> %s" % (rel, cited))
    if claude_refs:
        bad = True
        print("Harness-specific references outside the places allowed to mention them:")
        for rel, what in sorted(set(claude_refs)):
            print("  %-40s -> %s" % (rel, what))
    if local_ids:
        bad = True
        print("Concrete paper IDs in the toolkit (IDs are per-machine -- write `<ID>` instead):")
        for rel, what in sorted(set(local_ids)):
            print("  %-40s -> %s" % (rel, what))

    if bad:
        return 1
    print("check_docs: every cited path resolves; no stale harness or paper-ID references.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
