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
# The vendor skill folders are GENERATED from procedures/ by tools/init_workspace.py
# and are gitignored, so they are output, not source -- checking them would be checking
# our own generator's work twice.
SKIP_DIRS = {".git", "raw", "__pycache__", ".venv", "venv", "node_modules",
             ".agents", ".claude", ".cursor", ".codex"}
# The gitignored WORKSPACE, for the same reason `raw` is skipped: its documents name files
# that belong to a publisher, not to us. A locator note cites
# `41467_2024_47576_MOESM7_ESM.xlsx` precisely because that file is NOT here yet -- naming it
# is the note's whole job. This guard exists to stop AGENTS.md's routing rotting, and the
# routing is all in tracked files.
SKIP_RE = re.compile(r"^(J\d\d_|\d{3}_|papers$|_control$|audit$)")

# A repo path inside backticks: `playbook/checks.md`, `audit.py`, `lib/provenance.py`.
# Anchored on a known extension so prose like `clean` or `--papers` is not mistaken for one.
PATH = re.compile(r"`([A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:md|py|txt|tsv|csv|xlsx|json|sh))`")
# Placeholders stand for a family of files, not one file.
PLACEHOLDER = re.compile(r"<|\*|\bN\b")
# Named as examples of a problem, not as files of ours. The second group are member files
# inside a third-party DATA DEPOSIT (Zenodo, GEO), cited by name in the playbook because the
# lesson is about which member to open -- naming them generically would lose the lesson.
EXEMPT = {"inspect.py", "csv.py",
          "figure2_input_metadata.csv", "figure4_output_metadata.RData"}
# A PUBLISHER's supplementary file. These are named on purpose and will never be repo paths:
# a procedure that shows what a fetch request looks like has to name a real one, or the
# example teaches a shape nobody can copy. Covers Springer/Nature MOESM, Elsevier mmc, and
# PMC author-manuscript supplements.
SUPP_FILE = re.compile(r"(?:_MOESM\d+_ESM|^mmc\d+|^1-s2\.0-|^NIHMS\d+-)", re.I)

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
                     r"|screened\.md|NEEDS_HUMAN\.md|clean_\w+\.(xlsx|csv)|SKILL\.md)$")


def _keep(d):
    return d not in SKIP_DIRS and not SKIP_RE.match(d)


def walk():
    for base, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if _keep(d)]
        for n in names:
            if n.endswith((".md", ".py")):
                yield os.path.join(base, n)


def check_procedures():
    """Every procedure must carry the frontmatter its skill adapter is generated from.

    A missing or mismatched `name` is the failure that matters: Cursor requires a
    skill's name to equal its folder, and a wrong one fails silently -- the skill
    simply never matches.
    """
    bad = []
    d = os.path.join(ROOT, "procedures")
    if not os.path.isdir(d):
        return bad
    for f in sorted(os.listdir(d)):
        if not f.endswith(".md"):
            continue
        name = f[:-3]
        m = re.match(r"\A---\n(.*?)\n---\n", open(os.path.join(d, f), encoding="utf-8").read(), re.S)
        if not m:
            bad.append(("procedures/" + f, "no YAML frontmatter"))
            continue
        fields = dict(re.findall(r"^(\w[\w-]*):\s*(.*)$", m.group(1), re.M))
        if fields.get("name") != name:
            bad.append(("procedures/" + f,
                        "declares name %r, must be %r" % (fields.get("name"), name)))
        if not fields.get("description", "").strip():
            bad.append(("procedures/" + f, "no description"))
    return bad


def main():
    dangling, claude_refs, local_ids = [], [], []
    stubs = os.path.join(".claude", "skills")
    # A document may name a file by basename alone -- `sweep.md`, `candidates.tsv`,
    # `checks.md` -- meaning "the one of those", of which there is a copy per journal or
    # per paper. Accept any basename that exists somewhere in the repo.
    basenames = {os.path.basename(f) for f in walk()}
    for base, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if _keep(d)]
        basenames.update(names)

    for f in walk():
        rel = os.path.relpath(f, ROOT)
        text = open(f, encoding="utf-8").read()

        if rel == os.path.join("tools", "check_docs.py"):
            continue                      # this file names the patterns it looks for

        for cited in set(PATH.findall(text)):
            if SUPP_FILE.search(cited):
                continue
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

        # RUNTIME files are generated into the gitignored workspace and their whole job is to
        # name this machine's concrete artifacts -- AUDIT.md reports on "Paper 001" because
        # that is the paper it audited. Policing them for <ID> placeholders is checking the
        # wrong thing: the rule exists to keep the TOOLKIT portable, and these are output.
        if rel not in ID_OK and not RUNTIME.match(os.path.basename(rel)):
            for m in LOCAL_ID.findall(text):
                local_ids.append((rel, m))

        # CLAUDE.md is gone. .claude/skills/ is generated and gitignored, so only the
        # three docs that explain the arrangement have reason to name it.
        if re.search(r"\bCLAUDE\.md\b", text):
            claude_refs.append((rel, "CLAUDE.md"))
        if stubs in text.replace("/", os.sep) and rel not in (
                "AGENTS.md", "SETUP.md", "README.md", os.path.join("tools", "init_workspace.py")):
            claude_refs.append((rel, ".claude/skills"))

    procs = check_procedures()

    bad = False
    if procs:
        bad = True
        print("Procedures whose frontmatter cannot generate a skill adapter:")
        for rel, why in procs:
            print("  %-40s -> %s" % (rel, why))
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
    print("check_docs: paths resolve, procedure frontmatter is valid, no stale references.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
