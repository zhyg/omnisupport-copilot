# Webhook 问题处理方案卡

```yaml
baseline_commit: 1473db6dfa785487e1a0f87bb97bdfec6719725c
candidate_commit: deade0bdf068f75405904e995deb7f6c0b3d829b
candidate_worktree: implementation committed; evidence metadata updated in a follow-up commit
theme: webhook-troubleshooting
provider/model: siliconflow / Qwen/Qwen3.5-27B; embedding Qwen/Qwen3-Embedding-4B; rerank Pro/BAAI/bge-reranker-v2-m3
release_id: omni-dev-v2026.08.23-002 (rolled back to omni-dev-v2026.08.23-001)
golden_set: 8 cases, 8 passed
hard_gates: G1..G6 pass
capstone_e2e: pass
representative_trace_id: b0f075f1f659afee69410f85933857a2
known_limitations:
  - local Compose has no HA or deployment controller
  - eight-case latency sample is not a capacity test
  - provider model aliases are pinned by release metadata, not self-hosted weights
```

该能力为 Northstar Workspace 坐席生成一张证据约束的 Webhook 排障卡。它不是自由聊天：输出字段被冻结，citation 只能来自检索结果，动作由服务端策略决定，未知精确错误码会拒答，财务动作必须进入 HITL。

## 前置条件与配置

- Docker Compose；首次构建 Devbox 建议预留 20 GB。
- 仓库根目录的 `llm.txt`，仅用于本地读取 SiliconFlow 密钥，已被 `.gitignore` 排除。
- 不把密钥复制进 `.env.example`、报告、Trace 或命令输出。

从仓库根目录加载本地密钥和候选版本变量：

```bash
export SILICONFLOW_API_KEY="$(awk '/api-key/{print $2}' llm.txt)"
export EMBEDDING_API_KEY="$SILICONFLOW_API_KEY"
export RERANK_API_KEY="$SILICONFLOW_API_KEY"
export LLM_PROVIDER=siliconflow
export LLM_MODEL='Qwen/Qwen3.5-27B'
export LLM_BASE_URL='https://api.siliconflow.cn/v1'
export LLM_TIMEOUT_SECONDS=25
export LLM_MAX_RETRIES=0
export QUERY_REWRITE_PROVIDER=siliconflow
export QUERY_REWRITE_MODEL='Qwen/Qwen3.5-27B'
export QUERY_REWRITE_BASE_URL='https://api.siliconflow.cn/v1'
export EMBEDDING_PROVIDER=siliconflow
export EMBEDDING_MODEL='Qwen/Qwen3-Embedding-4B'
export EMBEDDING_BASE_URL='https://api.siliconflow.cn/v1'
export EMBEDDING_DIMENSIONS=1536
export RERANK_PROVIDER=siliconflow
export RERANK_MODEL='Pro/BAAI/bge-reranker-v2-m3'
export RERANK_BASE_URL='https://api.siliconflow.cn/v1'
export CAPSTONE_RELEASE_ID='capstone-webhook-v2.0.0'
export CAPSTONE_DATA_RELEASE_ID='data-capstone-webhook-v2'
export CAPSTONE_INDEX_RELEASE_ID='index-capstone-qwen3-1536-v1'
export CAPSTONE_PROMPT_RELEASE_ID='prompt-solution-card-v1'
export CAPSTONE_GRAPH_RELEASE_ID='graph-capstone-webhook-v2'
export CAPSTONE_AS_OF='2026-08-23T00:00:00Z'
```

## 一键启动与验收

```bash
docker compose -f infra/docker-compose.yml up -d --build
docker compose -f infra/docker-compose.yml --profile capstone run --rm capstone_bootstrap
docker compose -f infra/docker-compose.yml --profile capstone run --rm capstone_bootstrap
docker compose -f infra/docker-compose.yml --profile capstone run --rm \
  --entrypoint python capstone_bootstrap -m scripts.capstone.verify_e2e \
  --require-llm --output reports/capstone/e2e-candidate.json
docker compose -f infra/docker-compose.yml --profile capstone run --rm \
  --entrypoint python capstone_bootstrap -m scripts.capstone.evaluate_solution_cards \
  --expected-release-id capstone-webhook-v2.0.0 \
  --output reports/capstone/solution-card-eval-candidate.json
```

预期：bootstrap 首次得到 240 个工单、117 个 chunk；第二次 `tickets.skipped=240`、`index.skipped=117`；E2E 顶层 `status=pass`；Golden Set `passed=8`。产品入口为 <http://localhost:8010>，内部 RAG OpenAPI 为 <http://localhost:8000/docs>，Phoenix 为 <http://localhost:6006>。

## 测试与发布

```bash
docker compose -f infra/docker-compose.yml --profile capstone run --rm \
  --entrypoint pytest capstone_bootstrap tests/contract tests/integration -q
python -m release.generator --spec release/specs/final_capstone_webhook.yaml \
  --output-dir artifacts/releases --environment dev --created-by yangong \
  --previous-manifest artifacts/releases/omni-dev-v2026.08.23-001.json
```

已生成的候选 manifest 是 [omni-dev-v2026.08.23-002.json](reports/releases/omni-dev-v2026.08.23-002.json)。注册、激活、回滚命令和实测 generation 见 [release_and_rollback.md](reports/release_and_rollback.md)。

## 故障排查

- `generation_mode=deterministic_fallback`：检查密钥是否存在、base URL 是否为 `/v1`，以及 `LLM_PROVIDER=siliconflow`；降级仍应返回 200。
- `BadRequestError` 出现在 Query Rewrite：候选会保留原始问题和精确标识并退回确定性改写；可从 `query_rewrite.fallback_reason` 定位。
- `502 rag_api_unavailable`：检查 `omni_rag_api` 日志和 90 秒 Product API 依赖超时；本作业将模型调用限制为 25 秒、0 SDK 重试。
- 向量维度错误：必须保持 `EMBEDDING_DIMENSIONS=1536`，与 PostgreSQL `vector(1536)` 契约一致。
- 磁盘不足：只清理 build cache 和停止容器，不删除数据库/MinIO/Phoenix volumes。

## 提交物导航

- [架构与边界](design/architecture.md)
- [数据 manifest](data/manifest_webhook_troubleshooting.json)
- [方案卡能力契约](contracts/capability.md)
- [Golden Set](evals/golden_set.jsonl)
- [基线](reports/baseline.md)
- [评测与 Trace](reports/eval_report.md)
- [E2E 汇总](reports/e2e_report.json)
- [发布与回滚](reports/release_and_rollback.md)
- [演示脚本](demo/demo_script.md)
- [反思](reflection.md)
