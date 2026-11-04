# The communications protocol

**Version 1.0** · the canonical text · changes are listed in [`CHANGELOG.md`](CHANGELOG.md)

How the Skreen5hot projects record what they say to, and hear from, each other, and how
they alert each other that something was said. Every project that corresponds keeps its own
record, under its own `communications/`, by these rules. This repository holds the rules,
the list of team codes, and the board where messages are announced. It holds no messages.

Version 1.0 is the protocol as the Ontology Template wrote it
(`Skreen5hot/Ontology-Template`, `communications/README.md` at
`43eecfadcc0bb97b1ca8838129e77622ba87853b`, sha256
`150a312b30990469e4e68222a9ea485d6766579900749bd7413f4e4dd2ff57a8`). It is generalized
so it no longer depends on any one repository's layout, and it adds team codes (§ Codes)
and alerts (§ Alerts).

---

## The record

```text
communications/
  README.md                 names the protocol version this record follows (§ Adopting)
  <team>/README.md          who the team is and where its repository lives
  <team>/incoming/          messages received, copied verbatim with their source
  <team>/outgoing/          messages sent
```

One folder for each team the project corresponds with, named by the team's code in
lowercase. Nothing in the record is published.

## A message

One Markdown file: a YAML header between `---` lines, then the body.

**Filename**: `YYYY-MM-DD-<slug>.md`. The date is the day the message was sent or
received; the slug is short and lowercase (`a-z`, `0-9`, `-`). The folder says the team
and the direction.

**Header**: a real example, from the Business Capability Ontology (`BCO`) to the Business
Process Ontology (`BPO`).

```yaml
---
id: BCO-BPO-2026-10-23-vendoring-pin   # <FROM>-<TO>-<date>-<slug>; must match the path
from: BCO
to: BPO
date: 2026-10-23                        # must match the filename
type: request                           # request | finding | answer | notice | acknowledgment
subject: One line, what this is about
in_reply_to: null                       # the id of the message this answers, or null
refs:                                   # what the message is about, bound by digest
  - repo: Skreen5hot/BusinessProcessOntology
    commit: 66131945b525c54f44e4962f32bb1f52dfa0cd12
    path: ontology/apqc-ext.ttl
    sha256: 1b9a9375cb7303003556004effd712b63913d6aa4935dbf604a653aec65cab4b
author: Aaron Damiano                   # a person, or an agent named as an agent
requires_act: false                     # true when only the architect can answer it
---
```

An incoming message has one more field, `source`, saying where the original lives:

```yaml
source:
  repo: Skreen5hot/BusinessProcessOntology
  commit: <the commit the original was read at>
  path: <its path there>
  sha256: <SHA-256 of the original file's bytes>
```

The body below the header is that original, byte for byte. A checker recomputes the
digest of the body and requires it to equal `source.sha256`. A copy that has been
"tidied" therefore fails, instead of quietly standing in for what was sent.

## Rules

1. **A committed message never changes.** A correction is a new message whose `in_reply_to`
   names the message it corrects. A checker reads git history and refuses a message file
   that more than one commit has touched.
2. **Status is derived, not written.** A `request` or `finding` is *open* until a later
   message answers it (its `in_reply_to` is the id) with type `answer` or
   `acknowledgment`. There is no status field to forget to update.
3. **Every ref is digest-bound.** A path with no commit and no SHA-256 names whatever is
   there today. A ref into the project's own repository is recomputed from
   `git show <commit>:<path>`. A ref into another repository is checked for shape and can
   be verified there.
4. **A message is not a decision.** It can ask for one (`requires_act: true`). The decision
   itself is the architect's, goes in the project's decision record, and cites the message
   by id.
5. **Agents are named as agents.** A message drafted by an agent says so in `author`, and
   says at whose direction it was drafted. The same applies to an agent's alert or comment
   on the board.
6. **Sending is outside the record.** An outgoing message is the record of what was said.
   It is announced on the board (§ Alerts), and it may also reach the team some other way.
   The record does not claim delivery. An alert does not claim it either.

## Codes

Every team has one **code**: uppercase letters and digits, the name other teams know it
by. Codes are listed in [`correspondents.yaml`](correspondents.yaml), and that list is the
authority. A team's code is the one it uses for itself in its own messages.

Before version 1.0, some records used a different code for a team than the team used for
itself. For example, the Ontology Template's record calls the template `EXAMPLE` and the
SDD team calls it `OT`. Those other names are listed as the team's `aliases`. A record may
keep using an alias it already uses. A new record uses the code.

Adding a team means adding an entry to `correspondents.yaml` here and adding the team
folder in each record that corresponds with it.

## Alerts

The board is the Discussions tab of this repository. It tells a team that a message is
waiting. It is not the message.

1. **One Discussion per thread.** A message whose `in_reply_to` is null opens a Discussion
   in the **Alerts** category. Every later message in that thread (answer, correction,
   acknowledgment) is announced as a comment on that same Discussion. Anyone who has taken
   part in a thread is then notified of the rest of it. A reply to a message that was
   never announced (one sent before the board existed, for example) opens its own
   Discussion.
2. **The title carries the ids:** `[FROM→TO] <id> — <subject>`, using the root message's
   id. A search on a code or an id then finds the thread.
3. **The alert is a YAML block** with the message's header fields and its exact location
   in the sender's record:

   ```yaml
   id: BCO-BPO-2026-10-23-vendoring-pin
   from: BCO
   to: BPO
   type: request
   subject: One line, what this is about
   in_reply_to: null
   requires_act: false
   author: Aaron Damiano
   record:
     repo: Skreen5hot/Business-and-Agent-Capabilities-Ontology
     commit: <the commit that added the message file>
     path: communications/bpo/outgoing/2026-10-23-vendoring-pin.md
     sha256: <SHA-256 of the file's bytes at that commit>
   link: https://github.com/<repo>/blob/<commit>/<path>
   ```

   The link names a commit, never a branch, for the same reason as Rule 3. When the
   sender's repository is private, the link will not open for everyone, but the digest
   still binds the alert to the message.
4. **The alert is never the message.** The board holds no body. A recipient records the
   message in `incoming/` from the original that `record` names. The recorded copy's
   `source.sha256` then equals the alert's `record.sha256`, and that equality is how a
   team's inbox knows the alert has been dealt with.
5. **The board holds no status.** Marking a Discussion answered, closing it, or reacting to
   it means only that someone *saw* it. Under Rule 2, a thread closes only when a message
   in the record closes it.
6. **Talk is welcome in the thread.** Conversation in the comments is fine, but anything
   formal is a message. Category **General** is for anything that is not an alert.

`tools/alert.py` writes the alert for a message file and can post it.
`tools/inbox.py` lists the alerts addressed to a team that its record does not yet hold.
Run it when a session starts. An agent gets no GitHub notifications, so it has to check.

**Being notified.** GitHub does not notify you of your own activity. To be told of alerts,
watch this repository and choose *Custom → Discussions*. To be told when the protocol
changes, also choose *Releases*. Notification preferences belong to each person; posting
an alert does not guarantee anyone sees it.

## Changing the protocol

This file is the only copy of the rules that has authority.

- A change is a pull request to this repository. It edits this file, adds an entry to
  `CHANGELOG.md`, and raises the version: the minor number for a change every existing
  record still satisfies, the major number for one it may not.
- A merged version is tagged `protocol-v<version>` and published as a GitHub Release.
  That is what *Watch → Releases* notifies people of. It is also announced in the
  **Protocol** category of the board.
- A change takes effect in a project when that project adopts it (§ Adopting). No record
  is out of date just because a newer version exists.

## Adopting

A project's `communications/README.md` names the version it follows, the way a ref names
a file:

```markdown
This record follows the communications protocol, version 1.0:
Skreen5hot/communications, PROTOCOL.md at <commit>, sha256 <digest>.
```

It may add rules of its own, provided they do not contradict these, and it states those
rules there. Adopting a later version is a commit that changes those lines.
