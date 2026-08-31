# Week04 Time Travel Demo Report

- table: `silver.ticket_fact`
- snapshot_count: `7`
- current_snapshot_id: `3102956398352179151`
- current_row_count: `482`
- selected_snapshot_id (before/historical): `7096804225126005740`
- selected_snapshot_row_count: `480`
- compare_snapshot_id (after/backfill): `3102956398352179151`
- compare_snapshot_row_count: `482`
- row_count_delta (rows restored): `2`
- status: `ok`

## Notes

- Use this demo after at least one successful materialization.
- Compare before/after snapshots to verify that backfilled rows are restored in new snapshot while historical snapshot preserves old state.
