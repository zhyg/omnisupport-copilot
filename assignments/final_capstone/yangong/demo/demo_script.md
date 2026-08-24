# Demo Script

1. 打开 <http://localhost:8010>，用 `agent@northstar.demo` 登录并选择 Workspace 工单。
2. 输入“Workspace 4.2 的 Webhook 返回 HTTP 401 和 WS-WEBHOOK-401，应该如何排查？”，点击“生成方案卡”。展示冻结的九字段契约、最多三步、真实 evidence、confidence、release 和 trace。
3. 在 Phoenix 搜索 `92d5a759c5a6e1d6d952b6c0deb84a51`，依次展示 Product、RAG、Hybrid Retrieval、generation 和 audit span；指出 Trace 只有 query hash/length，没有原文和密钥。
4. 输入“Webhook 不工作了，怎么修？”，展示 `needs_clarification=true` 和 `missing_required_context`。
5. 输入包含 `WS-QUANTUM-999` 的 C4，展示 citation 空、confidence 0、`no_retrieval_results`。
6. 输入 C5，点击 `add_internal_note` 建议；确认后展示 completed，再用相同 idempotency key 重放并说明无重复副作用。
7. 输入 C6，展示 `grant_service_credit/hitl`；坐席提交后为 awaiting_approval，管理员批准后 resume/completed。
8. 展示 `solution-card-eval-candidate.json` 的 8/8、p50/p95；说明首轮 C4 失败和 protected-identifier coverage 修复。
9. 展示 model-fault E2E：关闭模型端点后仍 pass、generation_mode 为 fallback。
10. 展示 Release audit：候选 generation 4，原子回滚 generation 5；最后打开 post-rollback E2E pass 报告。
