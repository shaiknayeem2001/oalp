# OALP Specification, v0.1 (draft)

**Open Agent Logging Protocol: git for AI agent decisions.**

Status: working draft for public comment. Anything here may change before v1.0. The key words MUST, SHOULD and MAY are used as described in RFC 2119.

## 1. Purpose

OALP defines a vendor-neutral format for recording the decisions an AI agent makes, so that the record:

1. captures *why* an action was taken, not only *that* it was taken;
2. is **tamper-evident**: any later edit, insertion or deletion can be detected;
3. can be **verified by a third party** using only the records themselves;
4. can be written and queried by any agent through MCP.

The design deliberately borrows git's object model, because git already solves "an append-only history whose integrity anyone can check".

## 2. Objects

All objects are JSON. Every object has:

| field | type | required | meaning |
|---|---|---|---|
| `type` | string | yes | `"decision"` or `"blob"` |
| `oalp_version` | string | yes | `"0.1"` for this draft |
| `id` | string | yes | the object's content hash (§3) |

### 2.1 Decision record (≈ git commit)

| field | type | required | meaning |
|---|---|---|---|
| `parent` | string \| null | yes | `id` of the previous decision on this branch; `null` for the first |
| `branch` | string | yes | the branch the decision was committed to |
| `timestamp` | string | yes | RFC 3339 UTC time, millisecond precision |
| `agent` | object | yes | `{"id": ..., "model"?: ..., "version"?: ...}` |
| `intent` | string | yes | what the agent was trying to achieve |
| `context` | array | no | inputs the decision relied on: inline values or blob references `{"blob": <id>, "label"?: ...}` |
| `reasoning` | string | no | the agent's stated rationale |
| `alternatives` | array | no | options considered and why they were rejected |
| `action` | object | no | what the agent did, e.g. `{"tool": "send_email", "args": {...}}` |
| `outcome` | object | no | result, e.g. `{"status": "success" \| "error" \| "pending", "result"?: ...}` |
| `metadata` | object | no | implementation-specific extras (trace ids, cost, latency) |

`reasoning` is the agent's *stated* rationale. OALP records what the agent reported; it does not claim this is a faithful account of the model's internal computation.

### 2.2 Blob (≈ git blob)

| field | type | required | meaning |
|---|---|---|---|
| `media_type` | string | yes | e.g. `text/plain`, `application/json` |
| `content` | string | yes | the content (binary data base64-encoded) |

Blobs let large inputs (documents, tool output, retrieved passages) be stored once and referenced by hash from many decisions.

## 3. Hashing

- The **canonical form** of an object is its JSON encoding with keys sorted, no insignificant whitespace, and UTF-8 output without ASCII escaping. (v0.1 uses this simple rule; v1.0 is expected to adopt RFC 8785 JSON Canonicalization Scheme.)
- An object's `id` is the lowercase hex **SHA-256** of the canonical form of the object **with the `id` field removed**.
- Because a decision includes its `parent` id, its hash covers the whole history before it. Changing any earlier decision changes its id and breaks every later `parent` link.

## 4. Repository layout (reference storage)

Implementations MAY use any storage, but MUST be able to export to this layout:

```
.oalp/
  HEAD                  "ref: refs/heads/<branch>"
  refs/heads/<branch>   id of the branch's latest decision
  objects/<id[0:2]>/<id[2:]>.json
```

Objects are immutable: an implementation MUST NOT overwrite an existing object file.

## 5. Branches

A branch is a named pointer to its latest decision. Typical use: one branch per agent run, task or session, or a branch to retry from an earlier decision without losing the original path. Committing a decision MUST set its `parent` to the branch's current head and then move the head to the new id.

## 6. Verification

A verifier, starting from one or more branch heads, MUST:

1. load each object and check that it hashes to its own `id` and file name;
2. follow `parent` links to the root, reporting any missing object;
3. for each blob reference in `context`, check that the blob exists and hashes to its id.

A log passes only if no issues are found.

**Trust boundary.** A hash chain proves a history is *internally consistent*. On its own it does not stop someone with write access from rewriting the entire chain and recomputing every hash. To close that gap, v0.2 will add:

- **signed decisions** (Ed25519 signature by the agent's or host's key over the `id`), and
- **anchoring**: periodically publishing branch-head ids to an external party (an auditor, a transparency log, another system), so later rewrites are detectable against the anchored head.

## 7. MCP interface

An OALP MCP server exposes these tools:

| tool | arguments | returns |
|---|---|---|
| `oalp_commit` | `agent_id, intent, reasoning?, action?, outcome?, context?, alternatives?, branch?` | new decision id |
| `oalp_log` | `ref?, limit?` | decisions, newest first |
| `oalp_show` | `ref` | one decision |
| `oalp_branch` | `name, start?` | id the branch starts at |
| `oalp_verify` | `ref?` | `{"ok": bool, "issues": [...]}` |

`ref` may be a full id, a unique id prefix of at least 4 characters, a branch name, or `HEAD`.

## 8. Example

```json
{
  "type": "decision",
  "oalp_version": "0.1",
  "id": "9c1e…",
  "parent": "41ab…",
  "branch": "invoice-run-2026-11-25",
  "timestamp": "2026-11-25T17:52:03.120Z",
  "agent": {"id": "billing-agent", "model": "claude-opus"},
  "intent": "Send payment reminder for invoice INV-1042",
  "context": [{"blob": "e3f0…", "label": "invoice INV-1042"}],
  "reasoning": "Invoice is 30 days overdue and no reminder has been sent",
  "alternatives": [{"option": "escalate to account manager", "rejected_because": "under escalation threshold"}],
  "action": {"tool": "send_email", "args": {"to": "accounts@client.example", "template": "reminder-1"}},
  "outcome": {"status": "success"}
}
```

## 9. Open questions

Feedback welcome via issues:

- Should `reasoning` be structured (steps, cited evidence) rather than free text?
- How should multi-agent handoffs be modelled: merge decisions with two parents, or cross-branch references?
- How should redaction work so personal data can be removed while the log stays verifiable (e.g. hashing blob content separately from its envelope)?
- Which standards should a v1.0 format map to (OpenTelemetry GenAI conventions, W3C PROV)?
