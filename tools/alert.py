# SPDX-License-Identifier: MIT
"""Write the alert for a committed message, and optionally post it.

    python tools/alert.py <message.md>                 # print title and body
    python tools/alert.py <message.md> --post          # post to the board
    python tools/alert.py <message.md> --post --new-thread

Run it from anywhere; the message's own repository supplies the commit, and
its `origin` remote supplies owner/name (or pass --repo). The message must be
committed exactly as it stands, by one commit (PROTOCOL.md Rule 1).

A message with in_reply_to null opens a Discussion. A reply becomes a comment
on the Discussion that announced the message it replies to. Posting needs a
token in GITHUB_TOKEN.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import board  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("message", type=Path)
    ap.add_argument("--repo", help="owner/name of the message's repository")
    ap.add_argument("--post", action="store_true")
    ap.add_argument("--new-thread", action="store_true",
                    help="open a Discussion even though the message replies "
                         "to one never announced")
    ap.add_argument("--board", default=board.BOARD)
    args = ap.parse_args(argv)
    try:
        alert = board.build_alert(args.message, args.repo)
    except (ValueError, board.subprocess.CalledProcessError) as exc:
        print("alert: %s" % exc, file=sys.stderr)
        return 1
    known = {n for t in board.teams()
             for n in [t["code"], *(t.get("aliases") or [])]}
    for side in ("from", "to"):
        if alert[side] not in known:
            print("alert: warning: %s %r is not in correspondents.yaml"
                  % (side, alert[side]), file=sys.stderr)
    if not args.post:
        print(board.title(alert))
        print()
        print(board.render(alert), end="")
        return 0
    url = board.post(alert, board.fetch(args.board), args.new_thread,
                     args.board)
    print(url)
    return 0


if __name__ == "__main__":
    sys.exit(main())
