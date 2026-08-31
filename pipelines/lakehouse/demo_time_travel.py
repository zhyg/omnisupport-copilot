"""Week04 time travel demonstration."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from pipelines.lakehouse.catalog import CORE_TABLES, load_lakehouse_catalog


def run_time_travel_demo(
    table_name: str,
    snapshot_id: int | None = None,
    compare_snapshot_id: int | None = None,
) -> dict:
    catalog = load_lakehouse_catalog()
    table = catalog.load_table(table_name)
    snapshots = list(table.metadata.snapshots)

    if snapshot_id is None and snapshots:
        snapshot_id = snapshots[0].snapshot_id

    current_snapshot = table.current_snapshot()
    current_snapshot_id = current_snapshot.snapshot_id if current_snapshot else None
    current_rows = _count_rows(table)
    historical_rows = None
    if snapshot_id is not None:
        historical_rows = _count_rows(table, snapshot_id=snapshot_id)

    compare_rows = None
    if compare_snapshot_id is not None:
        compare_rows = _count_rows(table, snapshot_id=compare_snapshot_id)

    delta = None
    if historical_rows is not None and compare_rows is not None:
        delta = compare_rows - historical_rows
    elif historical_rows is not None and current_rows is not None:
        delta = current_rows - historical_rows

    return {
        "report_version": "week04_time_travel_demo_v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "table": table_name,
        "snapshot_count": len(snapshots),
        "current_snapshot_id": current_snapshot_id,
        "current_row_count": current_rows,
        "selected_snapshot_id": snapshot_id,
        "selected_snapshot_row_count": historical_rows,
        "compare_snapshot_id": compare_snapshot_id,
        "compare_snapshot_row_count": compare_rows,
        "row_count_delta": delta,
        "status": "ok" if snapshots else "no_snapshots",
        "notes": [
            "Use this demo after at least one successful materialization.",
            "Compare before/after snapshots to verify that backfilled rows are restored in new snapshot while historical snapshot preserves old state.",
        ],
    }


def _count_rows(table, snapshot_id: int | None = None) -> int:
    scan = table.scan(snapshot_id=snapshot_id) if snapshot_id is not None else table.scan()
    return scan.to_arrow().num_rows


def _markdown(payload: dict) -> str:
    lines = [
        "# Week04 Time Travel Demo Report",
        "",
        f"- table: `{payload['table']}`",
        f"- snapshot_count: `{payload['snapshot_count']}`",
        f"- current_snapshot_id: `{payload['current_snapshot_id']}`",
        f"- current_row_count: `{payload['current_row_count']}`",
        f"- selected_snapshot_id (before/historical): `{payload['selected_snapshot_id']}`",
        f"- selected_snapshot_row_count: `{payload['selected_snapshot_row_count']}`",
    ]
    if payload.get("compare_snapshot_id"):
        lines.extend([
            f"- compare_snapshot_id (after/backfill): `{payload['compare_snapshot_id']}`",
            f"- compare_snapshot_row_count: `{payload['compare_snapshot_row_count']}`",
        ])
    if payload.get("row_count_delta") is not None:
        lines.append(f"- row_count_delta (rows restored): `{payload['row_count_delta']}`")
    lines.extend([
        f"- status: `{payload['status']}`",
        "",
        "## Notes",
        "",
        *[f"- {note}" for note in payload["notes"]],
        "",
    ])
    return "\n".join(lines)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".md":
        path.write_text(_markdown(payload), encoding="utf-8")
    else:
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Week04 Iceberg time travel demo")
    parser.add_argument("--table", default="silver.ticket_fact", choices=CORE_TABLES)
    parser.add_argument("--snapshot-id", type=int, default=None, help="historical snapshot ID (e.g. before backfill)")
    parser.add_argument("--compare-snapshot-id", type=int, default=None, help="newer snapshot ID to compare with")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    payload = run_time_travel_demo(args.table, args.snapshot_id, args.compare_snapshot_id)
    if args.out:
        _write(args.out, payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
    return 0 if payload["status"] in {"ok", "no_snapshots"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
