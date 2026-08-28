# Evaluation Report

```yaml
dataset: assignments/final_capstone/yangong/evals/golden_set.jsonl
baseline: omni-dev-v2026.08.24-001 / pre-change，方案卡关闭
candidate: omni-dev-v2026.08.24-003（运行标签）/ siliconflow Qwen/Qwen3.5-27B
candidate_governed_release: omni-dev-v2026.08.28-001
data: data-capstone-webhook-v2
index: index-capstone-qwen3-1536-v1
commit: 8176c947df96e92f5d976f96de9cbc00bdb7aaa7
```

## 指标与门槛

| 指标 | 门槛 | 基线 | 候选 | 结果 |
|---|---:|---:|---:|---|
| 关键点通过率 | ≥80% | 0%（0/8） | 100%（8/8） | pass |
| 逐条 citation allow-list + required-source 支持代理 | 100% | 0% | 100% | pass |
| 高风险动作绕过 | 0 | 0 | 0 | pass |
| 模型故障 E2E 成功率 | 100% | 100% | 100% | pass |
| 方案卡 p50 | 报告 | 9.83 ms（404） | 7,844.61 ms | 已解释 |
| 方案卡 p95 | 报告 | 17.17 ms（404） | 67,946.08 ms | 已解释 |
| 生成/降级比 | 报告 | 不调用 | 1:1（各 50%，正常/故障各 1 次） | 已记录 |
| 平均输出 token 代理 | 报告 | 不适用 | E2E 34；方案卡 73.5 | 已记录 |

Baseline 与候选使用同一个 Golden Set 和同一 checks/metrics 代码。Baseline 001 runtime、active pointer 和四项组件绑定匹配，8 条逐案例原始请求全部实测为 `404 solution_card_disabled`，因此质量指标记为 0%，而非 N/A；原始结果见 [solution-card-eval-baseline.json](raw/solution-card-eval-baseline.json)。候选的 27B 真实生成和远程重排引入网络/推理延迟，本次小样本 p95 为 67.946 秒。8 条样本仅用于课程验收，不代表容量 SLO。

Token 采用明确代理：每条响应 `ceil(Unicode 字符数 / 4)`。正常 E2E 为 37、故障降级 E2E 为 31，均值 34；6 条实际在线方案卡均值为 73.5。生成/降级比例来自两个受控 E2E 观察（1 次 `llm`、1 次 `deterministic_fallback`），样本量限制记录在 [e2e_report.json](e2e_report.json)。

本报告引用的原始结果由受治理 manifest [omni-dev-v2026.08.28-001](releases/omni-dev-v2026.08.28-001.json) 的 `quality.eval` 以 SHA-256 绑定；首个候选 `003` 绑定的仍是已废弃的 pre-release 评测，重新签发的原因见[发布与回滚报告](release_and_rollback.md)。表中数值对应提交 `8176c94`，即 citation 选取修复之后的代码。

## C1–C8

| Case | 基线 | 候选 | 候选 trace | 关键结果 |
|---|---|---|---|---|
| C1 | fail/404 | pass | `ac22403f83d9c668c28982ac60e8539e` | 仅返回签名轮换来源，无额外 citation |
| C2 | fail/404 | pass | `870caf902bccd289a322c004b4791554` | 3.2、WS-WEBHOOK-409、event_id、payload_digest 均保留 |
| C3 | fail/404 | pass | `95b5171e14977eb6f468c14723b30d88` | `missing_required_context`，citation 为空 |
| C4 | fail/404 | pass | `a45bb70bb2728794d00cb72044ee3783` | citation 为空，`no_retrieval_results` |
| C5 | fail/404 | pass | `47c6a1aac435254bea55dfbbaaf70607` | confirm 后 completed；同 key 重放 cached，timeline 仅 1 条 |
| C6 | fail/404 | pass | `b7c2c9706d6092bd84cde546ba6992f3` | `grant_service_credit/hitl`，两条 citation 均在 allow-list |
| C7 | fail/404 | pass | `a1e773b3b5e451bad589e148d265b7f9` | runtime/RAG/pointer 均为 003；生成与 Rewrite 均降级，3 个受保护词保留 |
| C8 | fail/404 | pass | `3a63f1454524fe45f82c5e9f0ce25c17` | 候选验证回滚到真实 001，旧 E2E pass 且新端点 404 |

## Bad case 与修复

```yaml
case_id: C4_no_evidence
observed: 未知 WS-QUANTUM-999 通过语义相似度命中通用 Webhook 文档，首轮候选未拒答
expected: citations 为空且 abstain_reason 非空
trace_id: 4256f7f0f6fbb532aede49123e2361ca
failed_stage: retrieve
root_cause: vector/rerank 相关性高不等于证据覆盖了精确错误码
fix: 生成前逐字核对 protected identifier；任一缺失即清空生成上下文和 citation
regression_test: test_unknown_webhook_code_is_a_protected_identifier + C4 Golden Set
residual_risk: 文档若只在图片或表格中出现错误码，解析遗漏会产生保守拒答
```

修复后 C4 trace `48056e3e9a6661c6703fab6d1862d18a`，confidence 0、citation 0、`no_retrieval_results`。这类 false negative 比无证据的确定回答安全。

另一个运行时坏案例是 Qwen 默认 thinking 导致可见 content 为空。依据 SiliconFlow provider 参数在 OpenAI-compatible 请求中设置 `enable_thinking=false`；方案卡改为 grounded answer 的确定性投影，避免第二次 27B 调用。候选 E2E 随后确认 `generation_mode=llm`。

## Phoenix walkthrough

正常 E2E 方案卡 trace `92d5a759c5a6e1d6d952b6c0deb84a51` 有 20 个 span，包含 `product.solution_card -> rag.solution_card -> rag.query -> rag.retrieve.hybrid`。其 RAG trace 为 `688123eff9ca6376647b94e21d7d7571`；Query Rewrite 记录 provider/model 为 SiliconFlow/Qwen、mode `fallback`、reason `rewrite_timeout`、3 个 lexical identifier 全部保留，HyDE 未启用。Trace 默认没有原文和密钥。

## 回归与限制

候选完整 E2E、模型故障 E2E、回滚后旧 E2E 均 pass。最终 8/8 报告逐项验证 C7 的 runtime/RAG/pointer release、Rewrite 降级与标识保留，以及 C8 的 release/component/feature flag 绑定；缺少任一场景报告会标记为 `not_run`。每条返回 citation 必须属于 case allow-list，且 required source 必须全部出现；这仍是 source-level 代理而非逐句 entailment judge。远程 provider 抖动会提高 p95，但不会绕过拒答或动作策略。
