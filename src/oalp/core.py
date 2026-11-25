"""OALP core: a content-addressed, hash-chained store of AI agent decisions.

Think of it as git for agent decisions:

    git commit   ->  decision record (what the agent decided, why, and what it did)
    git blob     ->  context blob (large inputs: documents, tool output, prompts)
    git branch   ->  a line of decisions (one agent run, session or task)
    git log      ->  the decision history of a branch
    git fsck     ->  verify: recompute every hash and check every parent link
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

OALP_VERSION = "0.1"
OALP_DIR = ".oalp"
DEFAULT_BRANCH = "main"

DECISION_FIELDS = (
    "intent",        # what the agent was trying to achieve
    "context",       # inputs it relied on (inline or blob references)
    "reasoning",     # the agent's stated rationale
    "alternatives",  # options it considered and rejected
    "action",        # what it did: {"tool": ..., "args": ...}
    "outcome",       # what happened: {"status": ..., "result": ...}
)


class OALPError(Exception):
    pass


def canonical_json(obj: Any) -> bytes:
    """Deterministic JSON encoding used for hashing (sorted keys, no whitespace, UTF-8)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def object_id(obj: dict) -> str:
    """Content address of an object: SHA-256 over its canonical JSON, without its own id."""
    body = {k: v for k, v in obj.items() if k != "id"}
    return hashlib.sha256(canonical_json(body)).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass
class VerifyIssue:
    object_id: str
    problem: str

    def __str__(self) -> str:
        return f"{self.object_id[:12]}: {self.problem}"


class Repository:
    """A decision repository on disk, laid out like a tiny git repo:

    .oalp/
      HEAD                  "ref: refs/heads/main"
      refs/heads/<branch>   id of the branch's latest decision
      objects/ab/cdef...    one JSON file per object, named by its hash
    """

    def __init__(self, root: str | os.PathLike = "."):
        self.root = Path(root)
        self.dir = self.root / OALP_DIR

    # ----- setup -------------------------------------------------------------

    @classmethod
    def init(cls, root: str | os.PathLike = ".") -> "Repository":
        repo = cls(root)
        if repo.dir.exists():
            raise OALPError(f"already an OALP repository: {repo.dir}")
        (repo.dir / "objects").mkdir(parents=True)
        (repo.dir / "refs" / "heads").mkdir(parents=True)
        (repo.dir / "HEAD").write_text(f"ref: refs/heads/{DEFAULT_BRANCH}\n")
        return repo

    def _require(self) -> None:
        if not self.dir.exists():
            raise OALPError(f"not an OALP repository (no {OALP_DIR}/ in {self.root}); run `oalp init`")

    # ----- objects -----------------------------------------------------------

    def _object_path(self, oid: str) -> Path:
        return self.dir / "objects" / oid[:2] / f"{oid[2:]}.json"

    def _write_object(self, obj: dict) -> str:
        oid = object_id(obj)
        obj = {**obj, "id": oid}
        path = self._object_path(oid)
        if not path.exists():  # objects are immutable: never overwrite
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(canonical_json(obj))
            tmp.replace(path)
        return oid

    def read(self, oid: str) -> dict:
        self._require()
        oid = self.resolve(oid)
        return json.loads(self._object_path(oid).read_text("utf-8"))

    def resolve(self, ref: str) -> str:
        """Accept a full id, a unique id prefix (min 4 chars), a branch name or HEAD."""
        if ref == "HEAD":
            head = self.head_id()
            if head is None:
                raise OALPError("HEAD has no decisions yet")
            return head
        branch_file = self.dir / "refs" / "heads" / ref
        if branch_file.is_file():
            return branch_file.read_text().strip()
        if len(ref) == 64 and self._object_path(ref).exists():
            return ref
        if len(ref) >= 4:
            folder = self.dir / "objects" / ref[:2]
            matches = [ref[:2] + p.stem for p in folder.glob(f"{ref[2:]}*.json")] if folder.exists() else []
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                raise OALPError(f"ambiguous id prefix: {ref}")
        raise OALPError(f"unknown decision or branch: {ref}")

    def put_blob(self, content: str, media_type: str = "text/plain") -> str:
        """Store a large context item once and reference it from decisions by id."""
        self._require()
        return self._write_object({"type": "blob", "oalp_version": OALP_VERSION,
                                   "media_type": media_type, "content": content})

    # ----- branches ----------------------------------------------------------

    def current_branch(self) -> str:
        head = (self.dir / "HEAD").read_text().strip()
        if not head.startswith("ref: refs/heads/"):
            raise OALPError("detached HEAD is not supported in v0.1")
        return head.removeprefix("ref: refs/heads/")

    def head_id(self, branch: str | None = None) -> str | None:
        branch = branch or self.current_branch()
        f = self.dir / "refs" / "heads" / branch
        return f.read_text().strip() if f.exists() else None

    def branches(self) -> dict[str, str]:
        heads = self.dir / "refs" / "heads"
        return {p.name: p.read_text().strip() for p in sorted(heads.iterdir()) if p.is_file()}

    def create_branch(self, name: str, start: str | None = None) -> str:
        self._require()
        if "/" in name or name in ("HEAD", "") or name.startswith("."):
            raise OALPError(f"invalid branch name: {name!r}")
        f = self.dir / "refs" / "heads" / name
        if f.exists():
            raise OALPError(f"branch already exists: {name}")
        start_id = self.resolve(start) if start else self.head_id()
        if start_id is None:
            raise OALPError("nothing to branch from: commit a decision first")
        f.write_text(start_id + "\n")
        return start_id

    def checkout(self, name: str) -> None:
        self._require()
        if name != DEFAULT_BRANCH and not (self.dir / "refs" / "heads" / name).exists():
            raise OALPError(f"unknown branch: {name}")
        (self.dir / "HEAD").write_text(f"ref: refs/heads/{name}\n")

    # ----- decisions ---------------------------------------------------------

    def commit(self, *, agent: dict | str, intent: str, action: dict | None = None,
               reasoning: str | None = None, context: list | None = None,
               alternatives: list | None = None, outcome: dict | None = None,
               metadata: dict | None = None, branch: str | None = None,
               timestamp: str | None = None) -> str:
        """Record one agent decision on a branch and advance the branch to it."""
        self._require()
        if not intent:
            raise OALPError("a decision needs an intent")
        branch = branch or self.current_branch()
        record: dict[str, Any] = {
            "type": "decision",
            "oalp_version": OALP_VERSION,
            "parent": self.head_id(branch),
            "branch": branch,
            "timestamp": timestamp or _now(),
            "agent": {"id": agent} if isinstance(agent, str) else agent,
            "intent": intent,
        }
        for key, value in (("context", context), ("reasoning", reasoning),
                           ("alternatives", alternatives), ("action", action),
                           ("outcome", outcome), ("metadata", metadata)):
            if value is not None:
                record[key] = value
        oid = self._write_object(record)
        (self.dir / "refs" / "heads" / branch).write_text(oid + "\n")
        return oid

    def log(self, ref: str | None = None, limit: int | None = None) -> Iterator[dict]:
        """Walk the parent chain from a branch tip (newest first), like `git log`."""
        self._require()
        oid = self.resolve(ref) if ref else self.head_id()
        count = 0
        while oid and (limit is None or count < limit):
            obj = self.read(oid)
            yield obj
            oid = obj.get("parent")
            count += 1

    def diff(self, a: str, b: str) -> dict[str, tuple[Any, Any]]:
        """Field-level differences between two decisions."""
        da, db = self.read(a), self.read(b)
        skip = {"id", "parent", "timestamp"}
        keys = sorted((set(da) | set(db)) - skip)
        return {k: (da.get(k), db.get(k)) for k in keys if da.get(k) != db.get(k)}

    def verify(self, ref: str | None = None) -> list[VerifyIssue]:
        """Check integrity like `git fsck`: every stored object must hash to its own
        name and id, every parent must exist, and every referenced blob must be intact.
        Any edit to a past decision breaks its hash and every link after it."""
        self._require()
        issues: list[VerifyIssue] = []
        tips = [self.resolve(ref)] if ref else list(self.branches().values())
        seen: set[str] = set()
        for oid in tips:
            while oid and oid not in seen:
                seen.add(oid)
                path = self._object_path(oid)
                if not path.exists():
                    issues.append(VerifyIssue(oid, "missing object (referenced but not stored)"))
                    break
                try:
                    obj = json.loads(path.read_text("utf-8"))
                except json.JSONDecodeError:
                    issues.append(VerifyIssue(oid, "object is not valid JSON"))
                    break
                if obj.get("id") != oid:
                    issues.append(VerifyIssue(oid, f"stored id {str(obj.get('id'))[:12]} does not match its name"))
                if object_id(obj) != oid:
                    issues.append(VerifyIssue(oid, "content hash mismatch: record was modified after commit"))
                for item in obj.get("context") or []:
                    if isinstance(item, dict) and "blob" in item:
                        bpath = self._object_path(item["blob"])
                        if not bpath.exists():
                            issues.append(VerifyIssue(oid, f"missing context blob {item['blob'][:12]}"))
                        elif object_id(json.loads(bpath.read_text("utf-8"))) != item["blob"]:
                            issues.append(VerifyIssue(oid, f"context blob {item['blob'][:12]} was modified"))
                oid = obj.get("parent")
        return issues
