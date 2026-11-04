# SPDX-License-Identifier: MIT
"""Offline checks of the board tools and of correspondents.yaml.

    python -m unittest discover tests
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import yaml  # noqa: E402

import board  # noqa: E402

MESSAGE = textwrap.dedent("""\
    ---
    id: SDD-OT-2026-10-27-cco-class-hierarchy-register
    from: SDD
    to: OT
    date: 2026-10-27
    type: request
    subject: Vendor the CCO class hierarchy
    in_reply_to: null
    refs: []
    author: Claude (agent), drafted at the direction of Aaron Damiano
    requires_act: true
    ---

    Please vendor it.
    """).encode()


def run(cwd, *args):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


class Repo:
    """A throwaway git repository holding one committed message."""

    def __init__(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name)
        run(self.path, "git", "init", "-q")
        run(self.path, "git", "config", "user.email", "t@example.org")
        run(self.path, "git", "config", "user.name", "t")
        run(self.path, "git", "remote", "add", "origin",
            "https://github.com/Skreen5hot/SemanticDataDictionary.git")
        self.message = (self.path / "communications" / "ot" / "outgoing"
                        / "2026-10-27-cco-class-hierarchy-register.md")
        self.message.parent.mkdir(parents=True)
        self.message.write_bytes(MESSAGE)
        run(self.path, "git", "add", ".")
        run(self.path, "git", "commit", "-qm", "message")


class CorrespondentsTest(unittest.TestCase):
    def test_well_formed(self):
        self.assertEqual(board.check_correspondents(), [])

    def test_aliases_name_the_team(self):
        self.assertEqual(board.names_for("EXAMPLE"), {"OT", "EXAMPLE"})
        self.assertEqual(board.names_for("OT"), {"OT", "EXAMPLE"})

    def test_discussion_template_is_yaml(self):
        for path in (ROOT / ".github" / "DISCUSSION_TEMPLATE").glob("*.yml"):
            self.assertIsInstance(yaml.safe_load(path.read_text()), dict)


class AlertTest(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        self.addCleanup(self.repo.dir.cleanup)

    def test_alert_names_the_commit_and_digest(self):
        alert = board.build_alert(self.repo.message)
        self.assertEqual(alert["record"]["repo"],
                         "Skreen5hot/SemanticDataDictionary")
        self.assertEqual(alert["record"]["sha256"],
                         hashlib.sha256(MESSAGE).hexdigest())
        self.assertRegex(alert["record"]["commit"], r"^[0-9a-f]{40}$")
        self.assertIn("/blob/%s/" % alert["record"]["commit"], alert["link"])
        self.assertEqual(board.title(alert),
                         "[SDD→OT] SDD-OT-2026-10-27-cco-class-hierarchy-"
                         "register — Vendor the CCO class hierarchy")

    def test_rendered_alert_reads_back(self):
        alert = board.build_alert(self.repo.message)
        self.assertEqual(board.alerts_in(board.render(alert)), [alert])

    def test_an_uncommitted_change_is_refused(self):
        self.repo.message.write_bytes(MESSAGE + b"tidied\n")
        with self.assertRaisesRegex(ValueError, "not committed"):
            board.build_alert(self.repo.message)

    def test_an_edited_message_is_refused(self):
        self.repo.message.write_bytes(MESSAGE + b"tidied\n")
        run(self.repo.path, "git", "commit", "-qam", "edit")
        with self.assertRaisesRegex(ValueError, "Rule 1"):
            board.build_alert(self.repo.message)

    def test_remote_urls(self):
        for url in ("git@github.com:Skreen5hot/communications.git",
                    "https://github.com/Skreen5hot/communications",
                    "http://proxy@127.0.0.1:1234/git/Skreen5hot/communications"):
            self.assertEqual(board.repo_slug(url), "Skreen5hot/communications")


class InboxTest(unittest.TestCase):
    def setUp(self):
        self.repo = Repo()
        self.addCleanup(self.repo.dir.cleanup)
        self.alert = board.build_alert(self.repo.message)
        self.discussions = [{"id": "D1", "url": "https://example.org/d/1",
                             "title": board.title(self.alert),
                             "body": board.render(self.alert),
                             "comments": [{"body": "Seen, thanks."}]}]
        self.record = Path(tempfile.mkdtemp())

    def receive(self, team: str, digest: str):
        incoming = self.record / team / "incoming"
        incoming.mkdir(parents=True, exist_ok=True)
        header = {"id": "SDD-EXAMPLE-2026-10-27-x", "source": {
            "repo": "r", "commit": "0" * 40, "path": "p", "sha256": digest}}
        (incoming / "2026-10-27-x.md").write_text(
            "---\n%s---\n\nbody\n" % yaml.safe_dump(header))

    def test_waiting_until_recorded(self):
        waiting = board.unrecorded(self.discussions, "OT", self.record)
        self.assertEqual([a["id"] for a in waiting], [self.alert["id"]])
        self.assertEqual(waiting[0]["_discussion"], "https://example.org/d/1")
        self.receive("sdd", self.alert["record"]["sha256"])
        self.assertEqual(board.unrecorded(self.discussions, "OT",
                                          self.record), [])

    def test_alias_receives(self):
        self.assertEqual(len(board.unrecorded(self.discussions, "EXAMPLE",
                                              self.record)), 1)

    def test_other_teams_do_not(self):
        self.assertEqual(board.unrecorded(self.discussions, "BCO",
                                          self.record), [])

    def test_a_copy_of_something_else_does_not_count(self):
        self.receive("sdd", "f" * 64)
        self.assertEqual(len(board.unrecorded(self.discussions, "OT",
                                              self.record)), 1)

    def test_thread_lookup(self):
        self.assertIs(board.find_thread(self.discussions, self.alert["id"]),
                      self.discussions[0])
        self.assertIsNone(board.find_thread(self.discussions, "NOPE"))

    def test_malformed_blocks_are_not_alerts(self):
        self.assertEqual(board.alerts_in("```yaml\nid: x\n```"), [])
        self.assertEqual(board.alerts_in("```yaml\n: : :\n```"), [])


if __name__ == "__main__":
    unittest.main()
