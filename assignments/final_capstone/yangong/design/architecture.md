# Architecture

## 产品问题

目标用户是处理 Northstar Workspace 工单的一线坐席。触发条件是工单涉及 Webhook HTTP 401、签名密钥轮换、重复投递或幂等冲突。成功结果不是一段“看起来合理”的文本，而是一张可被产品和审计系统消费的方案卡：一句诊断、最多三步、真实 citation、置信度、澄清/拒答状态、受控动作建议、release_id 和 trace_id。

非目标包括训练模型、更换 PostgreSQL/pgvector、建立完整 GraphRAG、自动执行补偿、接入真实客户数据和生产级容量建设。

## 请求主链

```text
Browser -> Product API (JWT/tenant/case authorization)
        -> RAG API (internal token + tenant/actor headers)
        -> deterministic Query Rewrite gate
        -> vector + PostgreSQL FTS -> RRF -> remote rerank
        -> evidence pruning -> protected-identifier coverage gate
        -> grounded LLM answer or auditable fallback
        -> deterministic SolutionCard projection
        -> Product persistence/audit -> UI card
        -> optional existing action dialog -> Tool policy -> confirm/HITL/idempotency
```

浏览器只调用 Product API。RAG 和 Tool 的内部 token 不下发到前端。Product API 先用 JWT 解析 tenant/role，再验证 case 的 tenant；内部调用显式转发 tenant、actor、role 和 request_id。

## 数据链和版本

两份合成 HTML 文档分别覆盖 Workspace 3.2–4.2 的签名轮换与投递幂等。静态 manifest 固定 source_id、版本、许可、PII 状态、字节数和 SHA-256。`generate_demo_data.py` 将它们以 `assignment:` 前缀纳入 Workspace manifest，复用现有 MinIO ingest、parse、section-aware chunk、evidence anchor 和 pgvector 索引链。

数据版本为 `data-capstone-webhook-v2`，索引为 `index-capstone-qwen3-1536-v1`，Prompt 为 `prompt-solution-card-v1`，Graph 为 `graph-capstone-webhook-v2`。首次引导写入 240 个工单和 117 个向量；第二次同输入工单全跳过、向量全跳过。候选模型包由一个 release 同时绑定：

- generation：`Qwen/Qwen3.5-27B`
- embedding：`Qwen/Qwen3-Embedding-4B`，输出 1536 维
- rerank：`Pro/BAAI/bge-reranker-v2-m3`

## 检索、生成和失败边界

Query Rewrite 保持三个语义不同的字段：`semantic_query` 做向量召回，`lexical_terms` 保留错误码/版本，原始 question 用于 rerank 与生成。LLM 改写必须通过 JSON、长度、受保护标识和禁止新增标识门禁；失败回到确定性改写。本次候选的代表 trace 中改写 provider/model 是 SiliconFlow/Qwen，因 Structured Output 400 降级为 `fallback`，但 `WS-WEBHOOK-401`、`HTTP 401`、`4.2` 均被保留。

Hybrid Retrieval 先独立计算 vector 与 FTS 排名，再用 RRF 合并，最后远程 rerank。代表 trace 的前五项均有 `vector_score`、`fts_score`、`rrf_score` 和真实 `rerank_score`，最高重排分为 0.9856。

生成前新增确定性标识覆盖门禁：问题中的错误码/版本必须逐字出现在候选证据中。`WS-QUANTUM-999` 即使语义检索到了通用 Webhook 文档，也会清空生成上下文和 citation，返回 `no_retrieval_results`。这避免“相似文档”被误当成“精确代码的证据”。

LLM 只生成 evidence-bounded answer。方案卡是该 answer 的确定性投影；citation 从检索 metadata 复制，动作由代码策略生成，模型不能写入任意 source、operation 或 control。这样少一次 27B 调用并缩短超时窗口。

## 动作控制

方案卡只建议、不执行：

| 意图 | 建议 | 控制 |
|---|---|---|
| 普通排障 | `none` | `none` |
| 写 internal note | `add_internal_note` | `confirm` |
| service credit/refund | `grant_service_credit` | `hitl` |
| 任何拒答 | `none` | `none` |

用户点击建议后进入既有动作对话框。低风险备注要求显式确认和 idempotency key；财务补偿由 Tool API 创建 approval，管理员批准后才 resume。Product API 只允许引用同 tenant 工单中由消息或方案卡真实持久化的 evidence_id。

## 可观测与隐私

Product、RAG、rewrite、retrieve、generate、audit、HITL wait/resume 使用同一 W3C trace。`OTEL_CAPTURE_CONTENT=false`，Trace 记录 query hash/length、tenant、版本、模式、分数、耗时和 fallback_reason，不记录问题原文、客户 PII 或密钥。代表方案卡 trace `b0f075f1f659afee69410f85933857a2` 在 Phoenix 有 20 个 span。

## 发布取舍

候选 governed manifest 对 data/index/prompt/model/skills/graph/service 和评测报告逐文件计算 digest。注册后通过乐观锁指针从 bootstrap release 切到 `001`，再切到候选 `002`，最后原子回滚 `002 -> 001`。本地 Compose 需要显式重启服务以让进程内 `RELEASE_ID` 与指针对齐；生产需要部署控制器监听指针并协调镜像/配置回滚。
