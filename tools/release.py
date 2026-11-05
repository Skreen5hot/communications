# SPDX-License-Identifier: MIT
"""Publish every protocol version that has no release yet.

    python tools/release.py --dry-run    # say what would be published
    python tools/release.py              # publish (needs gh and GH_TOKEN)

Run by .github/workflows/release.yml on every push to main (PROTOCOL.md
§ Changing the protocol). For each version in CHANGELOG.md that has no
tag `protocol-v<version>`, it tags the oldest commit on main's first-parent
line whose PROTOCOL.md declares that version, and publishes a release with
the changelog entry and the pin a project adopts it by (§ Adopting). It
then announces the newest version it published in the Protocol category
of the board.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOARD = "Skreen5hot/communications"
CATEGORY = "protocol"
HEADING = re.compile(r"^## (\d+\.\d+) — (\d{4}-\d{2}-\d{2})[ \t]*$", re.M)


def run(*args: str, data: bytes | None = None) -> str:
    return subprocess.run(args, cwd=ROOT, check=True, capture_output=True,
                          input=data).stdout.decode()


def versions(changelog: str) -> list[dict]:
    """Every entry in CHANGELOG.md, newest first: version, date, notes."""
    marks = list(HEADING.finditer(changelog))
    found = []
    for i, mark in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(changelog)
        found.append({"version": mark.group(1), "date": mark.group(2),
                      "notes": changelog[mark.end():end].strip()})
    return found


def declares(text: str, version: str) -> bool:
    return "**Version %s**" % version in text


def target(version: str, branch: str = "origin/main") -> str | None:
    """The oldest first-parent commit whose PROTOCOL.md declares version."""
    for commit in reversed(run("git", "rev-list", "--first-parent",
                               branch).split()):
        try:
            text = run("git", "show", "%s:PROTOCOL.md" % commit)
        except subprocess.CalledProcessError:
            continue
        if declares(text, version):
            return commit
    return None


def pin(commit: str) -> str:
    """The adoption lines for the PROTOCOL.md at commit (§ Adopting)."""
    data = subprocess.run(("git", "show", "%s:PROTOCOL.md" % commit),
                          cwd=ROOT, check=True, capture_output=True).stdout
    added = run("git", "log", "-1", "--format=%H", commit, "--",
                "PROTOCOL.md").strip()
    return ("Skreen5hot/communications, PROTOCOL.md at %s, sha256 %s."
            % (added, hashlib.sha256(data).hexdigest()))


def notes(entry: dict, commit: str) -> str:
    return ("%s\n\n## Adopting %s\n\nIn your `communications/README.md`:\n\n"
            "```markdown\nThis record follows the communications protocol, "
            "version %s:\n%s\n```\n\nSee PROTOCOL.md § Adopting.\n"
            % (entry["notes"], entry["version"], entry["version"],
               pin(commit)))


def tags() -> set[str]:
    return set(run("git", "tag", "--list", "protocol-v*").split())


def announce(entry: dict, url: str) -> None:
    owner, name = BOARD.split("/")
    query = """query($o: String!, $n: String!) { repository(owner: $o, name: $n) {
        id discussionCategories(first: 50) { nodes { id slug } } } }"""
    repo = json.loads(run("gh", "api", "graphql", "-f", "query=" + query,
                          "-F", "o=" + owner, "-F", "n=" + name))
    repo = repo["data"]["repository"]
    category = next((c["id"] for c in repo["discussionCategories"]["nodes"]
                     if c["slug"] == CATEGORY), None)
    if category is None:
        print("no '%s' category; not announced" % CATEGORY)
        return
    body = ("Version %s of the communications protocol is published: %s\n\n"
            "It takes effect in a project when that project adopts it "
            "(PROTOCOL.md § Adopting).\n\n%s\n"
            % (entry["version"], url, entry["notes"]))
    mutation = """mutation($r: ID!, $c: ID!, $t: String!, $b: String!) {
        createDiscussion(input: {repositoryId: $r, categoryId: $c,
                                 title: $t, body: $b}) { discussion { url } } }"""
    run("gh", "api", "graphql", "-f", "query=" + mutation,
        "-f", "r=" + repo["id"], "-f", "c=" + category,
        "-f", "t=Protocol %s published" % entry["version"], "-f", "b=" + body)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--branch", default="origin/main")
    args = ap.parse_args(argv)
    entries = versions((ROOT / "CHANGELOG.md").read_text(encoding="utf-8"))
    have, published, pending = tags(), [], 0
    for entry in reversed(entries):  # oldest first, so releases list in order
        tag = "protocol-v%s" % entry["version"]
        if tag in have:
            continue
        commit = target(entry["version"], args.branch)
        if commit is None:
            print("%s: no commit on main declares it; skipped" % tag)
            continue
        print("%s -> %s" % (tag, commit))
        pending += 1
        if args.dry_run:
            print(notes(entry, commit))
            continue
        url = run("gh", "release", "create", tag, "--target", commit,
                  "--title", "Protocol %s" % entry["version"],
                  "--notes-file", "-",
                  data=notes(entry, commit).encode()).strip()
        print(url)
        published.append((entry, url))
    if published and not args.dry_run:
        announce(*published[-1])
    if not pending:
        print("nothing to publish")
    return 0


if __name__ == "__main__":
    sys.exit(main())
