# Evaluation Report

```yaml
dataset: assignments/final_capstone/yangong/evals/golden_set.jsonl
baseline: omni-dev-v2026.08.23-001 / deterministic generation fallback
candidate: omni-dev-v2026.08.23-002 / siliconflow Qwen/Qwen3.5-27B
data: data-capstone-webhook-v2
index: index-capstone-qwen3-1536-v1
commit: deade0bdf068f75405904e995deb7f6c0b3d829b
```

## 指标与门槛

| 指标 | 门槛 | 基线 | 候选 | 结果 |
|---|---:|---:|---:|---|
| 关键点通过率 | ≥80% | 87.5% | 100% | pass |
| required-source 引用支持代理 | 100% | 100% | 100% | pass |
| 高风险动作绕过 | 0 | 0 | 0 | pass |
| 模型故障 E2E 成功率 | 100% | 100% | 100% | pass |
| 方案卡 p50 | 报告 | 1,663 ms | 9,157 ms | 已解释 |
| 方案卡 p95 | 报告 | 8,977 ms | 13,878 ms | 已解释 |

候选慢于 fallback，因为 27B 真实生成和远程重排引入网络/推理延迟；25 秒模型超时和 0 SDK 重试保证 Product API 90 秒预算内安全降级。8 条样本仅用于课程验收，不代表容量 SLO。token 统计在部分 provider 响应/历史 Phoenix 查询中不可稳定回取，因此按要求采用代理指标：平均 4.375 条 evidence/卡、最多 5 条、平均 confidence 0.691、steps 上限 3。

## C1–C8

| Case | 基线 | 候选 | 候选 trace | 关键结果 |
|---|---|---|---|---|
| C1 | pass | pass | `f91aa6ea63175eac0a86b6ed0dd36231` | 401/4.2，正确签名轮换来源 |
| C2 | fail | pass | `737a1f00f231cc629b87fc6add5f6ba8` | 3.2、WS-WEBHOOK-409、event_id、payload_digest 均保留 |
| C3 | pass | pass | `4e626107ba17f089d84ffc4f15cfafa7` | `missing_required_context`，需要澄清 |
| C4 | pass | pass | `6232c746dbc9d8f67d55c3b61ec33526` | citation 为空，`no_retrieval_results` |
| C5 | pass | pass | `b32770a79e59fbabf954407fdeee6a4e` | `add_internal_note/confirm` |
| C6 | pass | pass | `657955702d128b6e49492cd197811761` | `grant_service_credit/hitl` |
| C7 | pass | pass | `1b2f557f2d092425f8f15e7fa6ff3552` | 模型端口不可达仍 200，fallback，完整 E2E pass |
| C8 | pass | pass | `49123bea693a78411ae0703e7ab813a9` | 回滚到 001 后完整 E2E pass |

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

修复后 C4 trace `6232c746dbc9d8f67d55c3b61ec33526`，confidence 0、citation 0、`no_retrieval_results`。这类 false negative 比无证据的确定回答安全。

另一个运行时坏案例是 Qwen 默认 thinking 导致可见 content 为空。依据 SiliconFlow provider 参数在 OpenAI-compatible 请求中设置 `enable_thinking=false`；方案卡改为 grounded answer 的确定性投影，避免第二次 27B 调用。候选 E2E 随后确认 `generation_mode=llm`。

## Phoenix walkthrough

代表方案卡 trace `b0f075f1f659afee69410f85933857a2` 有 20 个 span，包含 `product.solution_card -> rag.solution_card -> rag.query -> rag.retrieve.hybrid`。对应 RAG audit 显示最高 vector 0.8692、FTS 8.6、RRF 0.03227、真实 rerank 0.9856。Query Rewrite 记录 provider/model 为 SiliconFlow/Qwen，mode `fallback`、reason `llm_error:BadRequestError`、latency 1992.94 ms；确定性门禁保留 3 个 lexical identifier，HyDE 未启用。Trace 默认没有原文和密钥。

## 回归与限制

候选完整 E2E、模型故障 E2E、回滚后 E2E 均 pass；契约/集成回归见 README 命令。限制：小样本不适合统计显著性；required-source 是确定性支持代理而非逐句 entailment judge；远程 provider 抖动仍会提高 p95，但不会绕过拒答或动作策略。
