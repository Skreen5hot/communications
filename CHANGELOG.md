# Changelog

Versions of [`PROTOCOL.md`](PROTOCOL.md). Each version is tagged `protocol-v<version>` and
published as a GitHub Release.

## 1.2 — 2026-11-06

- **Codes: a team registers by speaking.** A team's first alert on the board adds it to
  `correspondents.yaml`, through the new `register` workflow. The repository is the team's
  identity: a new code from a known repository becomes an alias, and a known code from
  another repository is a clash that is reported and not registered. People edit the file
  only for names, teams without a repository, and clashes.
- **Tools.** `tools/register.py` does the registering. `alert.py` now says that posting an
  alert registers an unknown sender, instead of warning about it.

Every record that satisfied 1.1 still satisfies 1.2.

## 1.1 — 2026-11-04

These come from the first adoption, by SDD. Every record that satisfied 1.0 still satisfies 1.1.

- **Rule 1, moves and deletions.** A checker follows renames, and a message may move only
  with its bytes unchanged. Before 1.1, counting commits by path meant a rename gave a
  message a fresh history, so a rename that also edited it went unnoticed. A message is
  never deleted. A file that was never a message may be, and the commit that removes it
  says so.
- **Rule 7, digests are of committed bytes.** On a Windows checkout with CRLF line
  endings, `PROTOCOL.md` on disk did not match its published digest. Digests are now
  always computed with `git show`. Records keep `communications/` byte for byte
  (`communications/** -text`), and so does this repository (`* -text`).
- **Alerts.** A message sent before the board existed needs no alert.
- **Tools.** `alert.py` follows renames: a byte-identical move is accepted, and a move
  that also edits the message is refused. The alert names the latest commit at which
  the message sits at its current path.

## 1.0 — 2026-11-04

The first canonical version. It is the protocol from `Skreen5hot/Ontology-Template`,
`communications/README.md` at `43eecfadcc0bb97b1ca8838129e77622ba87853b`, with these
changes:

- **Generalized.** The rules no longer name the template's files (`config/project.yaml`,
  `tools/communications.py`, `docs/decisions/`). Rule 4 says "the project's decision
  record".
- **Codes.** `correspondents.yaml` is now the shared list of team codes. Codes that
  existing records already use, such as `EXAMPLE` for `OT` and `BPOTEST` for `BPOT`, are
  kept as aliases.
- **Alerts.** Messages are announced on this repository's Discussions board: one
  Discussion per thread, a YAML alert pointing at a fixed commit and carrying the file's
  digest, and no status on the board. Rule 6 now names the board, and Rule 5 also applies
  to alerts.
- **Changing and adopting.** The protocol changes only here, by version. A record states
  the version it follows, bound by commit and digest.

Every record that satisfied the template's protocol still satisfies 1.0.
