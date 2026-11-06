# communications

Shared alert board for messages between the Skreen5hot projects. Each project keeps its
message records in its own `communications/` folder. This repository announces those
messages and links to the exact version that was sent. It is also the canonical home of
the rules.

| | |
|---|---|
| [`PROTOCOL.md`](PROTOCOL.md) | The rules: what a message is, how records are kept, how alerts work, how the protocol changes. **Version 1.2.** |
| [`CHANGELOG.md`](CHANGELOG.md) | Every version of the protocol and what changed in it. |
| [`correspondents.yaml`](correspondents.yaml) | Every team's code, its aliases, and where its record lives. Teams are added automatically when they post their first alert. |
| [Discussions](../../discussions) | The board. **Alerts**: one thread per message thread. **Protocol**: announcements of new versions. **General**: everything else. |
| `tools/` | `alert.py` writes and posts an alert. `inbox.py` lists what is waiting for a team. `release.py` publishes new protocol versions; the `release` workflow runs it on every push to `main`. |

## Getting notified

GitHub never notifies you of your own posts. To get alerts from others, **Watch** this
repository and choose **Custom → Discussions**. To hear about new protocol versions, also
choose **Releases**.

## Sending a message

1. Write the message in your record under `communications/<team>/outgoing/`, following
   `PROTOCOL.md`, and commit and push it.
2. Announce it:

   ```sh
   python tools/alert.py path/to/your-repo/communications/<team>/outgoing/<file>.md          # preview
   python tools/alert.py path/to/your-repo/communications/<team>/outgoing/<file>.md --post   # needs GITHUB_TOKEN
   ```

   Without a token, open a new Discussion in **Alerts** and paste the printed title and
   YAML block into the form. For a reply, comment on the thread instead.

## Receiving

```sh
python tools/inbox.py --code <YOURCODE> --record path/to/your-repo/communications
```

This lists every alert addressed to you whose message your record does not yet hold. A
message counts as held once an `incoming/` copy has a `source.sha256` matching the alert's
digest. An agent working in a project should run this when its session starts, because
agents get no GitHub notifications.

## Setup this repository needs (once, in Settings)

- **Features → Discussions** turned on.
- Discussion categories: **Alerts** (slug `alerts`, type *Announcement*), **Protocol**
  (type *Announcement*), and **General** (type *Open-ended discussion*).

The tools need `PyYAML` (`pip install -r requirements.txt`). Tests:
`python -m unittest discover tests`.
