---
name: evaluating-omnisupport-week1-5
description: "Evaluates and re-evaluates OmniSupport Week 1–5 milestone homework against the instructor rubric. Use when grading, 评估, 复评, 验收, or writing Markdown reports about resolution_rate, contracts, replay/backfill, Iceberg time travel, dbt, metric registry, governed KPI tools, authorization, or audit evidence."
compatibility: Requires local access to the rubric and student Git repository; Docker is optional but recommended when equivalent isolated services are unavailable.
---

# Evaluating OmniSupport Week 1–5

对 OmniSupport Week 1–5 综合里程碑作业执行证据优先、修订锁定、隔离复现、可重复复评的验收。始终区分“代码具备能力”“提交材料声称通过”和“本次独立实测通过”。

## 适用边界

- 适用于主线指标 `resolution_rate`；若学员选择 `avg_resolution_hours`，使用评分指南中的替代口径。
- 适用于首次评分和同一学员的多轮重新提交。
- 以用户指定的评分指南为唯一分值来源。每次重新读取指南；本 skill 中的分值仅表示当前常见基线。
- 不把其他结课作业的 C1–C8、G1–G6 或硬门槛带入本作业。当前 Week 1–5 指南明确没有一票否决项。
- 不因命名风格、代码量、可选架构升级或未要求的 UI 扣分。

## 当前评分基线

读取指南后核对下表；若指南已变化，以指南原文为准：

| 维度 | 分值 |
|---|---:|
| 阶段一：口径与边界 | 12 |
| 阶段二：契约门禁 | 15 |
| 阶段三：入湖与补数 | 15 |
| 阶段四：时间旅行与性能基线 | 13 |
| 阶段五：dbt、注册表与受控工具 | 30 |
| 阶段六：端到端贯通与越权反例 | 10 |
| 文档可读性与证据可追溯性 | 5 |
| **合计** | **100** |

默认成绩映射：90–100 为 `优秀`，60–89 为 `良好`，低于 60 为 `不及格`。交付档位 `及格档/推荐档/满分档` 与数字分、作业等级分别记录，不能互相替代。

## 证据分级

所有结论标明以下证据状态之一：

1. **独立实测**：本次在锁定修订和隔离环境运行所得。
2. **提交原始证据**：Git 跟踪的 JSON、SQL 输出、快照报告、审计记录或测试日志。
3. **静态实现证据**：代码、契约、SQL、YAML 和调用路径支持，但本次未运行。
4. **学员文字声明**：仅验收报告声称，不能单独证明运行结果。
5. **未验证**：环境或资源不足；不能写成失败，也不能按实测通过计分。

主动寻找反证。若验收报告、artifact、实现和独立输出不一致，以直接、可重放的证据优先，并在文档维度记录不一致。

## 完整评分指南

- 本 skill 将评分指南全文收录在 [references/week1-5-grading-guide.md](references/week1-5-grading-guide.md)，包括第 1–12 节、全部满分标准、固定扣分项、参考命令、未量化观察项、四处放行、证据表、核心质量检查、交付档位、`avg_resolution_hours` 替代口径、评分记录表和一页式速查。
- 每次评分必须完整读取 bundled guide，不能只依赖 `SKILL.md` 中的执行摘要。
- 仓库存在用户指定或课程最新指南时，也完整读取该文件。当前项目规范位置为 [homework-guide/里程碑作业·Week1-5综合_评分指南.md](../../../homework-guide/里程碑作业·Week1-5综合_评分指南.md)。若它与 bundled guide 不一致，以用户指定或仓库最新指南为唯一分值来源，并在报告中记录差异；不要混用两个版本的分值或扣分项。

## 工作流

### 1. 读取规则并冻结口径

完整读取用户指定的评分指南，提取：

- 七个维度和总分。
- 每阶段满分标准、固定扣分项和参考命令。
- 四处显式放行要求。
- 交付档位、成绩映射和必需报告结构。
- 是否存在硬门槛；没有时明确记录“无硬门槛”。
- `resolution_rate` 或备选指标的分子、分母、除零、维度和聚合语义。

不要用本 skill 的摘要替代当次指南原文。

### 2. 锁定本次提交

规范化路径并记录来源状态：

```bash
realpath <student-repo>
git -C <student-repo> status --short --branch -uall
git -C <student-repo> branch --show-current
git -C <student-repo> rev-parse HEAD
git -C <student-repo> rev-parse @{upstream}
git -C <student-repo> log -5 --oneline --decorate
```

- 报告写出分支、完整 SHA、本地与 upstream 是否同步、工作树是否干净。
- 工作树有未提交修改时，区分“已提交修订”和“未提交内容”；除非用户明确要求，不把未提交内容计入锁定提交。
- 复评时从上一份报告读取上次 SHA 和分数，再检查：

```bash
git -C <student-repo> diff --stat <previous-sha>..<current-sha>
git -C <student-repo> log --oneline <previous-sha>..<current-sha>
```

- 只复核变化会影响的旧结论，同时重新跑核心回归，不能只看 diff 就给分。

### 3. 保持学员仓库只读

- 静态读取可在学员仓库进行；所有可能写缓存、报告、数据库或 root-owned 文件的命令在 detached worktree 运行。
- 不修改、暂存、还原或清理学员文件；发现无关改动时记录但继续任务。
- 先盘点现有容器、网络和服务，不停止或复用学员正在运行的实例。
- 使用唯一的短 SHA 作为临时资源后缀：

```bash
SOURCE=<student-repo>
REV=<assessed-sha>
SHORT=$(git -C "$SOURCE" rev-parse --short "$REV")
TMP_ROOT="/tmp/omni-regrade-$SHORT"
git -C "$SOURCE" worktree add --detach "$TMP_ROOT/worktree" "$REV"
```

- 所有 state、report 和测试输出显式写到 `$TMP_ROOT`，避免 CLI 默认路径覆盖提交 artifact。
- 不要假设顶层 `--report-json` 会传入嵌套调用；某些 recovery CLI 会用 `report_path=None` 调用 ingest，仍把默认报告写进 detached worktree。运行前后检查 detached worktree 状态，把这种写入限制在临时 worktree，绝不还原或清理学员主工作树。

### 4. 建立七阶段证据矩阵

#### 阶段一：口径与边界

核对：

- 分子为 `status ∈ {resolved, closed}` 的工单数。
- 分母为同一 `activity_date` 粒度的全部工单数。
- 使用 `nullif(ticket_count, 0)`，结果位于 `[0,1]`。
- 至少包含 `metric_date × product_line` 维度。
- 聚合指标敏感度为 `low` 且理由合理。
- Agent 视图无 `customer_id`、`assignee_id` 等 PII。
- 允许角色、HITL 边界、禁止直查原表和禁止返回明细均明确。

#### 阶段二：契约门禁

核对 `status`、`created_at`、`resolved_at`，合法枚举及 JSON Schema 约束。必须验证：

- 非法 `status=done` 被实际拒绝。
- `resolved/closed + resolved_at=null` 有明确质量处理，如 `quality_gate=warn`。
- 测试覆盖两个终态，且测试代码签名与实际实现一致。

不要只读 JSON Schema；终态时间规则通常属于业务质量层。

#### 阶段三：入湖与补数

追踪同一条证据链：

```text
source_id → fixture 时间 → start/end cursor → checkpoint
          → dry-run → 首次执行 → 二次回放 → 数据库计数
```

检查：

- `start_cursor/end_cursor` 是否真正传入 ingest 并过滤记录，而非只出现在计划文本。
- dry-run 是否真的执行。对某些 CLI，正确用法可能是 `--execute --dry-run`；必须检查输出中的 `dry_run` 和 `execution_result`，不能相信命令注释。
- dry-run 是否零写入、零 checkpoint 推进，并能展示候选范围。
- 首次执行有 `inserted > 0`，二次执行有 `inserted=0` 和 duplicates/skipped。
- Bronze 指纹/唯一键、Silver upsert、checkpoint 三种幂等证据是否一致。
- 文档称 `[start,end)` 时，实现必须排除 `cursor == end`；检查 `>` 与 `>=` 并寻找边界测试。

#### 阶段四：时间旅行与性能基线

检查：

- 两个明确的 snapshot ID。
- 使用同一过滤条件查询补数前后 row count，并计算 delta。
- 旧快照仍保持旧计数，新快照含补回数据。
- 基线包含 row/snapshot/file count、avg/min/max file size、latest snapshot ID 和 operation。
- 未为了展示效果执行 compaction。

仅有性能基线不等于完成时间旅行。若本次没有独立启动 Iceberg/MinIO，明确写“提交证据复核”，不要伪装成独立实测。

#### 阶段五：dbt、注册表与受控工具

逐一验证四处显式放行：

1. `support_kpi_mart.sql`
2. `agent_tool_input_view.sql`
3. `metric_registry_v1.yml`
4. `query_support_kpis_v1.json`

再检查：

- intermediate 同时提供 `ticket_count` 和 `resolved_ticket_count`。
- mart 公式使用正确分子、分母和除零保护。
- registry 的 `formula` 也应表达 `nullif(ticket_count, 0)` 除零语义；不能因为 mart 可执行公式正确就忽略治理元数据不一致。
- ratio registry aggregation 不是 `sum`。
- safe view 不含 PII。
- Tool 只查询 safe view，使用参数化 SQL，并执行 registry、角色、窗口校验。
- 范围、非负、无 PII 的 dbt 测试通过。

独立数值夹具至少包含同粒度的 `resolved`、`closed`、`open` 各一条。预期：

```text
resolved_ticket_count=2
ticket_count=3
resolution_rate≈0.6667
```

这能同时发现遗漏 `closed` 和错误分母。

#### 阶段六：端到端与越权

完整链应使用同一组数据和可关联的 run/trace：

```text
源数据变化 → 入湖/补数 → Iceberg 新快照 → dbt 重算
           → 授权查询 → 未授权拒绝 → audit_log
```

至少独立运行：

- 允许角色查询 `resolution_rate`，检查返回值、freshness 和 `audit_id`。
- 未授权角色查询，检查 `allowed=false` 和 `ROLE_DENIED`。
- 未注册指标查询，检查 `METRIC_DENIED`。
- 每次调用前后查询 `audit_log` 计数，并用响应 `audit_id` 回查数据库。

测试中的 fake connection 只能证明调用意图，不能替代真实数据库持久化。阅读审计异常处理：若 INSERT 异常被吞掉，则健康路径可通过，但不能宣称严格 fail-closed 或“无审计调用不可能发生”。

#### 文档与追溯

逐项交叉检查报告中的：

- 命令是否真的产生其注释所称行为。
- 测试数量和耗时是否与当前精确命令一致。
- 嵌入代码是否与仓库签名、返回值和日志文本一致。
- snapshot、source、fixture、release、audit ID 是否来自同一条链。
- “全部通过”“工业级”“不可篡改”等结论是否超出实现保证。

报告清晰但关键运行结论失真时，按指南的证据追溯项扣分；功能层和文档层若是两个不同缺陷，可以分别扣，但不要对同一缺陷重复惩罚。

### 5. 独立运行时验证

按风险从小到大执行，先定向测试，再构建全环境：

1. 精确契约和集成测试。
2. 干净 Docker image 构建。
3. 独立 PostgreSQL，应用全部 migration。
4. Week 3 dry-run/首次/二次回放。
5. 合法三状态 fixture 下的 `dbt build` 和数值查询。
6. KPI 成功、角色拒绝、指标拒绝及真实审计。
7. 需要且资源允许时，再启动独立 MinIO/Iceberg 复现时间旅行。

资源命名必须唯一，例如：

```text
omni-regrade-<shortsha>-net
omni-regrade-<shortsha>-pg
omni-regrade:<shortsha>
```

验证 Docker 构建时注意跨文件依赖约束，例如 `pyproject.toml` 与 service requirements 的同一包版本冲突。构建成功只证明环境可安装，不替代功能测试。

若命令失败：记录第一因果错误，判断是学生代码、提交依赖还是评估环境问题；修正评估参数错误后重跑，不把评估者使用错误 IP、端口或 DSN 计为学生失败。

#### Docker 与等价隔离

- Docker 不是评分指南的硬门槛，也不因“使用 Docker”本身加分。它只是隔离 PostgreSQL、MinIO/Iceberg、dbt 和依赖安装的默认手段。
- Docker 不可用、资源不足或用户明确要求不运行时，可使用等价的临时虚拟环境、独立数据库和对象存储。证据强度按实际隔离与可重放程度判断。
- 无法等价复现的环节写“未验证”，不能写成失败，也不能按独立实测通过；再依评分指南的运行证据与交付档位规则计分。
- 不复用或停止评估开始前已存在的容器。独立资源必须使用短 SHA 后缀，并在结束时只删除本次创建的资源。

#### 环境与执行故障处理

| 现象 | 判断方法 | 处理方式 |
|---|---|---|
| `rg: command not found` | `command -v rg` | 用 `find`、`grep` 继续，不因此中断或影响评分。评估任务本身不授权安装系统包；只有用户明确要求时才安装 `ripgrep`。 |
| PostgreSQL 启动后短暂 `rejecting connections` 或目标数据库不存在 | 查看独立容器日志并对指定用户、数据库执行 `pg_isready` | 这通常是 entrypoint 正在初始化/创建数据库。轮询到目标数据库真正 ready，不用固定 sleep，也不计为学员失败。 |
| 主机有 `python3` 但没有 `python` | 分别执行 `command -v python3`、`command -v python` | 主机侧只读汇总优先用 `python3`；学员测试仍使用锁定镜像或隔离虚拟环境中的解释器，不依赖未跟踪的学员 `.venv`。 |
| 复合命令最后的汇总步骤失败，但前面的写入/测试已经完成 | 检查退出位置、已生成 JSON、数据库计数和容器日志 | 不重跑整个非幂等链。保留已完成结果，只重做失败的只读汇总或从第一个未完成步骤继续。 |
| recovery 命令指定了外层报告路径，detached worktree 仍出现 tracked report 修改 | `git -C "$TMP_ROOT/worktree" status --short -uall` | 这是嵌套 ingest 使用默认报告路径的副作用。确认学员主工作树未变，保留临时修改供核查，最后用 `git worktree remove --force` 删除 detached worktree。 |
| Docker build 大量步骤显示 `CACHED` | 阅读 build 输出并记录缓存状态 | 缓存构建仍可证明当前 context 可产出镜像，但不要声称依赖被全新下载；只有排查依赖解析问题时才考虑 `--no-cache`。 |

失败后的处理原则：先解释现象，再确认已发生的状态变化，最后选择最小续跑步骤。不要因评估脚本、主机命令名、就绪时序或后处理错误给学员扣分。

### 6. 评分

- 先按七个维度独立给分，再求和；算术总分必须等于分项之和。
- 优先执行指南中的固定扣分项；没有量化的观察项不自行创造额外分值。
- 没有运行证据时，不能给运行项满分；环境阻塞则写未验证并按指南处理。
- 四处显式放行每缺一处，按指南逐处扣分。
- Stage 6 的 7 分链路和 3 分越权反例分开判断。
- 最后依据实际交付特征给出 `及格档/推荐档/满分档`，再依据总分给出 `优秀/良好/不及格`。
- 复评报告写出上次分数、当前分数和变化量，并只把新提交实际修复的内容列为改进。

### 7. 生成并保存报告

需要完整报告时读取 [references/report-template.md](references/report-template.md)。报告至少包含：

- 锁定修订与仓库状态。
- 分项评分和总分。
- 相比上次提交的有效改进。
- 独立复验命令与关键结果。
- 证据不一致及剩余限制。
- 四段式结论：`作业等级/作业优点/作业不足/改进方向`。

用户要求保存到目录时：

- 使用绝对路径。
- 不覆盖旧报告。
- 首次评分可用 `...-evaluation.md`；复评优先用 `...-reevaluation-<shortsha>.md`。
- 若目标名已存在，再加入时间戳或递增后缀。
- 写入后重新读取，验证四段式标题存在、总分算术正确、文件非空。
- 最终回复给出完整路径和简短结论。

### 8. 清理与最终确认

只清理本次创建的资源：临时容器、网络、image、volume、worktree 和 `$TMP_ROOT`。不得停止或修改评估开始前已存在的服务。detached worktree 即使被默认报告写脏，也只用 `git worktree remove --force` 删除，不在学员主工作树执行 restore/reset/clean。

结束前确认：

- 学员工作树状态与开始时一致。
- 学员 HEAD 和 upstream 未被评估过程改变。
- 旧评分报告仍存在且时间戳未变化。
- 新报告位于用户要求的目录。
- 独立资源全部删除；原有容器仍处于原状态。
- 每个给分和扣分结论都能回指直接证据或指南条款。
- 报告没有把提交材料写成独立实测，也没有把未验证写成失败。

## 高频误判

- 把 recovery plan 当作 dry-run：检查 `dry_run` 和 `execution_result`。
- 看到 cursor 参数就认为已过滤：追到 ingest 调用和每条记录的 predicate。
- 把 `>` 写成 `[start,end)`：边界语义实际不同。
- 只看二次 `skipped` 就认为完成缺口补回：还需首次 inserted 和补后计数。
- 只看 snapshot ID 就认为完成时间旅行：还需同条件 row-count 对比。
- 只在 mart 找到指标就认为 Tool 可查：必须核对四处放行。
- 用全为 resolved 的数据验证比率：无法发现分母错误；必须加入 open。
- 用 mocked audit 测试证明持久化：必须查真实 `audit_log`。
- 把 audit best-effort 写成 fail-closed：检查异常是否被吞掉。
- 相信报告中的测试数量：对相同文件执行精确命令。
- 在学员主工作树运行会写默认报告的 CLI：始终使用 detached worktree 和 `/tmp` 输出。
