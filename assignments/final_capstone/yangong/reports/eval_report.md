# Evaluation Report

```yaml
dataset: assignments/final_capstone/yangong/evals/golden_set.jsonl
baseline: omni-dev-v2026.08.24-001 / pre-change，方案卡关闭
candidate: omni-dev-v2026.08.24-003 / siliconflow Qwen/Qwen3.5-27B
data: data-capstone-webhook-v2
index: index-capstone-qwen3-1536-v1
commit: 6eed8cf202c3c90ca593dbb1260039060919a0fb
```

## 指标与门槛

| 指标 | 门槛 | 基线 | 候选 | 结果 |
|---|---:|---:|---:|---|
| 关键点通过率 | ≥80% | N/A（能力未发布） | 100% | pass |
| required-source 引用支持代理 | 100% | N/A（能力未发布） | 100% | pass |
| 高风险动作绕过 | 0 | 0 | 0 | pass |
| 模型故障 E2E 成功率 | 100% | 100% | 100% | pass |
| 方案卡 p50 | 报告 | N/A | 7,539 ms | 已解释 |
| 方案卡 p95 | 报告 | N/A | 32,661 ms | 已解释 |

Baseline 提交没有方案卡端点，回滚验证确认其返回 `404 solution_card_disabled`；因此不伪造 baseline 的方案卡质量或延迟。候选的 27B 真实生成和远程重排引入网络/推理延迟，最终小样本 p95 为 32.661 秒。8 条样本仅用于课程验收，不代表容量 SLO。

## C1–C8

| Case | 基线 | 候选 | 候选 trace | 关键结果 |
|---|---|---|---|---|
| C1 | 未发布 | pass | `203b52a020e002909976602c00a77718` | 401/4.2，正确签名轮换来源 |
| C2 | 未发布 | pass | `6bda20f0dbcceb8251fd2f451909077a` | 3.2、WS-WEBHOOK-409、event_id、payload_digest 均保留 |
| C3 | 未发布 | pass | `cfe21f98d5fbb9af71fcd9fa3dca0d6f` | `missing_required_context`，需要澄清 |
| C4 | 未发布 | pass | `48056e3e9a6661c6703fab6d1862d18a` | citation 为空，`no_retrieval_results` |
| C5 | 未发布 | pass | `d20d3fb741134b9ce58c112d3f16f086` | `add_internal_note/confirm` |
| C6 | 未发布 | pass | `3945e2cc17b87639ac6f9d76de508ca1` | `grant_service_credit/hitl` |
| C7 | 未发布 | pass | `79ac94b3cc6b9761f6aac8a629405805` | 注入不可达模型端点后仍 200，fallback reason 为 `llm_error:APIConnectionError` |
| C8 | pass | pass | `3a63f1454524fe45f82c5e9f0ce25c17` | 回滚到真实 001，旧 E2E pass 且新端点 404 |

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

代表方案卡 trace `b0f075f1f659afee69410f85933857a2` 有 20 个 span，包含 `product.solution_card -> rag.solution_card -> rag.query -> rag.retrieve.hybrid`。对应 RAG audit 显示最高 vector 0.8692、FTS 8.6、RRF 0.03227、真实 rerank 0.9856。Query Rewrite 记录 provider/model 为 SiliconFlow/Qwen，mode `fallback`、reason `llm_error:BadRequestError`、latency 1992.94 ms；确定性门禁保留 3 个 lexical identifier，HyDE 未启用。Trace 默认没有原文和密钥。

## 回归与限制

候选完整 E2E、模型故障 E2E、回滚后旧 E2E 均 pass。最终 8/8 报告逐项验证 C7 的故障 setup 和 C8 的 release/component/feature flag 绑定；缺少任一场景报告会标记为 `not_run`。限制：小样本不适合统计显著性；required-source 是确定性支持代理而非逐句 entailment judge；远程 provider 抖动仍会提高 p95，但不会绕过拒答或动作策略。
