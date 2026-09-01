# 里程碑作业（Week 1–5 综合）评分指南

> 整理自《里程碑作业（Week 1–5 综合）·标准答案与详尽解析》。
>
> 配套作业：《让一个新指标「从源头走到能被安全调用」》。
>
> 主线指标：`resolution_rate`（工单解决率）；选择 `avg_resolution_hours` 时按第 10 节的替代口径评分。

内容来源说明：本文的评分维度、分值、固定扣分项、交付档位、标准实现和验收要求均来自源 DOCX；为便于实际批改，额外做了章节重排，并归纳了批改顺序、证据表、评分记录表和勾选清单。这些整理内容不新增分值、扣分项或门槛。

## 1. 评分结论与执行顺序

本作业满分 **100 分**，按七个维度评分：

| 评分维度 | 分值 |
|---|---:|
| 阶段一：口径与边界 | 12 |
| 阶段二：契约门禁 | 15 |
| 阶段三：入湖与补数 | 15 |
| 阶段四：时间旅行与性能基线 | 13 |
| 阶段五：dbt、注册表与受控工具 | 30 |
| 阶段六：端到端贯通与越权反例 | 10 |
| 文档可读性与证据可追溯性 | 5 |
| **合计** | **100** |

为便于执行，可按源文档的主线整理为以下批改顺序：

1. 确认学员选择的指标及其业务口径。
2. 检查分子、分母、除零保护和结果范围。
3. 沿“契约 → 入湖/补数 → Iceberg → dbt → 注册表 → 工具”逐环核验证据。
4. 重点检查指标是否经过四处显式放行，以及 Agent 视图、角色和查询窗口是否安全。
5. 执行或复核正向查询与越权拒绝两个端到端案例。
6. 按七个维度逐项计分，再对照交付档位。

> 源 DOCX 未列出独立的硬门槛或一票否决规则。应按七个维度和第 9 节交付档位评分，不另行增加门槛。

## 2. 总体评分原则

本次作业是巩固型里程碑，不以代码量、复杂架构或命名风格取胜。除明确评分项外，代码风格和命名细节从宽。重点判断以下三条主线。

### 2.1 口径正确

- 分子：当天状态属于 `resolved` 或 `closed` 的工单数，即 `resolved_ticket_count`。
- 分母：当天全部工单数，即 `ticket_count`，不得只统计已解决工单。
- 公式：`resolved_ticket_count / nullif(ticket_count, 0)`，必须防止除零。
- 结果：`resolution_rate` 应落在 `[0, 1]`。
- 比率不可直接跨维度求和；上层应按定义重算，或在注册表中声明合适的聚合方式。

### 2.2 链路完整

应能从证据中串起以下链路，而不是只在某一层算出指标：

```text
口径与边界
  → 数据契约
  → 增量入湖与补数
  → Iceberg 快照与性能基线
  → dbt intermediate / mart / safe view
  → 指标注册表
  → Tool 契约与受控查询
  → 正向查询、越权拒绝和审计
```

### 2.3 安全设计到位

- 指标默认不可被 Agent 查询，必须在 **mart、safe view、指标注册表、Tool 契约**四处显式放行。
- Agent 可见视图不得包含 `customer_id`、`assignee_id` 等可定位个人的字段。
- Agent 不得绕过受控工具直接查询原始 `tickets` 表，也不得返回明细工单行。
- 查询应执行注册表校验、角色校验、窗口校验并留下审计记录。
- 有权限能查只证明功能可用；越权请求被拒并留痕，才证明控制有效。

## 3. 标准实现基线

评分时以“行为和证据是否满足要求”为准，不要求代码逐字等同于参考答案。标准职责位置如下：

| 环节 | 参考位置 | 评分关注点 |
|---|---|---|
| 口径与边界 | `docs/blueprints/milestone_resolution_rate_acceptance.md` | 指标定义、维度、PII、角色、HITL 和红线 |
| 数据契约 | `contracts/data/ticket_contract.json` | `status`、`created_at`、`resolved_at` 及非法枚举拦截 |
| 入湖与补数 | `pipelines/ingestion/ticket_ingest.py`、`ingest_state.py`、`replay_backfill.py` | 水位、缺口、dry-run 和幂等 |
| Iceberg | `pipelines/lakehouse/materialize.py`、`demo_time_travel.py`、`perf_baseline.py` | 快照对比与自然状态基线 |
| dbt intermediate | `analytics/models/intermediate/int_ticket_activity_daily.sql` | `ticket_count`、`resolved_ticket_count` |
| dbt mart | `analytics/models/marts/support_kpi_mart.sql` | 比率计算和除零保护 |
| Agent 安全视图 | `analytics/models/marts/agent_tool_input_view.sql` | 指标白名单和无 PII |
| 指标注册表 | `analytics/metric_registry_v1.yml` | 业务定义、类型、聚合、权限和质量测试 |
| Tool 契约 | `contracts/tools/tools/query_support_kpis_v1.json` | 可查询指标枚举 |
| Tool 服务 | `services/tool_api/app/kpi_query.py`、`metric_registry.py` | 注册表、视图、角色、窗口和审计 |

`int_ticket_activity_daily.sql` 若已提供 `resolved_ticket_count`，学员无需为了增加代码量而重复实现。评分重点是能否把现有数据安全地放行至 Agent。

## 4. 分阶段评分细则

### 4.1 阶段一：口径与边界（12 分）

#### 满分标准

- 明确分子是 `status ∈ {resolved, closed}` 的当天工单数。
- 明确分母是同一 `activity_date` 口径下的全部工单数 `ticket_count`。
- 写明公式及 `nullif(ticket_count, 0)` 除零保护。
- 明确聚合维度，至少包含 `metric_date × product_line`；`priority`、`org_id`、`category` 可按设计选用。
- 将聚合指标敏感度说明为 `low` 并给出理由。
- 明确 Agent 视图不得出现 `customer_id`、`assignee_id` 等 PII 字段。
- 明确可查询角色，如 `support_ops`、`instructor`、`admin`。
- 明确需要人工确认的边界，例如查询窗口超过 31 天或跨组织批量导出。
- 明确 Agent 不得直查原始工单表，也不得返回工单明细。

#### 文档明确的扣分项

| 问题 | 扣分 |
|---|---:|
| 口径含糊：只写“解决数/总数”，未定义哪些状态属于“已解决” | −4 |
| 未说明 PII 等级 | −4 |

若分母误写为“当天已解决工单数”，会导致分子、分母同源，解决率恒为 1，应作为核心口径错误处理，不能按满分口径项给分。

### 4.2 阶段二：契约门禁（15 分）

#### 满分标准

- 能从 `ticket_contract.json` 指认计算所需字段：`status`、`created_at`、`resolved_at`。
- 正确识别合法状态枚举：`open`、`pending`、`in_progress`、`resolved`、`closed`、`escalated`。
- 说明 `resolved` 和 `closed` 计入已解决。
- 对“`status=resolved` 但 `resolved_at` 为空”的数据给出质量处理，例如 `quality_gate=warn`。
- 制造一条非法状态（如 `done`），实际运行契约门禁，并提交校验失败的截图或报错文本。
- 能解释契约采用 JSON Schema 2020-12，非法值由字段 `enum` 约束拦截，`additionalProperties: false` 阻止未声明字段；已有契约足够时，不强制修改契约结构。

参考验收命令：

```bash
pytest tests/contract/test_week02_gate.py -q
```

#### 文档明确的扣分项

| 问题 | 扣分 |
|---|---:|
| 仅口头声称契约可以拦截，没有运行证据 | −6 |
| 将 `done` 误判为合法枚举值 | −5 |

### 4.3 阶段三：入湖与补数（15 分）

#### 满分标准

- `seed_loader` / `ticket_ingest` 正常入湖流程可运行，并能在 `data/canonization/checkpoints/week03_ingest_state.json` 中找到采集水位。
- 能通过删除某日分区或回退水位制造缺口。
- 使用补数 dry-run 识别要补的分区，确认范围后执行补数，并证明缺口已补回。
- 能解释至少一种真实幂等机制：
  - 按 `ingest_batch_id` 与分区覆盖写，而不是重复追加；
  - `ingest_state` 记录已处理水位，重放只处理缺口；
  - `ticket_id` 主键或唯一约束防止重复落行。
- 源文档将“补数前先 dry-run、确认范围后再执行”称为隐藏加分项；其计分歧义见 4.8 节。

参考验收命令：

```bash
cat data/canonization/checkpoints/week03_ingest_state.json
pytest tests/integration/test_replay_backfill_dry_run.py -q
```

#### 文档明确的扣分项

| 问题 | 扣分 |
|---|---:|
| 仅靠全量重跑完成补数，且无法解释为何不会重复写入 | −5 |

### 4.4 阶段四：时间旅行与性能基线（13 分）

#### 满分标准

- 提交补数前、补数后的两个 `snapshot_id`。
- 分别查询两个快照并比较计数，证明缺失分区已补入且旧状态仍可追溯。
- 提交性能基线报告，至少包含：
  - `row_count`
  - `snapshot_count`
  - `file_count`
  - 平均、最小、最大文件大小
  - 最新 `snapshot_id`
  - 最新 operation
- 保留 Week 4 的自然状态，不为了“优化”而执行 compaction。

参考验收命令：

```bash
python -m pipelines.lakehouse.demo_time_travel
python -m pipelines.lakehouse.perf_baseline \
  --all-core \
  --out reports/week04/iceberg_baseline_report.md
```

#### 文档明确的扣分项

| 问题 | 扣分 |
|---|---:|
| 只生成性能基线，未做补数前后时间旅行对比 | −5 |
| 擅自执行 compaction，导致自然状态基线失真 | −3 |

### 4.5 阶段五：dbt、注册表与受控工具（30 分）

这是本作业的核心评分维度。分数拆分如下：

实现核查还应确认：

- `int_ticket_activity_daily.sql` 已按 `activity_date × product_line × priority × org_id × category` 聚合，并提供 `ticket_count` 与 `resolved_ticket_count`；仓库版本缺失时应补齐。
- `agent_tool_input_view.sql` 只暴露安全聚合字段，例如 `metric_date`、`metric_name`、`product_line`、`priority`、`org_id`、`category`、`metric_value`、`data_release_id`、`generated_at`，不得带入 PII。
- `kpi_query.py` / `metric_registry.py` 沿用“注册表校验 → 只查 `agent_tool_input_view` → 角色与窗口校验 → 审计落库”的既有路径，无需为了本指标大改服务结构。

| 子项 | 分值 | 满分标准 |
|---|---:|---|
| mart 显式放行 | 5 | 在 `support_kpi_mart.sql` 中生成 `resolution_rate` |
| safe view 显式放行 | 5 | 在 `agent_tool_input_view.sql` 的指标白名单中加入该指标 |
| registry 显式放行 | 5 | 在 `metric_registry_v1.yml` 中完整登记定义、类型、权限和测试 |
| Tool 契约显式放行 | 5 | 在 `query_support_kpis_v1.json` 的指标枚举中加入该指标 |
| 公式与数值正确 | 5 | 分子、分母正确，使用除零保护，结果位于 `[0,1]` |
| dbt 测试 | 5 | 范围、非负和 Agent 视图无 PII 的测试均通过 |
| **合计** | **30** |  |

#### 注册表最低要求

`resolution_rate` 的登记应表达以下语义，不要求字段顺序与参考答案一致：

```yaml
name: resolution_rate
label: Resolution Rate
business_name_zh: 工单解决率
description: Share of tickets resolved on the activity date.
business_definition_zh: 当天已解决工单数（status ∈ {resolved, closed}）除以当天工单总数。
owner: analytics_engineering
metric_type: ratio
formula: resolved_ticket_count / nullif(ticket_count, 0)
numerator: resolved_ticket_count
denominator: ticket_count
aggregation: avg
unit: ratio
sensitivity: low
definition_status: production
version: 1.0.0
allowed_roles: [support_ops, instructor, admin]
quality_tests: [non_negative, ratio_between_0_and_1]
```

#### 必查测试

- `ratio_metrics_between_0_and_1.sql`：指标值位于 `[0,1]`。
- `metric_values_non_negative.sql`：指标值非负。
- `no_pii_columns_in_agent_tool_input_view.sql`：Agent 视图不含 PII。

参考验收命令：

```bash
(cd analytics && dbt build)
pytest tests/integration/test_week05_metric_registry.py -q
pytest tests/integration/test_week05_kpi_query_tool.py -q
pytest tests/contract/test_week05_metric_contracts.py -q
```

#### 文档明确的扣分项

| 问题 | 扣分 |
|---|---:|
| mart、safe view、registry、Tool 契约每漏一处 | 每处 −5 |
| ratio 指标使用 `sum` 聚合 | −3 |
| 将 `customer_id` 等 PII 带入 Agent 视图 | −5 |

只在 mart 中计算出指标但工具查不到，不是工具缺陷，而是没有完成纵深白名单放行，应按缺失位置逐项扣分。

### 4.6 阶段六：端到端贯通与越权反例（10 分）

#### 分值拆分

| 子项 | 分值 | 满分标准 |
|---|---:|---|
| 端到端链路 | 7 | 源数据变化、重新入湖、Iceberg 新快照、dbt 重算、有权限查询等证据前后对应 |
| 越权反例 | 3 | 未授权角色被拒绝，并返回拒绝原因或审计证据 |

#### 标准验证链

1. 将一条源工单改为 `resolved` 并写入 `resolved_at`。
2. 重新入湖，证明重复执行不会产生重复数据。
3. 生成 Iceberg 新快照，并用时间旅行确认变化。
4. 运行 dbt，使 `resolution_rate` 随源数据变化。
5. 使用 `support_ops` 等允许角色查询，返回 `allowed=true`、指标值、freshness 和审计信息。
6. 使用 `guest` 等未授权角色查询，返回 `allowed=false` 和 `denial_code`，并留下审计。

#### 文档明确的扣分项

| 问题 | 扣分 |
|---|---:|
| 只演示有权限角色可以查询，未演示越权拒绝 | −3 |

### 4.7 文档可读性与证据可追溯性（5 分）

#### 满分标准

- 验收报告结构清晰，能沿阶段一至阶段六定位证据。
- 关键结论链接到对应代码、命令输出、测试结果、快照或审计记录。
- 报告能解释“为什么默认查不到，以及在哪四处显式放行”。
- 失败和限制如实记录，不只展示成功结果。

#### 文档明确的扣分项

| 问题 | 扣分 |
|---|---:|
| 结论没有运行证据或可追溯链接 | −3 |

### 4.8 原文提及但未量化的加分观察项

源 DOCX 两次提到可加分的高质量表现：

- 阶段三：补数前先 dry-run，展示待补分区，确认后再执行。
- 阶段五：报告能明确解释“指标默认不可查，必须在四处逐层显式放行”的设计意图。

但源 DOCX 没有给出这两项的具体加分值、额外加分上限或总分是否可超过 100。为避免自行创造分值，本指南只将其记录为高质量证据；如需额外计分，应由教师先统一补充规则。

## 5. 四处显式放行检查表

这是最容易遗漏、也是区分企业级实现与 Demo 的核心检查项。

| 放行位置 | 应观察到的证据 | 缺失影响 |
|---|---|---|
| `support_kpi_mart.sql` | 长表指标中存在 `resolution_rate`，公式正确 | mart 不产出指标 |
| `agent_tool_input_view.sql` | 指标出现在白名单中，且视图不含 PII | Agent 安全视图查不到指标 |
| `metric_registry_v1.yml` | 指标定义、类型、聚合、角色和质量测试完整 | 注册表校验不通过或治理信息缺失 |
| `query_support_kpis_v1.json` | 指标出现在 Tool 可查询枚举中 | Tool 契约拒绝请求 |

四处全部完成后，还应确认服务端沿既有受控路径执行：

```text
注册表校验
  → 只查询 agent_tool_input_view
  → 角色与时间窗口校验
  → 返回聚合指标
  → 写入审计记录
```

## 6. 证据验收指南（按原文归纳）

| 阶段 | 最低有效证据 |
|---|---|
| 口径与边界 | 验收文档中的公式、维度、PII、角色、HITL 和红线 |
| 契约门禁 | 非法 `status=done` 被 JSON Schema 拦截的实际输出 |
| 入湖与补数 | 水位状态、dry-run 缺口列表、补数结果和幂等解释 |
| 时间旅行 | 补数前后两个快照 ID、计数对比和性能基线报告 |
| dbt 与注册表 | 四处代码或配置变更、`dbt build` 和三类测试结果 |
| 端到端 | 源数据变化前后对应的快照、指标查询和审计记录 |
| 安全反例 | 允许角色成功响应与未授权角色拒绝响应 |

只有文字声称“已通过”而无原始输出时，不应按完整运行证据计分。截图可以辅助，但应能看清命令、关键输出和对应对象。

## 7. 高频错误及统一判定

### 7.1 “指标算出来了，但工具查不到”

原因通常是只完成了 mart，漏掉 safe view、registry 或 Tool 契约。按四处放行规则，每漏一处扣 5 分。

### 7.2 “解决率始终为 1”

通常是错误地用已解决工单同时作为分子和分母。正确分母是当天全部工单 `ticket_count`。

### 7.3 “比率在上层直接求和”

两个 50% 不能直接相加为 100%。应按定义重算分子/分母之比，或声明并正确处理 `avg` 聚合。使用 `sum` 扣 3 分。

### 7.4 “环境无法运行全栈”

环境受限不等于可以获得运行项满分。学员仍可通过设计、关键 diff 和验收报告进入及格档；未实际完成的时间旅行、测试或端到端证据按细则计分，并受第 9 节档位约束。

### 7.5 “只演示正常查询”

正常查询只证明功能链可用。缺少越权拒绝反例时，阶段六扣 3 分。

## 8. 核心质量检查

源 DOCX 的“一页纸批改速查”明确将以下现象判为“核心没抓住”，应回退到推荐档以下并按细则逐项扣分：

- `resolution_rate > 1` 或因口径错误长期恒等于 1。
- PII 测试失败，Agent 视图泄漏个人标识字段。
- 只计算指标，没有完成四处显式放行。

未授权角色可查询、Agent 绕过受控工具直查原始数据同样违反源文档的安全设计要求，应在对应维度扣分；但源文档没有为这两种情况另设“推荐档以下”的固定档位限制，因此不额外扩展该限制。

## 9. 交付档位与成绩解释

| 交付情况 | 档位判断 |
|---|---|
| 只有设计文档、未修改代码 | 最高不超过 70 分；仍需按细则评分，并非自动获得 70 分 |
| 设计、关键 diff、验收报告齐全，但受环境限制未跑全栈 | 可达到及格档，最高 70 分 |
| `dbt build` 通过、四处放行完整、相关测试通过 | 推荐档通常从 85 分起，再按其他维度扣分 |
| 在推荐档基础上完成端到端演示、越权拒绝、时间旅行和性能基线证据 | 具备满分档条件 |

源 DOCX 同时要求“按细则逐条扣分”，因此档位速查不能替代七个维度计分。满足推荐档或满分档特征，只代表进入相应档位的必要交付证据已经具备；若存在口径、PII 或证据缺陷，仍按细则扣分。

## 10. 备选指标 `avg_resolution_hours` 的评分差异

学员选择平均解决时长时，仅替换以下口径，其余契约、入湖、时间旅行、四处放行、权限反例及分值保持不变。

| 项目 | 正确要求 |
|---|---|
| 公式 | `avg(resolved_at - created_at)` |
| 纳入范围 | 仅统计 `resolved_at is not null` 的已解决工单 |
| 未解决工单 | 必须排除，不得将解决时长记为 0 |
| 单位 | `hours` |
| 指标类型 | `average` |
| 聚合 | `avg` |
| 注册表字段 | 不要求 `numerator`、`denominator` |
| 质量测试 | 使用 `metric_values_non_negative`，不使用 `ratio_between_0_and_1` |

若把未解决工单的时长记为 0，会人为拉低平均解决时长，应在阶段一的核心口径项扣分。

## 11. 教师评分记录表（整理模板）

### 11.1 基本信息

| 项目 | 记录 |
|---|---|
| 学员/学号 |  |
| 指标 | `resolution_rate` / `avg_resolution_hours` |
| 提交 Commit |  |
| 验收环境 |  |
| 关键报告位置 |  |

### 11.2 分数记录

| 评分维度 | 满分 | 实得分 | 证据与扣分说明 |
|---|---:|---:|---|
| 阶段一：口径与边界 | 12 |  |  |
| 阶段二：契约门禁 | 15 |  |  |
| 阶段三：入湖与补数 | 15 |  |  |
| 阶段四：时间旅行与性能基线 | 13 |  |  |
| 阶段五：dbt、注册表与受控工具 | 30 |  |  |
| 阶段六：端到端贯通与越权反例 | 10 |  |  |
| 文档可读性与证据可追溯性 | 5 |  |  |
| **总分** | **100** |  |  |

### 11.3 最终结论

- 交付档位：及格档 / 推荐档 / 满分档
- 核心优点：
- 主要扣分项：
- 必须修复项：
- 复验命令与预期结果：

## 12. 一页式批改速查（按原文重排）

- [ ] 分子是 `resolved/closed` 工单数，分母是当天全部工单数。
- [ ] 使用 `nullif(ticket_count, 0)`，指标值在 `[0,1]`。
- [ ] PII 敏感度、允许角色、HITL 和禁止直查原表均有说明。
- [ ] 非法 `status=done` 被契约门禁实际拦截。
- [ ] 入湖有水位，缺口可 dry-run 并补回，幂等机制说得清。
- [ ] 提交补数前后两个 Iceberg 快照及性能基线。
- [ ] mart、safe view、registry、Tool 契约四处均已放行。
- [ ] ratio 聚合正确，范围、非负和无 PII 测试通过。
- [ ] 有权限角色能查到指标，未授权角色被拒并有审计。
- [ ] 报告中的关键结论均能追溯到代码、命令或原始结果。

> 批改主线：本作业要检验的不是“会算一个指标”，而是“能把一个指标安全、可治理、可审计地交给 Agent 使用”。
