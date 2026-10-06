"""A tiny todo list on the command line, stored in a JSON file."""

import argparse
import json
import sys
from pathlib import Path


def load(db: Path) -> list:
    return json.loads(db.read_text(encoding="utf-8")) if db.exists() else []


def save(db: Path, items: list) -> None:
    db.write_text(json.dumps(items, indent=2), encoding="utf-8")


def cmd_add(args) -> int:
    items = load(args.db)
    next_id = max((item["id"] for item in items), default=0) + 1
    items.append({"id": next_id, "title": args.title, "done": False})
    save(args.db, items)
    print(next_id)
    return 0


def cmd_done(args) -> int:
    items = load(args.db)
    for item in items:
        if item["id"] == args.id:
            item["done"] = True
            save(args.db, items)
            return 0
    print(f"no item {args.id}", file=sys.stderr)
    return 1


def cmd_list(args) -> int:
    for item in sorted(load(args.db), key=lambda i: i["id"]):
        mark = "x" if item["done"] else " "
        print(f"[{mark}] {item['id']}: {item['title']}")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="todo")
    parser.add_argument("--db", type=Path, default=Path("todo.json"))
    sub = parser.add_subparsers(dest="command", required=True)
    add = sub.add_parser("add")
    add.add_argument("title")
    add.set_defaults(func=cmd_add)
    done = sub.add_parser("done")
    done.add_argument("id", type=int)
    done.set_defaults(func=cmd_done)
    sub.add_parser("list").set_defaults(func=cmd_list)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
