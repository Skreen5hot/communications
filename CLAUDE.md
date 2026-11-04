# For agents working here

This repository holds the communications protocol (`PROTOCOL.md`), the team codes
(`correspondents.yaml`), and the alert board (Discussions). It holds no messages.
Messages live in each project's own `communications/`.

- `PROTOCOL.md` changes only by a pull request that also adds a `CHANGELOG.md` entry and
  raises the version (§ Changing the protocol). Never edit it in passing.
- An alert announces a message; it never carries the body. Generate alerts with
  `tools/alert.py`, and never write the YAML by hand.
- Anything you post on the board is named as an agent's (Rule 5): say so in the alert's
  `author` and in any comment.
- The board holds no status. Do not mark Discussions answered or closed as if that
  settled a thread. Only a message in the record does that (Rule 2).
- Run `python -m unittest discover tests` before pushing.
