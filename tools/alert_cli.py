"""Commands for managing production alert tables; no fake alert generation."""
from __future__ import annotations

import argparse
import json
from alert_service import DEFAULT_DB, init_db, list_alerts, get_summary, transition


def main():
    parser = argparse.ArgumentParser(description="Project II Alert Engine")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="SQLite path (defaults to data/water.db)")
    commands = parser.add_subparsers(dest="action", required=True)
    commands.add_parser("init", help="Create alerts tables (non-destructive)")
    commands.add_parser("status", help="Summarize alert states")
    lst = commands.add_parser("list", help="List current alerts")
    lst.add_argument("--state", choices=["all", "open", "acknowledged", "closed"], default="all")
    for action in ("acknowledge", "close"):
        cmd = commands.add_parser(action)
        cmd.add_argument("alert_id", type=int)
        cmd.add_argument("--actor", required=True)
        cmd.add_argument("--note", default="")
    args = parser.parse_args()
    if args.action == "init":
        init_db(args.db)
        print("OK: bang alerts, alert_observations, alert_actions da san sang; telemetry giu nguyen")
    elif args.action == "status":
        print(json.dumps(get_summary(args.db), indent=2, ensure_ascii=False))
    elif args.action == "list":
        for item in list_alerts(args.db, args.state):
            print(f"#{item['id']} | {item['state']} | {item['severity']} | {item['category']} | {item['zone']} | count={item['observations']}")
    else:
        try:
            print(json.dumps(transition(args.alert_id, args.action, args.actor, args.note, db=args.db), ensure_ascii=False))
        except ValueError as exc:
            parser.error(str(exc))


if __name__ == "__main__":
    main()
