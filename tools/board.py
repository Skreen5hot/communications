# SPDX-License-Identifier: MIT
"""The parts of PROTOCOL.md § Alerts a tool can hold.

Shared by alert.py (write and post an alert) and inbox.py (list the alerts
a team has not recorded). Nothing here holds status: the board says only
that a message exists, and where, by commit and digest.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import ssl
import subprocess
import urllib.request
from pathlib import Path

import yaml

BOARD = "Skreen5hot/communications"
ALERTS = "alerts"  # the Discussion category's slug
HERE = Path(__file__).resolve().parent.parent
CORRESPONDENTS = HERE / "correspondents.yaml"

ALERT_FIELDS = ("id", "from", "to", "type", "subject", "in_reply_to",
                "requires_act", "author", "record", "link")
RECORD_FIELDS = ("repo", "commit", "path", "sha256")
CODE = re.compile(r"^[A-Z][A-Z0-9]*$")
BLOCK = re.compile(r"```ya?ml[ \t]*\n(.*?)```", re.S)


# ------------------------------------------------------------ codes


def teams(path: Path = CORRESPONDENTS) -> list[dict]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))["teams"]


def names_for(code: str, path: Path = CORRESPONDENTS) -> set[str]:
    """A team's code and every alias records already use for it."""
    for team in teams(path):
        if team["code"] == code or code in (team.get("aliases") or []):
            return {team["code"], *(team.get("aliases") or [])}
    return {code}


def check_correspondents(path: Path = CORRESPONDENTS) -> list[str]:
    problems, seen = [], {}
    for number, team in enumerate(teams(path), 1):
        for field in ("code", "name", "repository", "aliases", "delivery"):
            if field not in team:
                problems.append("team %d lacks %s" % (number, field))
        for name in [team.get("code"), *(team.get("aliases") or [])]:
            if not isinstance(name, str) or not CODE.match(name):
                problems.append("team %d: %r is not an uppercase code"
                                % (number, name))
            elif name in seen:
                problems.append("%s names both %s and %s"
                                % (name, seen[name], team.get("code")))
            else:
                seen[name] = team.get("code")
    return problems


# ------------------------------------------------------------ messages


def split_header(data: bytes) -> dict:
    text = data.decode("utf-8")
    if not text.startswith("---"):
        raise ValueError("no YAML header")
    _, header, _ = re.split(r"^---[ \t]*$", text, maxsplit=2, flags=re.M)
    value = yaml.safe_load(header)
    if not isinstance(value, dict):
        raise ValueError("header is not a mapping")
    return value


def git(cwd: Path, *args: str) -> bytes:
    return subprocess.run(("git", *args), cwd=cwd, check=True,
                          capture_output=True).stdout


def repo_slug(remote_url: str) -> str:
    """owner/name from any remote URL: https, ssh, or a proxy path."""
    tail = re.split(r"[/:]", remote_url.strip().rstrip("/"))[-2:]
    owner, name = tail
    return "%s/%s" % (owner, name[:-4] if name.endswith(".git") else name)


def contents(top: Path, relative: str) -> list[tuple[str, str, str]]:
    """(commit, blob, status) for every commit that touched the file, newest
    first, following renames, so a move cannot hide an edit (Rule 1).
    Status is git's: A added, M modified, R100 moved unchanged."""
    out = git(top, "log", "--follow", "--raw", "--no-abbrev", "--format=C %H",
              "--", relative).decode()
    history, commit = [], None
    for line in out.splitlines():
        if line.startswith("C "):
            commit = line[2:]
        elif line.startswith(":") and commit:
            fields = line.split()
            history.append((commit, fields[3], fields[4]))
            commit = None
    return history


def build_alert(message: Path, repo: str | None = None) -> dict:
    """The alert for a committed message file, from the commit that added it."""
    message = message.resolve()
    top = Path(git(message.parent, "rev-parse", "--show-toplevel")
               .decode().strip())
    relative = message.relative_to(top).as_posix()
    if git(top, "status", "--porcelain", "--", relative).strip():
        raise ValueError("%s is not committed as it stands; an alert names "
                         "a commit" % relative)
    history = contents(top, relative)
    if not history:
        raise ValueError("%s has never been committed" % relative)
    edits = [c[:12] for c, _, status in history if status not in ("A", "R100")]
    if edits:
        raise ValueError("%s was changed after it was committed (%s); a "
                         "committed message never changes, even when it "
                         "moves (Rule 1)" % (relative, ", ".join(edits)))
    commit = history[0][0]  # the latest: where it sits at this path
    data = git(top, "show", "%s:%s" % (commit, relative))
    header = split_header(data)
    repo = repo or repo_slug(
        git(top, "remote", "get-url", "origin").decode())
    alert = {f: header.get(f) for f in ALERT_FIELDS[:-2]}
    alert["record"] = {"repo": repo, "commit": commit, "path": relative,
                       "sha256": hashlib.sha256(data).hexdigest()}
    alert["link"] = "https://github.com/%s/blob/%s/%s" % (repo, commit,
                                                          relative)
    return alert


# ------------------------------------------------------------ alerts


def title(alert: dict) -> str:
    return "[%s→%s] %s — %s" % (alert["from"], alert["to"], alert["id"],
                                alert["subject"])


def render(alert: dict) -> str:
    """The Discussion body or comment: one line for people, one block for tools."""
    lines = "%s → %s · %s%s" % (
        alert["from"], alert["to"], alert["type"],
        " · needs the architect" if alert.get("requires_act") else "")
    block = yaml.safe_dump(alert, sort_keys=False, allow_unicode=True,
                           width=1000)
    return "%s\n\nThe message: %s\n\n```yaml\n%s```\n" % (
        lines, alert["link"], block)


def check_alert(alert) -> list[str]:
    if not isinstance(alert, dict):
        return ["is not a mapping"]
    problems = ["lacks %s" % f for f in ALERT_FIELDS if f not in alert]
    record = alert.get("record")
    if not isinstance(record, dict):
        problems.append("record is not a mapping")
    else:
        problems += ["record lacks %s" % f for f in RECORD_FIELDS
                     if not record.get(f)]
        if record.get("commit") and not re.fullmatch(
                r"[0-9a-f]{40}", str(record["commit"])):
            problems.append("record.commit is not a full SHA")
        if record.get("sha256") and not re.fullmatch(
                r"[0-9a-f]{64}", str(record["sha256"])):
            problems.append("record.sha256 is not 64 lowercase hex")
    return problems


def alerts_in(text: str) -> list[dict]:
    """Every well-formed alert block in a Discussion body or comment."""
    found = []
    for block in BLOCK.findall(text or ""):
        try:
            value = yaml.safe_load(block)
        except yaml.YAMLError:
            continue
        if isinstance(value, dict) and not check_alert(value):
            for key, item in value.items():
                if isinstance(item, (dt.date, dt.datetime)):
                    value[key] = item.isoformat()
            found.append(value)
    return found


def thread_alerts(discussion: dict) -> list[dict]:
    texts = [discussion.get("body", "")] + [
        c.get("body", "") for c in discussion.get("comments", [])]
    alerts = []
    for text in texts:
        for alert in alerts_in(text):
            alert["_discussion"] = discussion.get("url")
            alerts.append(alert)
    return alerts


def find_thread(discussions: list[dict], message_id: str) -> dict | None:
    """The Discussion that announced message_id."""
    for discussion in discussions:
        if any(a["id"] == message_id for a in thread_alerts(discussion)):
            return discussion
    return None


# ------------------------------------------------------------ the record


def recorded_sources(record_dir: Path) -> set[str]:
    """source.sha256 of every incoming copy in a local communications/."""
    digests = set()
    for path in record_dir.glob("*/incoming/*.md"):
        try:
            source = split_header(path.read_bytes()).get("source") or {}
        except (ValueError, UnicodeDecodeError, yaml.YAMLError):
            continue
        if isinstance(source, dict) and source.get("sha256"):
            digests.add(str(source["sha256"]))
    return digests


def unrecorded(discussions: list[dict], code: str, record_dir: Path,
               path: Path = CORRESPONDENTS) -> list[dict]:
    """Alerts addressed to code whose message its record does not hold."""
    names = names_for(code, path)
    held = recorded_sources(record_dir) if record_dir.is_dir() else set()
    return [a for d in discussions for a in thread_alerts(d)
            if a["to"] in names and a["record"]["sha256"] not in held]


# ------------------------------------------------------------ GitHub


def token() -> str:
    value = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if value:
        return value
    try:
        return subprocess.run(("gh", "auth", "token"), check=True,
                              capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        raise SystemExit("no GitHub token: set GITHUB_TOKEN (Discussions are "
                         "read and written through the GraphQL API, which "
                         "needs one even for a public repository)")


def graphql(query: str, variables: dict) -> dict:
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": "Bearer %s" % token(),
                 "Content-Type": "application/json",
                 "User-Agent": "communications-board"})
    cafile = os.environ.get("SSL_CERT_FILE")
    context = ssl.create_default_context(cafile=cafile) if cafile else None
    with urllib.request.urlopen(request, context=context) as response:
        reply = json.load(response)
    if reply.get("errors"):
        raise SystemExit("GitHub: %s" % "; ".join(
            e.get("message", str(e)) for e in reply["errors"]))
    return reply["data"]


def board_ids(board: str = BOARD) -> tuple[str, str]:
    owner, name = board.split("/")
    data = graphql("""
      query($owner: String!, $name: String!) {
        repository(owner: $owner, name: $name) {
          id
          discussionCategories(first: 50) { nodes { id slug } }
        }
      }""", {"owner": owner, "name": name})
    repo = data["repository"]
    for category in repo["discussionCategories"]["nodes"]:
        if category["slug"] == ALERTS:
            return repo["id"], category["id"]
    raise SystemExit("%s has no '%s' Discussion category; create it in the "
                     "repository's Discussions settings" % (board, ALERTS))


def fetch(board: str = BOARD) -> list[dict]:
    """Every Discussion in the Alerts category, with its comments."""
    owner, name = board.split("/")
    _, category = board_ids(board)
    discussions, after = [], None
    while True:
        data = graphql("""
          query($owner: String!, $name: String!, $cat: ID!, $after: String) {
            repository(owner: $owner, name: $name) {
              discussions(first: 50, after: $after, categoryId: $cat) {
                pageInfo { hasNextPage endCursor }
                nodes { id url title body
                        comments(first: 100) { nodes { body } } }
              }
            }
          }""", {"owner": owner, "name": name, "cat": category,
                 "after": after})["repository"]["discussions"]
        for node in data["nodes"]:
            node["comments"] = node["comments"]["nodes"]
            discussions.append(node)
        if not data["pageInfo"]["hasNextPage"]:
            return discussions
        after = data["pageInfo"]["endCursor"]


def post(alert: dict, discussions: list[dict], new_thread: bool = False,
         board: str = BOARD) -> str:
    """Open the thread's Discussion, or comment on it. Returns the URL."""
    if find_thread(discussions, alert["id"]):
        raise SystemExit("%s is already on the board" % alert["id"])
    parent = alert.get("in_reply_to")
    if parent and not new_thread:
        thread = find_thread(discussions, parent)
        if thread is None:
            raise SystemExit(
                "%s replies to %s, which was never announced. Announce that "
                "first, or pass --new-thread." % (alert["id"], parent))
        return graphql("""
          mutation($id: ID!, $body: String!) {
            addDiscussionComment(input: {discussionId: $id, body: $body}) {
              comment { url } }
          }""", {"id": thread["id"], "body": render(alert)}
        )["addDiscussionComment"]["comment"]["url"]
    repo, category = board_ids(board)
    return graphql("""
      mutation($repo: ID!, $cat: ID!, $title: String!, $body: String!) {
        createDiscussion(input: {repositoryId: $repo, categoryId: $cat,
                                 title: $title, body: $body}) {
          discussion { url } }
      }""", {"repo": repo, "cat": category, "title": title(alert),
             "body": render(alert)})["createDiscussion"]["discussion"]["url"]
