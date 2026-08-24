# Release and Rollback

```yaml
release_id: omni-dev-v2026.08.23-002
implementation_commit: deade0bdf068f75405904e995deb7f6c0b3d829b
data_release_id: data-capstone-webhook-v2
index_release_id: index-capstone-qwen3-1536-v1
prompt_release_id: prompt-solution-card-v1
skill/service release: skills-capstone-existing-v1 / service-solution-card-v1
gates: contract / eval / security / e2e = pass
activation_evidence: release.promoted generation 4, manifest sha256:a20722a2c2343f9f8e68066381a0f841fd43439dfd567ece16d4a81242d4c0ba
rollback_target: omni-dev-v2026.08.23-001
rollback_verification: generation 5 + reports/capstone/e2e-post-rollback.json pass
```

候选 manifest 随提交保存在 [omni-dev-v2026.08.23-002.json](releases/omni-dev-v2026.08.23-002.json)，其直接祖先为 [001](releases/omni-dev-v2026.08.23-001.json)。两者都通过 v2 JSON Schema、digest 完整性和 release policy；候选附带 data/index/prompt/model/skills/graph/service 的 artifact digest，以及候选评测、正常 E2E 和故障 E2E 的 digest。

实测状态序列：

1. 注册 `001`、`002`。
2. 从 bootstrap pointer `capstone-webhook-v2.0.0` 激活 `001`，generation 3。
3. 以 expected-current=`001` 激活候选 `002`，generation 4。
4. 查询 active 返回 `002` 和完整 manifest。
5. 用 direct-ancestor、expected-current 和必填 reason 原子回滚 `002 -> 001`，generation 5。
6. 以 `CAPSTONE_RELEASE_ID=omni-dev-v2026.08.23-001` 重启 RAG/Tool/Product，完整 E2E pass；RAG、方案卡、动作返回的 release_id 与 active pointer 一致。

关键命令：

```bash
python -m release.registry register --manifest artifacts/releases/omni-dev-v2026.08.23-002.json
python -m release.registry promote --release-id omni-dev-v2026.08.23-002 \
  --expected-current-release-id omni-dev-v2026.08.23-001 --actor yangong
python -m rollout.rollback --target-release-id omni-dev-v2026.08.23-001 \
  --current-release-id omni-dev-v2026.08.23-002 --actor yangong \
  --reason c8_verified_atomic_rollback
```

数据库审计链最后三项依次为：promote 到 `001`、promote 到 `002`、rollback 到 `001`；generation 分别为 3、4、5。由于本地 Compose 没有部署控制器，指针变化后由显式 `--force-recreate` 让进程内版本对齐；生产应由控制器自动完成镜像、配置和指针协调。
