# OALP: Open Agent Logging Protocol

**An open standard for immutable, auditable records of AI agent decisions, built on the Model Context Protocol (MCP).**

> **Status: early draft (v0.1, work in progress).** The spec and reference implementation are being developed in the open. Feedback, issues and design discussion are very welcome.

## Why OALP?

AI agents are moving from demos into regulated, high-stakes work: finance, compliance, trading, government services. As they act more on their own, a basic question gets harder to answer: **what did the agent decide, why, and based on what?**

Today every team builds its own agent logging. The formats don't match, the logs can be edited after the fact, and auditors have nothing standard to verify against. Observability tools trace *calls*; they don't capture *decisions* in a form that holds up to an audit.

OALP aims to close that gap with a small, vendor-neutral standard that any MCP-based agent can adopt.

## Goals

- **Decision-level records:** capture each agent decision with its inputs, the context and tools it used, the alternatives it considered, the action it took and its outcome.
- **Tamper-evident by design:** an append-only log with hash-chained entries, so any edit or deletion is detectable.
- **MCP-native:** exposed as an MCP server, so agents and hosts can emit and query decision logs without custom glue code.
- **Vendor- and model-neutral:** works with any model, agent framework or MCP host.
- **Verifiable by third parties:** auditors can check the integrity of a log without trusting the system that produced it.
- **Privacy-aware:** support for redaction and references to sensitive data, so logs stay auditable without leaking it.

## Planned components

| Component | Description | Status |
|---|---|---|
| Specification | Record schema, hash-chaining rules, MCP interface | Drafting |
| Reference MCP server | Emits, stores and serves OALP logs | In progress |
| SDKs | Python and TypeScript first | Planned |
| Verifier CLI | Checks log integrity and schema conformance | Planned |
| Conformance tests | Test suite for compatible implementations | Planned |
| Integrations | Examples with popular agent frameworks and MCP hosts | Planned |

## Roadmap

1. Publish the v0.1 draft spec for public comment
2. Ship the reference MCP server and the verifier CLI
3. Release Python and TypeScript SDKs
4. Add the conformance test suite
5. Build example integrations and gather feedback from real deployments
6. Stabilise the spec at v1.0

## Contributing

OALP is at an early stage, so this is the best time to shape it. Open an issue to discuss the design, propose schema fields or share your use case, especially if you run agents in a regulated environment.

## License

[Apache License 2.0](LICENSE)

## Maintainer

Created and maintained by [Shaik Nayeem Ahmed](https://github.com/shaiknayeem2001).
