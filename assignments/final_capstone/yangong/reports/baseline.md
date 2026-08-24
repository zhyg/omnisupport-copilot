# 基线报告

```yaml
commit: 1473db6dfa785487e1a0f87bb97bdfec6719725c
logical_release_id: capstone-prechange-v1.0.0
governed_release_id: omni-dev-v2026.08.24-001
data_release_id: data-capstone-v1
index_release_id: index-capstone-v1
prompt_release_id: prompt-capstone-v1
graph_release_id: graph-capstone-prechange-v1
generation: deterministic_fallback
embedding: deterministic-hash-embedding-v1@1536
rerank: disabled
solution_card: disabled
```

## 真实的变更前数据链

基线由临时 Git worktree 中的提交 `1473db6` 执行 bootstrap，而不是用当前分支代码换一个 release 标签：

- 240 个基线工单；
- 10 个 active knowledge source；
- 91 个 source chunk 和 91 个确定性向量；
- 32 个 entity、28 条 edge、4 个 community；
- 不包含 `webhook-signature-rotation` 和 `webhook-retry-idempotency`；
- 不包含方案卡 prompt/service 能力，`solution_card=false`。

机器可读绑定见 [baseline_component_bindings.json](baseline_component_bindings.json)，受治理 manifest [001](releases/omni-dev-v2026.08.24-001.json) 对该文件、旧 Prompt、Skill 契约和原始 E2E 报告的 SHA-256 digest 保护。

## 旧功能 E2E

[e2e-baseline-legacy.json](raw/e2e-baseline-legacy.json) 顶层为 `pass`，run_id 为 `2674b3bd35bb`。原有 RAG 返回 5 条 evidence，KPI 查询有 98 行，低风险备注直接完成，财务动作进入 HITL 并在批准后恢复；Phoenix RAG trace 为 `3e9f3cd0461e7146bb5ff745468b633a`。

基线没有方案卡能力，因此不把当前实现运行在旧 release 标签上的结果伪装成 baseline 质量。E2E 明确验证方案卡端点返回 `404 solution_card_disabled`；候选质量提升从“能力未发布”到最终 Golden Set 8/8。
