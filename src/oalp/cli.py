"""`oalp` command line: git-style commands for AI agent decision logs."""

from __future__ import annotations

import argparse
import json
import sys

from .core import OALPError, Repository


def _json_arg(value: str | None):
    if value is None:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError as e:
        raise OALPError(f"invalid JSON: {value!r} ({e.msg})")


def _print_decision(d: dict, full: bool = False) -> None:
    print(f"decision {d['id']}")
    agent = d.get("agent", {})
    print(f"Agent:   {agent.get('id')}" + (f" ({agent['model']})" if agent.get("model") else ""))
    print(f"Branch:  {d.get('branch')}")
    print(f"Date:    {d.get('timestamp')}")
    print(f"\n    {d.get('intent')}")
    if d.get("action"):
        print(f"    -> action: {json.dumps(d['action'], ensure_ascii=False)}")
    if d.get("outcome"):
        print(f"    -> outcome: {json.dumps(d['outcome'], ensure_ascii=False)}")
    if full:
        for key in ("reasoning", "alternatives", "context", "metadata"):
            if d.get(key) is not None:
                print(f"    {key}: {json.dumps(d[key], ensure_ascii=False, indent=2)}")
    print()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="oalp", description="Git for AI agent decisions.")
    p.add_argument("-C", dest="root", default=".", help="run as if started in this directory")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create an empty decision repository")

    c = sub.add_parser("commit", help="record an agent decision")
    c.add_argument("--agent", required=True, help="agent id")
    c.add_argument("--model", help="model the agent ran on")
    c.add_argument("-m", "--intent", required=True, help="what the agent was trying to do")
    c.add_argument("--reasoning")
    c.add_argument("--action", help='JSON, e.g. \'{"tool": "send_email", "args": {...}}\'')
    c.add_argument("--outcome", help='JSON, e.g. \'{"status": "success"}\'')
    c.add_argument("--context", help="JSON list of inputs the agent relied on")
    c.add_argument("--alternatives", help="JSON list of options considered")
    c.add_argument("--branch")

    lg = sub.add_parser("log", help="show decision history")
    lg.add_argument("ref", nargs="?")
    lg.add_argument("-n", type=int, dest="limit")
    lg.add_argument("--oneline", action="store_true")

    s = sub.add_parser("show", help="show one decision in full")
    s.add_argument("ref", nargs="?", default="HEAD")

    b = sub.add_parser("branch", help="list or create branches")
    b.add_argument("name", nargs="?")
    b.add_argument("start", nargs="?")

    co = sub.add_parser("checkout", help="switch branch")
    co.add_argument("name")

    d = sub.add_parser("diff", help="compare two decisions")
    d.add_argument("a")
    d.add_argument("b")

    v = sub.add_parser("verify", help="check the log has not been tampered with")
    v.add_argument("ref", nargs="?")

    blob = sub.add_parser("blob", help="store a large context item (reads stdin)")
    blob.add_argument("--media-type", default="text/plain")

    args = p.parse_args(argv)
    repo = Repository(args.root)

    try:
        if args.cmd == "init":
            Repository.init(args.root)
            print(f"Initialized empty OALP repository in {repo.dir.resolve()}")
        elif args.cmd == "commit":
            agent = {"id": args.agent, **({"model": args.model} if args.model else {})}
            oid = repo.commit(agent=agent, intent=args.intent, reasoning=args.reasoning,
                              action=_json_arg(args.action), outcome=_json_arg(args.outcome),
                              context=_json_arg(args.context), alternatives=_json_arg(args.alternatives),
                              branch=args.branch)
            print(f"[{args.branch or repo.current_branch()} {oid[:12]}] {args.intent}")
        elif args.cmd == "log":
            for dec in repo.log(args.ref, args.limit):
                if args.oneline:
                    tool = (dec.get("action") or {}).get("tool", "")
                    print(f"{dec['id'][:12]} {dec['intent']}" + (f"  [{tool}]" if tool else ""))
                else:
                    _print_decision(dec)
        elif args.cmd == "show":
            _print_decision(repo.read(args.ref), full=True)
        elif args.cmd == "branch":
            if args.name:
                repo.create_branch(args.name, args.start)
                print(f"Created branch {args.name}")
            else:
                current = repo.current_branch()
                for name, oid in repo.branches().items():
                    print(f"{'*' if name == current else ' '} {name}  {oid[:12]}")
        elif args.cmd == "checkout":
            repo.checkout(args.name)
            print(f"Switched to branch '{args.name}'")
        elif args.cmd == "diff":
            for key, (a, b) in repo.diff(args.a, args.b).items():
                print(f"--- {key}\n-  {json.dumps(a, ensure_ascii=False)}\n+  {json.dumps(b, ensure_ascii=False)}")
        elif args.cmd == "verify":
            issues = repo.verify(args.ref)
            if issues:
                for issue in issues:
                    print(f"FAIL {issue}")
                return 1
            print("OK: every decision hash and parent link checks out")
        elif args.cmd == "blob":
            print(repo.put_blob(sys.stdin.read(), args.media_type))
    except OALPError as e:
        print(f"oalp: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
