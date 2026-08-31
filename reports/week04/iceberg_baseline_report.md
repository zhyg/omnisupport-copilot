# Week04 Iceberg Baseline Report

generated_at: `2026-08-31T14:31:20.383260+00:00`

| table | rows | snapshots | files | avg file size | min file size | max file size | latest snapshot id | latest operation |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| bronze.raw_ticket_event | 960 | 1 | 1 | 117448.0 | 117448 | 117448 | 4614495867466921954 | append |
| bronze.raw_doc_asset | 12 | 1 | 1 | 6946.0 | 6946 | 6946 | 1352648339820946946 | append |
| silver.ticket_fact | 480 | 3 | 1 | 26447.0 | 26447 | 26447 | 5790149629725186960 | append |
| silver.knowledge_doc | 24 | 1 | 1 | 9129.0 | 9129 | 9129 | 2041085980789350956 | append |

## Known Limits

- Week04 records current table health and metadata shape; it does not run compaction.
- Partition distribution is omitted for unpartitioned Student Core Pack tables.

## Next Steps

- Use this report as the before/after baseline for Week05 transform and Week06 orchestration.
- Only introduce maintenance jobs after table growth justifies them.
