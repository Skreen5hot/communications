# SPDX-License-Identifier: MIT
"""Register every team the board has heard from (PROTOCOL.md § Codes).

    python tools/register.py                    # read the board, update the file
    python tools/register.py --board-json F     # from a saved board instead
    python tools/register.py --dry-run          # say what would change

A team registers by announcing its first message. Its code is the alert's
`from`, and its repository is the alert's `record.repo`. The repository is the
team's identity:

- an unknown code from an unregistered repository  -> a new team
- an unknown code from a registered repository     -> an alias of that team
- a known code from a different repository         -> a clash: not registered,
                                                      reported for a person

Run by .github/workflows/register.yml whenever something is posted on the
board. It is idempotent: an alert already reflected in the file changes
nothing. The file is edited as text, so its comments and layout survive.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import board  # noqa: E402


def display_name(repo: str) -> str:
    """'Skreen5hot/edge-project-store' -> 'Edge Project Store'."""
    name = repo.split("/")[-1]
    name = re.sub(r"[-_.]+", " ", name)
    name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)
    return " ".join(w[:1].upper() + w[1:] for w in name.split())


def plan(teams: list[dict], alerts: list[dict]) -> tuple[list, list, list]:
    """(new teams, new aliases, clashes) the alerts call for."""
    by_name = {}
    by_repo = {}
    for team in teams:
        for name in [team["code"], *(team.get("aliases") or [])]:
            by_name[name] = team
        if team.get("repository"):
            by_repo[team["repository"].lower()] = team
    new, aliases, clashes = [], [], []
    for alert in alerts:
        code, repo = alert["from"], alert["record"]["repo"]
        if not isinstance(code, str) or not board.CODE.match(code):
            clashes.append("%s: from %r is not an uppercase code"
                           % (alert["id"], code))
            continue
        known = by_name.get(code)
        owner = by_repo.get(repo.lower())
        if known is not None:
            if known.get("repository") and known["repository"].lower() \
                    != repo.lower():
                clashes.append(
                    "%s: %s is registered to %s, but this alert comes from %s"
                    % (alert["id"], code, known["repository"], repo))
            continue
        if owner is not None:
            entry = {"code": owner["code"], "alias": code, "id": alert["id"]}
            owner.setdefault("aliases", []).append(code)
            by_name[code] = owner
            aliases.append(entry)
            continue
        team = {"code": code, "name": display_name(repo), "repository": repo,
                "aliases": [], "delivery": "board", "id": alert["id"]}
        by_name[code] = team
        by_repo[repo.lower()] = team
        new.append(team)
    return new, aliases, clashes


def apply(text: str, new: list[dict], aliases: list[dict]) -> str:
    for entry in aliases:
        block = re.search(r"^  - code: %s[ \t]*\n(?:    .*\n)*?    aliases: "
                          r"\[([^\]\n]*)\]" % re.escape(entry["code"]),
                          text, re.M)
        if block is None:
            raise ValueError("cannot find the aliases line for %s"
                             % entry["code"])
        current = [a.strip() for a in block.group(1).split(",") if a.strip()]
        start, end = block.span(1)
        text = text[:start] + ", ".join(current + [entry["alias"]]) \
            + text[end:]
    if not text.endswith("\n"):
        text += "\n"
    for team in new:
        text += ("\n  - code: %s\n    name: %s\n    repository: %s\n"
                 "    aliases: []\n    delivery: board"
                 "   # registered by %s\n"
                 % (team["code"], team["name"], team["repository"],
                    team["id"]))
    return text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--board", default=board.BOARD)
    ap.add_argument("--board-json", type=Path)
    ap.add_argument("--file", type=Path, default=board.CORRESPONDENTS)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    discussions = (json.loads(args.board_json.read_text(encoding="utf-8"))
                   if args.board_json else board.fetch(args.board))
    alerts = [a for d in discussions for a in board.thread_alerts(d)]
    new, aliases, clashes = plan(board.teams(args.file), alerts)
    for team in new:
        print("register %s (%s) from %s" % (team["code"], team["repository"],
                                             team["id"]))
    for entry in aliases:
        print("alias %s for %s from %s" % (entry["alias"], entry["code"],
                                           entry["id"]))
    for clash in clashes:
        print("::warning title=Code clash::%s" % clash)
    if not new and not aliases:
        print("nothing to register")
        return 0
    text = apply(args.file.read_text(encoding="utf-8"), new, aliases)
    if args.dry_run:
        print(text)
        return 0
    args.file.write_bytes(text.encode("utf-8"))  # LF on every platform
    problems = board.check_correspondents(args.file)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
