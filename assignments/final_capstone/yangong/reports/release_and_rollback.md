# 发布与回滚报告

```yaml
baseline_release: omni-dev-v2026.08.24-001
baseline_commit: 1473db6dfa785487e1a0f87bb97bdfec6719725c
baseline_manifest_digest: sha256:ab17254254181897787df97a591c47a0fc4aeeac652fa2225acf8712204d6d3f
candidate_release: omni-dev-v2026.08.24-003
candidate_commit: 6eed8cffb80c0d9786f460b1eb0afd8d0fa15c72
candidate_manifest_digest: sha256:c190567b2c60b39f0b6fa1adf051f749829449dafa4bcec240175802cd82b2bd
reissued_candidate_release: omni-dev-v2026.08.28-001
reissued_candidate_commit: 8176c947df96e92f5d976f96de9cbc00bdb7aaa7
reissued_candidate_manifest_digest: sha256:635e14c6799275248a9bb9114018d9286db5a5e41047755b69043b5509e371ec
rollback_generation: 5
post_rollback_e2e: pass
candidate_restored_generation: 6
baseline_same_rubric_eval_generation: 7
final_candidate_restored_generation: 8
```

## 真实的变更前绑定

Baseline `001` 由提交 `1473db6` 的代码和数据链生成，不包含本次两份 Webhook 文档及方案卡能力：

| 组件 | Baseline 001 | Candidate 003 |
|---|---|---|
| data | `data-capstone-v1` | `data-capstone-webhook-v2` |
| index | `index-capstone-v1` | `index-capstone-qwen3-1536-v1` |
| embedding | `deterministic-hash-embedding-v1@1536` | `Qwen/Qwen3-Embedding-4B@1536` |
| prompt | `prompt-capstone-v1`，无方案卡模板 | `prompt-solution-card-v1` |
| graph | `graph-capstone-prechange-v1`，91 个 source chunk | `graph-capstone-webhook-v2`，117 个 source chunk |
| service | `service-capstone-v1` | `service-solution-card-v1` |
| feature flag | `solution_card=false` | `solution_card=true` |

完整 baseline 绑定保存在 [baseline_component_bindings.json](baseline_component_bindings.json)，受治理 manifest 的 digest 保护。

## 实测状态序列

1. 注册真实 baseline `001` 与最终候选 `003`。
2. 从 `001` 提升 `003`，generation 4；候选服务和 Qwen 向量索引健康。
3. 使用 direct-ancestor、expected-current 和必填 reason 原子回滚 `003 -> 001`，generation 5。
4. 从提交 `1473db6` 的临时 worktree 恢复 baseline 数据、91 个确定性向量和图绑定，并以 `SOLUTION_CARD_ENABLED=false` 重建服务。
5. 运行旧产品 E2E：RAG、KPI、低风险动作和 HITL 均 pass；运行时 release 与 active pointer 都为 `001`，方案卡端点返回 `404 solution_card_disabled`。
6. 验证结束后重新提升 `003`，generation 6，并恢复 117 个 Qwen 文档向量和候选服务。
7. 为补齐 R8，同样再次切到真实 `001`（generation 7），用相同 8 条问题逐条记录 `404 solution_card_disabled`；随后恢复 `003`（generation 8）。最终 runtime、RAG 与 active pointer 均为 `003`。

机器证据为 [e2e-post-rollback.json](raw/e2e-post-rollback.json)：trace `3a63f1454524fe45f82c5e9f0ce25c17`，明确记录 baseline 的 data/index/prompt/graph 四项绑定以及方案卡关闭结果。最终 Golden Set 只有在该报告与 baseline manifest 完全匹配时才允许 C8 通过。

## 候选 manifest 重新签发

首个候选 `003` 在提交 `6eed8cf` 上签发，之后的 `a9e2bf7`、`84ef892`、`8176c94` 又改动了它绑定的文件却没有重新签发，因此 `003` 已经不再描述当前代码：

| 问题 | 具体表现 |
|---|---|
| 实现摘要过期 | `8176c94` 把 `solution_card.py` 的 citation 选取改为只保留覆盖问题中每个精确标识符的 source 级 citation，并在 abstain 时清空 citations；`003` 记录的是该修复前的摘要 |
| 门禁证据过期 | `003` 的 `quality.eval.report_path` 指向已废弃的 `raw/solution-card-eval-pre-release.json`，并绑定同样已废弃的 `raw/e2e-candidate.json` |
| 绑定缺口 | `raw/solution-card-eval-candidate.json`、`raw/solution-card-eval-baseline.json`、`raw/e2e-candidate-final.json`、`raw/bootstrap-replay.json` 未被任何 manifest 保护 |

`python -m release.verify` 把 `003` 的三处漂移报为 `mismatch`：`services/rag_api/app/solution_card.py`、`services/copilot_api/app/main.py` 和 `raw/e2e-model-fault.json`。manifest 不可变（生成器以 `open("x")` 写入），所以在 `8176c94` 上按当前 spec 重新签发了 `omni-dev-v2026.08.28-001`，`previous_release_id` 链到 `003`，复核结果为零漂移。

`git_sha` 落后 HEAD 本身不足以判定问题：只有当落后的提交动过被绑定的 artifact 时绑定才失效，这正是复核 `artifact_digests` 而非比较提交号的原因。

本次没有重跑验收，因此 `reports/raw` 里的 `release_id` 仍是运行标签 `omni-dev-v2026.08.24-003`。`08.28-001` 与 `003` 指向同一提交的同一批 artifact，但要让运行标签与受治理 id 完全一致，必须用新 id 重跑 bootstrap、C7 故障注入、C8 回滚与 baseline 同口径评测。注册和提升依赖运行中的 Postgres，尚未执行：

```bash
python -m release.verify \
  assignments/final_capstone/yangong/reports/releases/omni-dev-v2026.08.28-001.json
python -m release.registry register \
  --manifest assignments/final_capstone/yangong/reports/releases/omni-dev-v2026.08.28-001.json
python -m release.registry promote \
  --release-id omni-dev-v2026.08.28-001 \
  --expected-current-release-id omni-dev-v2026.08.24-003 --actor yangong
```

## 注册、提升与回滚命令

```bash
python -m release.registry register \
  --manifest assignments/final_capstone/yangong/reports/releases/omni-dev-v2026.08.24-001.json
python -m release.registry register \
  --manifest assignments/final_capstone/yangong/reports/releases/omni-dev-v2026.08.24-003.json
python -m release.registry promote \
  --release-id omni-dev-v2026.08.24-003 \
  --expected-current-release-id omni-dev-v2026.08.24-001 --actor yangong
python -m rollout.rollback \
  --target-release-id omni-dev-v2026.08.24-001 \
  --current-release-id omni-dev-v2026.08.24-003 --actor yangong \
  --reason c8_verified_prechange_rollback_final
```

回滚指针后，使用变更前提交恢复数据和索引 artifact（命令中的数据库和 MinIO 参数与仓库默认 Compose 一致）：

```bash
baseline_tree=$(mktemp -d /tmp/omnisupport-baseline-XXXXXX)
rmdir "$baseline_tree"
git worktree add --detach "$baseline_tree" 1473db6
for stage in ingest knowledge analytics graph; do
  docker run --rm --network infra_omni_net \
    -v "$baseline_tree:/workspace" -w /workspace \
    -e PYTHONPATH=/workspace \
    -e DATABASE_URL=postgresql://omni:omnipass@postgres:5432/omnisupport \
    -e MINIO_ENDPOINT=http://minio:9000 \
    -e MINIO_ACCESS_KEY=minioadmin -e MINIO_SECRET_KEY=minioadmin \
    -e EMBEDDING_MODEL=deterministic \
    -e CAPSTONE_RELEASE_ID=capstone-prechange-v1.0.0 \
    -e CAPSTONE_DATA_RELEASE_ID=data-capstone-v1 \
    -e CAPSTONE_INDEX_RELEASE_ID=index-capstone-v1 \
    -e CAPSTONE_PROMPT_RELEASE_ID=prompt-capstone-v1 \
    -e CAPSTONE_GRAPH_RELEASE_ID=graph-capstone-prechange-v1 \
    -e OTEL_ENABLED=false \
    infra-capstone_bootstrap python -m scripts.capstone.bootstrap \
    --root /workspace --stage "$stage"
done
git worktree remove --force "$baseline_tree"

CAPSTONE_RELEASE_ID=omni-dev-v2026.08.24-001 \
CAPSTONE_DATA_RELEASE_ID=data-capstone-v1 \
CAPSTONE_INDEX_RELEASE_ID=index-capstone-v1 \
CAPSTONE_PROMPT_RELEASE_ID=prompt-capstone-v1 \
CAPSTONE_GRAPH_RELEASE_ID=graph-capstone-prechange-v1 \
LLM_PROVIDER=fallback QUERY_REWRITE_STRATEGY=deterministic \
EMBEDDING_PROVIDER=auto EMBEDDING_MODEL=deterministic \
RERANK_PROVIDER=disabled SOLUTION_CARD_ENABLED=false \
docker compose --env-file infra/env/.env.local -f infra/docker-compose.yml \
  up -d --force-recreate --no-deps rag_api tool_api copilot_api
```

本地 Compose 没有部署控制器，所以指针切换后显式恢复 manifest 指定的数据/index artifact，并用 `--force-recreate` 对齐服务环境。生产环境应由部署控制器根据受治理 manifest 原子协调镜像、配置、索引和指针。
