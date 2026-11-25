# OALP: Open Agent Logging Protocol

**Git for AI agent decisions.** An open standard for immutable, auditable records of what AI agents decide, why they decide it, and what they do, built on the Model Context Protocol (MCP).

> **Status: early draft (v0.1).** The [spec](SPEC.md) and a working Python reference implementation are here. The design is open for feedback. Please open an issue.

## Why OALP?

Developers would never ship code without version control. Yet AI agents now make decisions that move money, file compliance returns and change production systems, and most of those decisions leave behind only scattered, editable logs.

When something goes wrong, the questions are the same ones git answers for code:

- **What changed, and in what order?** → `oalp log`
- **Why was this done, and based on what?** → `oalp show`
- **Has anyone rewritten the history?** → `oalp verify`
- **How did two runs differ?** → `oalp diff`, branches

Observability tools trace *calls*. OALP records *decisions*, in a form an auditor can check without trusting the system that produced it.

## The git model, applied to agents

| git | OALP |
|---|---|
| commit | **decision record**: intent, context, reasoning, alternatives, action, outcome |
| commit hash | SHA-256 of the record's canonical JSON |
| parent pointer | each decision links to the previous one, forming a tamper-evident chain |
| blob | **context blob**: large inputs (documents, tool output) stored once, referenced by hash |
| branch | a line of decisions: one agent run, task or session |
| `git log` / `show` / `diff` | `oalp log` / `show` / `diff` |
| `git fsck` | `oalp verify`: recompute every hash, check every link |

Change one word in a past decision and its hash no longer matches. Every later decision points to the old hash, so the edit shows up immediately.

## Quick start

```bash
pip install -e .            # from a clone of this repo
oalp init

oalp commit --agent billing-agent --model claude-opus \
  -m "Send payment reminder for invoice INV-1042" \
  --reasoning "Invoice is 30 days overdue and no reminder was sent yet" \
  --action '{"tool": "send_email", "args": {"to": "accounts@client.example"}}' \
  --outcome '{"status": "success"}'

oalp log --oneline
oalp show HEAD
oalp verify          # OK: every decision hash and parent link checks out
```

### From Python

```python
from oalp import Repository

repo = Repository.init(".")
contract = repo.put_blob(open("contract.txt").read())
repo.commit(
    agent={"id": "compliance-agent", "model": "claude-opus"},
    intent="Flag late-payment clause for review",
    context=[{"blob": contract, "label": "customer contract"}],
    reasoning="Clause 7.2 conflicts with the client's standard terms",
    alternatives=[{"option": "auto-approve", "rejected_because": "terms conflict"}],
    action={"tool": "create_review_task", "args": {"clause": "7.2"}},
    outcome={"status": "success"},
)
assert repo.verify() == []
```

### As an MCP server

```bash
pip install -e ".[mcp]"
OALP_ROOT=./agent-logs oalp-mcp
```

This exposes `oalp_commit`, `oalp_log`, `oalp_show`, `oalp_branch` and `oalp_verify` as MCP tools, so any MCP-capable agent or host can log and query decisions with no custom glue code.

## Roadmap

- [x] v0.1 draft spec: record format, hashing, storage layout
- [x] Reference implementation: Python library, CLI, MCP server, tests
- [ ] Signed decisions (Ed25519) and external anchoring of branch heads
- [ ] `push` / `pull` to share decision logs between systems and auditors
- [ ] TypeScript SDK
- [ ] Redaction that keeps logs verifiable
- [ ] Conformance test suite for other implementations
- [ ] Integrations with popular agent frameworks
- [ ] v1.0 stable spec

## Contributing

OALP is at an early stage, so this is the best time to shape it. Open an issue to discuss the design, propose fields or share your use case, especially if you run agents in a regulated environment.

```bash
pip install -e ".[dev]" && pytest
```

## License

[Apache License 2.0](LICENSE). Created and maintained by [Shaik Nayeem Ahmed](https://github.com/shaiknayeem2001).
