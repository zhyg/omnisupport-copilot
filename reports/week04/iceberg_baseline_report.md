# Week04 Iceberg Baseline Report

generated_at: `2026-08-31T15:27:31.893654+00:00`

| table | rows | snapshots | files | avg file size | min file size | max file size | latest snapshot id | latest operation |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| bronze.raw_ticket_event | 962 | 5 | 1 | 117456.0 | 117456 | 117456 | 284706752567799321 | append |
| bronze.raw_doc_asset | 12 | 5 | 1 | 6946.0 | 6946 | 6946 | 4280529332619572987 | append |
| silver.ticket_fact | 482 | 7 | 1 | 26664.0 | 26664 | 26664 | 3102956398352179151 | append |
| silver.knowledge_doc | 24 | 5 | 1 | 9129.0 | 9129 | 9129 | 8326298521780115142 | append |

## Known Limits

- Week04 records current table health and metadata shape; it does not run compaction.
- Partition distribution is omitted for unpartitioned Student Core Pack tables.

## Next Steps

- Use this report as the before/after baseline for Week05 transform and Week06 orchestration.
- Only introduce maintenance jobs after table growth justifies them.
