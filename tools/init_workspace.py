#!/usr/bin/env python3
"""Set up this machine's workspace on a fresh clone.

The repo ships the toolkit only -- procedures, playbook, scripts, the journal list.
Everything this machine produces is per-machine and gitignored, so a clone has to
seed its own index before anything can be queued.

    python3 tools/init_workspace.py

Idempotent: it never overwrites a file that already exists.
"""
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SEEDS = [("docs/templates/paper_source.md", "paper_source.md")]


def main():
    made, kept = [], []
    for src, dst in SEEDS:
        d = os.path.join(ROOT, dst)
        if os.path.exists(d):
            kept.append(dst)
            continue
        shutil.copyfile(os.path.join(ROOT, src), d)
        made.append(dst)

    for d in ("journals", "audit"):
        os.makedirs(os.path.join(ROOT, d), exist_ok=True)

    for f in made:
        print("created  %s" % f)
    for f in kept:
        print("kept     %s (already present -- not overwritten)" % f)

    print("""
Workspace ready. This machine's index starts at 001 and is not shared.

Next:
  1. Claim a journal in the shared tracking sheet (docs/templates/tracking_sheet.csv
     says how it is laid out) so the other machine does not sweep it too.
  2. python3 journals/probe.py J01        # harvest + probe, zero model tokens
  3. Point your agent at AGENTS.md.

Mirror this folder to Drive. Git does not carry your papers, raw/ or audit reads.""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
