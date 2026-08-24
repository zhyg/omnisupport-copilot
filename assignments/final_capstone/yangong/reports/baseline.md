# Baseline

```yaml
commit: 1473db6dfa785487e1a0f87bb97bdfec6719725c
as_of: 2026-08-23T00:00:00Z
release_id: capstone-v1.0.0
generation: deterministic_fallback
embedding: deterministic-hash-embedding-v1@1536
rerank: disabled
```

## Bootstrap 与幂等

首次运行：240/240 工单写入、12 个知识 source、117 个 chunk、117 个向量、0 错误；新增的 Workspace manifest 中共有 4 份文档。第二次运行：工单 `inserted=0, skipped=240, bronze_duplicates=240`；对象 `uploaded=0`；索引 `embedded=0, skipped=117`；当前工单仍为 240、当前 chunk 仍为 117。

解析和图构建状态是 `warn`，原因是合成 HTML 的课程质量提示和本地 Graph 构建警告，不影响 `week8_ready=true`、117 个 source chunk、37 个 entity、35 条 edge。dbt build 为 pass。

## 原始 E2E

`reports/capstone/e2e-baseline.json` 顶层 pass，run_id `316bf6f00687`。RAG 使用 deterministic fallback，5 条 evidence；方案卡字段集合严格匹配 schema。Phoenix 已核对：RAG trace `b3a3e6269e3735db9fa5153f92546bf4`，方案卡 trace `ae457e45a999dd047b81f0a999c14318`，HITL wait/resume trace 分别为 `fa2f6fd39d52f12ba3710bf2309e617b`、`ca642de6bbb0e8606d5ed68495fad7a8`。

同一 Golden Set 的 fallback 基线为 7/8（87.5%）：C2 的 top-evidence 摘要没有同时呈现 `event_id` 和 `payload_digest`，但来源命中正确。这是候选真实 LLM生成需要改善的基线，不把 deterministic fallback 描述为模型质量。
