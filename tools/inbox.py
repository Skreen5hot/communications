# SPDX-License-Identifier: MIT
"""List the alerts addressed to a team that its record does not hold yet.

    python tools/inbox.py --code SDD                          # ./communications
    python tools/inbox.py --code SDD --record ../sdd/communications
    python tools/inbox.py --code SDD --json

An alert counts as recorded when some incoming copy's source.sha256 equals
the alert's record.sha256 (PROTOCOL.md § Alerts, 4). That match uses digests,
not ids, so it still works when the two records use different codes for the
same team. Aliases from correspondents.yaml count as the code.

Run it when a session starts: an agent gets no GitHub notifications, so it
has to check. Reading the board needs a token in GITHUB_TOKEN; --board-json
reads a saved copy instead (the shape fetch() returns).

Exit codes: 0 nothing waiting; 3 something waiting.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import board  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--code", required=True)
    ap.add_argument("--record", type=Path, default=Path("communications"))
    ap.add_argument("--board", default=board.BOARD)
    ap.add_argument("--board-json", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    # Titles carry "→"; a Windows console's code page cannot print it.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    discussions = (json.loads(args.board_json.read_text(encoding="utf-8"))
                   if args.board_json else board.fetch(args.board))
    waiting = board.unrecorded(discussions, args.code, args.record)
    if args.json:
        print(json.dumps(waiting, indent=2, sort_keys=True, default=str))
    elif not waiting:
        print("inbox %s: nothing waiting" % args.code)
    else:
        print("inbox %s: %d message(s) not yet recorded" % (args.code,
                                                            len(waiting)))
        for alert in waiting:
            print("  %s  %s%s" % (alert["id"], alert["subject"],
                                  "  [needs the architect]"
                                  if alert.get("requires_act") else ""))
            print("    message: %s" % alert["link"])
            print("    sha256:  %s" % alert["record"]["sha256"])
            print("    thread:  %s" % alert["_discussion"])
    return 3 if waiting else 0


if __name__ == "__main__":
    sys.exit(main())
