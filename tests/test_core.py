import json

import pytest

from oalp import OALPError, Repository, object_id
from oalp.cli import main


@pytest.fixture
def repo(tmp_path):
    return Repository.init(tmp_path)


def test_commit_chains_decisions(repo):
    first = repo.commit(agent="billing-agent", intent="Look up overdue invoices",
                        action={"tool": "query_invoices", "args": {"status": "overdue"}})
    second = repo.commit(agent="billing-agent", intent="Send a reminder",
                         reasoning="Invoice is 30 days overdue",
                         action={"tool": "send_email", "args": {"to": "client@example.com"}},
                         outcome={"status": "success"})
    history = list(repo.log())
    assert [d["id"] for d in history] == [second, first]
    assert history[0]["parent"] == first
    assert history[1]["parent"] is None


def test_ids_are_content_hashes(repo):
    oid = repo.commit(agent="a", intent="x", timestamp="2026-01-01T00:00:00.000Z")
    record = repo.read(oid)
    assert object_id(record) == oid == record["id"]


def test_verify_passes_on_clean_log(repo):
    for i in range(3):
        repo.commit(agent="a", intent=f"step {i}")
    assert repo.verify() == []


def test_verify_detects_tampering(repo):
    first = repo.commit(agent="a", intent="Approve refund of 50")
    repo.commit(agent="a", intent="Notify customer")
    path = repo._object_path(first)
    record = json.loads(path.read_text())
    record["intent"] = "Approve refund of 5000"  # rewrite history
    path.write_text(json.dumps(record))
    problems = [i.problem for i in repo.verify()]
    assert any("modified after commit" in p for p in problems)


def test_verify_detects_missing_parent(repo):
    first = repo.commit(agent="a", intent="one")
    repo.commit(agent="a", intent="two")
    repo._object_path(first).unlink()  # delete history
    assert any("missing object" in i.problem for i in repo.verify())


def test_branches_isolate_runs(repo):
    base = repo.commit(agent="a", intent="plan")
    repo.create_branch("retry", base)
    repo.commit(agent="a", intent="try approach A")
    repo.commit(agent="a", intent="try approach B", branch="retry")
    assert [d["intent"] for d in repo.log("main")] == ["try approach A", "plan"]
    assert [d["intent"] for d in repo.log("retry")] == ["try approach B", "plan"]


def test_blobs_and_blob_tampering(repo):
    blob = repo.put_blob("Customer contract text ...")
    repo.commit(agent="a", intent="Check contract terms", context=[{"blob": blob, "label": "contract"}])
    assert repo.verify() == []
    path = repo._object_path(blob)
    obj = json.loads(path.read_text())
    obj["content"] = "different text"
    path.write_text(json.dumps(obj))
    assert any("blob" in i.problem for i in repo.verify())


def test_diff_and_prefix_resolution(repo):
    a = repo.commit(agent="a", intent="send", action={"tool": "email"})
    b = repo.commit(agent="a", intent="send", action={"tool": "sms"})
    assert repo.resolve(a[:8]) == a
    assert repo.diff(a, b) == {"action": ({"tool": "email"}, {"tool": "sms"})}


def test_errors(tmp_path, repo):
    with pytest.raises(OALPError):
        Repository(tmp_path / "nowhere").commit(agent="a", intent="x")
    with pytest.raises(OALPError):
        repo.commit(agent="a", intent="")
    with pytest.raises(OALPError):
        repo.resolve("deadbeef")


def test_cli_end_to_end(tmp_path, capsys):
    root = str(tmp_path)
    assert main(["-C", root, "init"]) == 0
    assert main(["-C", root, "commit", "--agent", "ops-bot", "-m", "Restart service",
                 "--action", '{"tool": "restart", "args": {"svc": "api"}}']) == 0
    assert main(["-C", root, "log", "--oneline"]) == 0
    assert main(["-C", root, "verify"]) == 0
    out = capsys.readouterr().out
    assert "Restart service" in out and "OK" in out
