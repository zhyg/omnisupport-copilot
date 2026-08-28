# Webhook 问题处理方案卡

```yaml
baseline_commit: 1473db6dfa785487e1a0f87bb97bdfec6719725c
candidate_commit: 8176c947df96e92f5d976f96de9cbc00bdb7aaa7
theme: webhook-troubleshooting
provider/model: siliconflow / Qwen/Qwen3.5-27B; embedding Qwen/Qwen3-Embedding-4B; rerank Pro/BAAI/bge-reranker-v2-m3
governed_release_id: omni-dev-v2026.08.28-001（在 8176c94 上重新签发，绑定当前代码与最终证据）
runtime_release_label: omni-dev-v2026.08.24-003（实测运行时标签；C8 回滚到 001 后已恢复候选）
golden_set: 8 cases, 8 passed
hard_gates: G1..G6 pass
capstone_e2e: pass
representative_trace_id: 92d5a759c5a6e1d6d952b6c0deb84a51
known_limitations:
  - local Compose has no HA or deployment controller
  - eight-case latency sample is not a capacity test
  - provider model aliases are pinned by release metadata, not self-hosted weights
```

该能力为 Northstar Workspace 坐席生成一张证据约束的 Webhook 排障卡。它不是自由聊天：输出字段被冻结，citation 只能来自检索结果，动作由服务端策略决定，未知精确错误码会拒答，财务动作必须进入 HITL。

## 前置条件与配置

- Docker Compose；首次构建 Devbox 建议预留 20 GB。
- 在 `infra/env/.env.local` 配置 SiliconFlow 密钥和模型变量；该文件被 `.gitignore` 排除。
- 不把密钥复制进 `.env.example`、报告、Trace 或命令输出。

`infra/env/.env.local` 至少包含以下非密钥配置；三个 API Key 变量填写同一个 SiliconFlow Key：

```bash
SILICONFLOW_API_KEY=<本地密钥>
EMBEDDING_API_KEY=<同一个本地密钥>
RERANK_API_KEY=<同一个本地密钥>
LLM_PROVIDER=siliconflow
LLM_MODEL=Qwen/Qwen3.5-27B
LLM_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_PROVIDER=siliconflow
EMBEDDING_MODEL=Qwen/Qwen3-Embedding-4B
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_DIMENSIONS=1536
RERANK_PROVIDER=siliconflow
RERANK_MODEL=Pro/BAAI/bge-reranker-v2-m3
RERANK_BASE_URL=https://api.siliconflow.cn/v1
CAPSTONE_RELEASE_ID=omni-dev-v2026.08.24-003
CAPSTONE_DATA_RELEASE_ID=data-capstone-webhook-v2
CAPSTONE_INDEX_RELEASE_ID=index-capstone-qwen3-1536-v1
CAPSTONE_PROMPT_RELEASE_ID=prompt-solution-card-v1
CAPSTONE_GRAPH_RELEASE_ID=graph-capstone-webhook-v2
CAPSTONE_AS_OF=2026-08-23T00:00:00Z
SOLUTION_CARD_ENABLED=true
```

## 一键启动与验收

```bash
docker compose --env-file infra/env/.env.local -f infra/docker-compose.yml up -d --build
docker compose --env-file infra/env/.env.local -f infra/docker-compose.yml --profile capstone run --rm \
  capstone_bootstrap python -m scripts.capstone.bootstrap --root /workspace --stage all \
  --output assignments/final_capstone/yangong/reports/raw/bootstrap-all.json
docker compose --env-file infra/env/.env.local -f infra/docker-compose.yml --profile capstone run --rm \
  capstone_bootstrap python -m scripts.capstone.bootstrap --root /workspace --stage all \
  --skip-release-registration \
  --output assignments/final_capstone/yangong/reports/raw/bootstrap-replay.json
docker compose --env-file infra/env/.env.local -f infra/docker-compose.yml --profile capstone run --rm \
  --entrypoint python capstone_bootstrap -m scripts.capstone.verify_e2e \
  --require-llm --expected-release-id omni-dev-v2026.08.24-003 \
  --output assignments/final_capstone/yangong/reports/raw/e2e-candidate-final.json
docker compose --env-file infra/env/.env.local -f infra/docker-compose.yml --profile capstone run --rm \
  --entrypoint python capstone_bootstrap -m scripts.capstone.evaluate_solution_cards \
  --expected-release-id omni-dev-v2026.08.24-003 \
  --fault-report assignments/final_capstone/yangong/reports/raw/e2e-model-fault.json \
  --rollback-report assignments/final_capstone/yangong/reports/raw/e2e-post-rollback.json \
  --rollback-manifest assignments/final_capstone/yangong/reports/releases/omni-dev-v2026.08.24-001.json \
  --expected-rollback-release-id omni-dev-v2026.08.24-001 \
  --output assignments/final_capstone/yangong/reports/raw/solution-card-eval-candidate.json
```

两次 bootstrap 分别写入独立报告：[首次](reports/raw/bootstrap-all.json)记录 `tickets.inserted=240`、117 个当前 chunk（`index.embedded=91/skipped=26`，因为 26 个向量已存在），[重放](reports/raw/bootstrap-replay.json)记录 `tickets.skipped=240`、`index.embedded=0/skipped=117`。E2E 顶层应为 `status=pass`，Golden Set 应为 `passed=8`。产品入口为 <http://localhost:8010>，内部 RAG OpenAPI 为 <http://localhost:8000/docs>，Phoenix 为 <http://localhost:6006>。

上面的 `omni-dev-v2026.08.24-003` 是产出这批证据时运行时实际使用的 release 标签（`CAPSTONE_RELEASE_ID`），所以命令和 `reports/raw` 里的 `release_id` 保持一致，可原样复现。同一提交的受治理记录是重新签发的 `omni-dev-v2026.08.28-001`；两者指向相同的代码与 artifact，但标签要完全对齐需要把 `CAPSTONE_RELEASE_ID` 与 `--expected-release-id` 换成新 id 后重跑整套验收。

## 测试与发布

```bash
docker compose --env-file infra/env/.env.local -f infra/docker-compose.yml --profile capstone run --rm \
  --entrypoint pytest capstone_bootstrap tests/contract tests/integration -q
release_output_dir=$(mktemp -d)
python -m release.generator --spec release/specs/final_capstone_baseline.yaml \
  --output-dir "$release_output_dir" --environment dev --created-by yangong \
  --git-sha 1473db6dfa785487e1a0f87bb97bdfec6719725c
python -m release.generator --spec release/specs/final_capstone_webhook.yaml \
  --output-dir "$release_output_dir" --environment dev --created-by yangong \
  --git-sha 8176c947df96e92f5d976f96de9cbc00bdb7aaa7 \
  --previous-manifest "$release_output_dir"/omni-dev-*.json
python -m release.verify assignments/final_capstone/yangong/reports/releases/*.json
```

已生成的 manifest 是 baseline [001](reports/releases/omni-dev-v2026.08.24-001.json)、首个候选 [003](reports/releases/omni-dev-v2026.08.24-003.json) 和重新签发的候选 [08.28-001](reports/releases/omni-dev-v2026.08.28-001.json)。原始报告均在 [reports/raw](reports/raw/)；注册、激活和回滚证据见 [release_and_rollback.md](reports/release_and_rollback.md)。

`release.verify` 是发布前的 digest 复核：manifest 的自摘要在其绑定的文件被改动后仍然自洽，所以必须把 `artifact_digests` 与工作区重新比对，否则代码漂移不会被任何门禁发现。候选 `003` 正是这样漂移的，`08.28-001` 是据此重新签发的结果，详情见[发布与回滚报告](reports/release_and_rollback.md)。该命令对 `001` 与 `08.28-001` 返回 `status=ok`，对 `003` 返回 `status=fail` 并列出 3 处 `mismatch`。

Baseline 同口径评测必须在 001 runtime、active pointer 与真实旧 artifact 均恢复后运行；8 条问题会逐条实测 `404 solution_card_disabled`，报告质量指标为 0%，命令如下：

```bash
docker compose --env-file infra/env/.env.local -f infra/docker-compose.yml --profile capstone run --rm \
  --entrypoint python capstone_bootstrap -m scripts.capstone.evaluate_solution_cards \
  --expected-release-id omni-dev-v2026.08.24-001 --expect-solution-card-disabled \
  --output assignments/final_capstone/yangong/reports/raw/solution-card-eval-baseline.json
```

## C7/C8 场景前置条件

C7 不能用正常请求代替故障注入。以下命令把 RAG 的生成和改写端点切到本容器不可达端口，运行验证器后再恢复候选配置：

```bash
LLM_BASE_URL=http://127.0.0.1:9/v1 LLM_TIMEOUT_SECONDS=1 LLM_MAX_RETRIES=0 \
QUERY_REWRITE_BASE_URL=http://127.0.0.1:9/v1 QUERY_REWRITE_TIMEOUT_SECONDS=1 \
docker compose --env-file infra/env/.env.local -f infra/docker-compose.yml \
  up -d --force-recreate --no-deps rag_api
docker compose --profile capstone --env-file infra/env/.env.local \
  -f infra/docker-compose.yml run --rm --no-deps --entrypoint python \
  capstone_bootstrap -m scripts.capstone.verify_e2e \
  --scenario llm_fault --expected-generation-mode deterministic_fallback \
  --expected-release-id omni-dev-v2026.08.24-003 \
  --output reports/capstone/e2e-model-fault.json
docker compose --env-file infra/env/.env.local -f infra/docker-compose.yml \
  up -d --force-recreate --no-deps rag_api
```

C8 必须恢复真实的旧 artifact，而不仅是修改 release 标签。先从 baseline 提交创建临时 worktree，并使用其中的 bootstrap 恢复 `data-capstone-v1/index-capstone-v1/graph-capstone-prechange-v1`；再回滚指针、设置 `SOLUTION_CARD_ENABLED=false` 并重建三个服务。验证命令为：

```bash
python -m rollout.rollback \
  --target-release-id omni-dev-v2026.08.24-001 \
  --current-release-id omni-dev-v2026.08.24-003 --actor yangong \
  --reason c8_verified_prechange_rollback_final
docker compose --profile capstone --env-file infra/env/.env.local \
  -f infra/docker-compose.yml run --rm --no-deps --entrypoint python \
  capstone_bootstrap -m scripts.capstone.verify_e2e \
  --scenario release_rollback \
  --expected-release-id omni-dev-v2026.08.24-001 \
  --expected-generation-mode deterministic_fallback \
  --expect-solution-card-disabled \
  --output reports/capstone/e2e-post-rollback.json
```

完整的 worktree 恢复参数、组件计数与 generation 序列记录在 [发布与回滚报告](reports/release_and_rollback.md)。验证器会同时检查 active pointer、四项组件绑定和方案卡 feature flag；仅改变 `RELEASE_ID` 会失败。

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
