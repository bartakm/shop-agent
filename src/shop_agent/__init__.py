import argparse
import asyncio
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Draft replies to customer emails using the Zrnko ERP over MCP.")
    parser.add_argument("inbox", nargs="?", default="inbox", type=Path, help="folder with *.json emails")
    parser.add_argument("--out", default="outbox", type=Path, help="folder for drafts")
    args = parser.parse_args()

    from .agent import run_inbox

    results = asyncio.run(run_inbox(args.inbox, args.out))
    waiting = sum(r.needs_human for r in results)
    print(f"\n{len(results)} emails, {len(results) - waiting} drafts ready, {waiting} need a human. Drafts in {args.out}/")
