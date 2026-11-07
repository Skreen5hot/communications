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

    def move(self, edit: bytes = b""):
        moved = self.repo.message.parent.parent.parent / "OT2" / "outgoing"
        moved.mkdir(parents=True)
        target = moved / self.repo.message.name
        run(self.repo.path, "git", "mv", str(self.repo.message), str(target))
        if edit:
            target.write_bytes(MESSAGE + edit)
        run(self.repo.path, "git", "commit", "-qam", "move")
        return target

    def test_a_move_with_the_same_bytes_is_accepted(self):
        target = self.move()
        alert = board.build_alert(target)
        self.assertEqual(alert["record"]["sha256"],
                         hashlib.sha256(MESSAGE).hexdigest())
        self.assertTrue(alert["record"]["path"].startswith(
            "communications/OT2/"))
        head = subprocess.run(("git", "rev-parse", "HEAD"), cwd=self.repo.path,
                              capture_output=True, text=True).stdout.strip()
        self.assertEqual(alert["record"]["commit"], head)

    def test_a_move_that_edits_is_refused(self):
        target = self.move(b"tidied on the way\n")
        with self.assertRaisesRegex(ValueError, "even when it moves"):
            board.build_alert(target)

    def test_an_edit_reverted_is_still_an_edit(self):
        self.repo.message.write_bytes(MESSAGE + b"tidied\n")
        run(self.repo.path, "git", "commit", "-qam", "edit")
        self.repo.message.write_bytes(MESSAGE)
        run(self.repo.path, "git", "commit", "-qam", "revert")
        with self.assertRaisesRegex(ValueError, "Rule 1"):
            board.build_alert(self.repo.message)

    def copy(self, edit: bytes = b""):
        """A new message that repeats this one, as a correction does."""
        target = self.repo.message.with_name(
            "2026-10-27-cco-class-hierarchy-register-corrected.md")
        target.write_bytes(MESSAGE.replace(
            b"register\nfrom", b"register-corrected\nfrom") + b"\nCorrected.\n")
        run(self.repo.path, "git", "add", ".")
        run(self.repo.path, "git", "commit", "-qm", "correction")
        if edit:
            target.write_bytes(target.read_bytes() + edit)
            run(self.repo.path, "git", "commit", "-qam", "edit")
        return target

    def test_a_copy_of_another_message_is_a_new_message(self):
        target = self.copy()
        statuses = [s for _, _, s in board.contents(
            self.repo.path, target.relative_to(self.repo.path).as_posix())]
        self.assertEqual(len(statuses), 1)
        self.assertTrue(statuses[0] == "A" or statuses[0].startswith("C"))
        alert = board.build_alert(target)
        self.assertEqual(alert["record"]["sha256"],
                         hashlib.sha256(target.read_bytes()).hexdigest())
        self.assertEqual(alert["id"],
                         "SDD-OT-2026-10-27-cco-class-hierarchy-register-corrected")

    def test_a_copy_edited_later_is_refused(self):
        target = self.copy(b"tidied\n")
        with self.assertRaisesRegex(ValueError, "Rule 1"):
            board.build_alert(target)

    def test_prints_on_a_windows_code_page(self):
        result = subprocess.run(
            (sys.executable, str(ROOT / "tools" / "alert.py"),
             str(self.repo.message)), capture_output=True,
            env={**__import__("os").environ, "PYTHONIOENCODING": "cp1252"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("[SDD→OT]".encode(), result.stdout)

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


def fake_alert(code, repo, mid="X-Y-2026-11-06-a"):
    return {"id": mid, "from": code, "to": "OT", "type": "notice",
            "subject": "s", "in_reply_to": None, "requires_act": False,
            "author": "a", "link": "l",
            "record": {"repo": repo, "commit": "0" * 40, "path": "p",
                       "sha256": "0" * 64}}


class RegisterTest(unittest.TestCase):
    def setUp(self):
        import register
        self.register = register
        self.text = (ROOT / "correspondents.yaml").read_text()
        self.teams = yaml.safe_load(self.text)["teams"]

    def run_plan(self, *alerts):
        return self.register.plan(self.teams, list(alerts))

    def test_names(self):
        name = self.register.display_name
        self.assertEqual(name("Skreen5hot/edge-project-store"),
                         "Edge Project Store")
        self.assertEqual(name("Skreen5hot/SemanticDataDictionary"),
                         "Semantic Data Dictionary")

    def test_a_new_team_registers_and_the_file_stays_valid(self):
        new, aliases, clashes = self.run_plan(
            fake_alert("EPS", "Skreen5hot/edge-project-store"),
            fake_alert("EPS", "Skreen5hot/edge-project-store", "second"))
        self.assertEqual([t["code"] for t in new], ["EPS"])
        self.assertEqual((aliases, clashes), ([], []))
        text = self.register.apply(self.text, new, aliases)
        self.assertTrue(text.startswith(self.text))  # comments kept
        path = Path(tempfile.mkdtemp()) / "c.yaml"
        path.write_text(text)
        self.assertEqual(board.check_correspondents(path), [])
        eps = [t for t in board.teams(path) if t["code"] == "EPS"][0]
        self.assertEqual((eps["name"], eps["repository"], eps["delivery"]),
                         ("Edge Project Store",
                          "Skreen5hot/edge-project-store", "board"))

    def test_known_codes_change_nothing(self):
        self.assertEqual(self.run_plan(
            fake_alert("SDD", "Skreen5hot/SemanticDataDictionary"),
            fake_alert("EXAMPLE", "Skreen5hot/Ontology-Template")),
            ([], [], []))

    def test_a_new_code_from_a_known_repository_is_an_alias(self):
        new, aliases, _ = self.run_plan(
            fake_alert("SDDX", "Skreen5hot/SemanticDataDictionary"))
        self.assertEqual(new, [])
        text = self.register.apply(self.text, new, aliases)
        path = Path(tempfile.mkdtemp()) / "c.yaml"
        path.write_text(text)
        self.assertEqual(board.names_for("SDDX", path), {"SDD", "SDDX"})
        self.assertEqual(board.names_for("OT", path), {"OT", "EXAMPLE"})

    def test_a_known_code_from_another_repository_is_a_clash(self):
        new, aliases, clashes = self.run_plan(
            fake_alert("SDD", "Someone/else"))
        self.assertEqual((new, aliases), ([], []))
        self.assertIn("registered to Skreen5hot/SemanticDataDictionary",
                      clashes[0])


class ReleaseTest(unittest.TestCase):
    def test_every_changelog_version_is_found(self):
        import release
        entries = release.versions((ROOT / "CHANGELOG.md").read_text())
        self.assertGreaterEqual(len(entries), 2)
        self.assertTrue(all(e["notes"] for e in entries))
        newest = entries[0]["version"]
        self.assertTrue(release.declares((ROOT / "PROTOCOL.md").read_text(),
                                         newest),
                        "PROTOCOL.md does not declare the newest changelog "
                        "version, %s" % newest)

    def test_headings(self):
        import release
        found = release.versions("# C\n\n## 2.0 — 2027-01-01\n\nB\n\n"
                                 "## 1.9 — 2026-12-01\n\nA\n")
        self.assertEqual([(e["version"], e["notes"]) for e in found],
                         [("2.0", "B"), ("1.9", "A")])


if __name__ == "__main__":
    unittest.main()
