---
name: evaluating-omnisupport-capstones
description: "Evaluates OmniSupport AI data engineering capstone submissions against the student assignment and instructor rubric. Use whenever grading, 验收, 复核, or drafting reports about C1–C8, G1–G6, Docker/Devbox reproducibility, RAG evidence, tenant isolation, HITL, evaluation, traces, releases, or homework strengths and weaknesses."
compatibility: Requires local access to the assignment guides and student Git repository; Docker and Docker Compose are needed for full runtime verification.
---

# Evaluating OmniSupport Capstones

对 OmniSupport 结课作业执行证据优先、可复现、可复核的验收。先判断硬门槛，再计算基础分和加分；把“提交材料声称通过”与“本次实际复现通过”明确分开。

## 适用边界

- 适用于 OmniSupport AI 数据工程结课作业、问题处理方案卡、C1–C8、G1–G6 和 D1–D8 验收。
- 以用户指定的学员任务书和教师评分指南为准。每次都重新读取，不把本 skill 中的示例当成不可变规则。
- C1–C8 是公开的统一验收用例，不是隐藏测试。学员针对这些用例设计功能和 Golden Set 是正常行为。
- 不因可选 UI、可选录屏、真实模型或其他非必需能力缺失而扣基础分。先从实际任务书确认它是否可选。
- 不要求提交包含密钥的 `.env.local`。正确判断是：仓库能否从 `.env.example` 和 README 重建可运行配置。

## 核心判定原则

1. **直接证据优先**：代码、SQL、Manifest、原始 JSON、测试输出、Trace 和 Release 记录优于总结性 Markdown。
2. **主动查找反证**：发现疑似缺陷后，检查后续 migration、其他调用路径和测试，避免只读一个文件就下结论。
3. **区分三种状态**：
   - `实测通过/失败`：本次在受控环境运行得到。
   - `材料显示通过/失败`：仅提交报告或历史 JSON 支持。
   - `未验证`：环境、权限或资源不足，不能等同失败。
4. **每个观点都有证据链**：作业优点、作业不足、改进方向、Gate、C/D 状态、分项得分和最终等级都必须能回指代码、SQL、Manifest、原始 JSON、测试输出、Trace、Release 或任务书规则。统一写成：观点 → 观察事实 → 文件/命令证据 → 对应规则或影响。不能只为负面观点举证，也不能用总结性 Markdown 单独证明其自身结论。
5. **改进建议必须对应已证实不足**：不要添加与本作业无关的架构升级。
6. **真实性和质量分开**：真实检索可以相关性差；明确标注的 synthetic evaluator 可以是单测，但不能证明真实 RAG 质量。
7. **不以固定输出冒充复现**：Trace ID、时间戳和模型措辞不要求逐字相同；状态、契约、证据来源和控制行为必须同口径复现。

## 工作流

### 1. 读取规则并冻结本次口径

先完整读取用户指定的两类文件：

- 学员任务书：确认必做/可选、C1–C8、环境约定、提交物和演示要求。
- 教师评分指南：确认 G1–G6、红线、七项基础分、加分项和成绩映射。

建立本次规则摘录，至少记录：

- G1–G6 的原文和硬门槛后果。
- C1–C8 的输入、预期行为和核心证据。
- D1–D8 是否必交；录屏、UI、真实模型是否可选。
- 用户额外指定的等级、字数和输出格式。

如果两份文件冲突，指出冲突并按用户明确指定的优先级执行；不要静默选择更严或更松的规则。

### 2. 定位学生仓库和评估修订

输入路径可能重复拼接或包含 `~`。先规范化并验证：

```bash
realpath <candidate-path>
git -C <student-repo> rev-parse --show-toplevel
git -C <student-repo> status --short --branch -uall
git -C <student-repo> branch --show-current
git -C <student-repo> rev-parse HEAD
```

若原路径不存在，仅在父目录中查找唯一匹配项；有多个候选时询问用户。报告中写明最终使用的绝对路径。

从作业 README 提取：学员、主题、Baseline、Candidate、Provider/Model、Generation Mode、Release ID 和代表性 Trace ID。验证：

```bash
git -C <student-repo> cat-file -e <baseline>^{commit}
git -C <student-repo> cat-file -e <candidate>^{commit}
git -C <student-repo> merge-base --is-ancestor <candidate> HEAD
git -C <student-repo> log --oneline <candidate>..HEAD
```

不要静默用 HEAD 代替声明的 Candidate。Candidate 与 HEAD 不同时，说明差异并明确本次实际测试的修订。若 HEAD 仅修改提交元数据，也仍记录绑定不一致。

### 3. 保持学生仓库只读

- 不在学生主工作树中运行会生成 `.env.local`、缓存、root-owned artifacts 或报告的命令。
- 静态读取可以直接在学生仓库执行；运行时验证使用 detached 临时 worktree。
- 不修改、暂存、还原或清理学生已有文件。
- 发现原工作树不干净时继续只读评估，并记录状态；不要替用户复原。

推荐隔离方式：

```bash
SOURCE=<student-repo>
REV=<assessed-revision>
TMP_ROOT=$(mktemp -d /tmp/omni-grade.XXXXXX)
git -C "$SOURCE" worktree add --detach "$TMP_ROOT/worktree" "$REV"
```

### 4. 静态证据审计

#### 数据、Manifest 与幂等

- 检查至少两份合成文档、Manifest、Schema、PII/license/version 字段和失败输入。
- Schema 校验通过不代表资产完整。对本地资产逐个比较 `size_bytes` 和 `checksum_sha256`：

```bash
stat -c '%s %n' <asset>
sha256sum <asset>
```

- 若 `on_missing_checksum=reject`，但资产缺 checksum，记录策略与数据自相矛盾。
- 核对二次运行的 inserted/skipped/upsert 计数，不能只读“幂等通过”的文字结论。

#### RAG、证据和租户

- 从 Product API 跟到 RAG 路由、检索函数、SQL 和 Evidence 表。
- `tenant_id` 出现在请求、Debug、Audit 或 Trace 中，不等于检索已隔离。必须找到传参、SQL predicate/RLS 和租户归属字段。
- 搜索所有 migration，确认没有后续补丁推翻初步结论。
- 抽查真实 citation：问题、步骤、quote、source、排序和置信度是否一致。
- 低相关性属于质量问题；手写或伪装 citation 才属于真实性问题。

#### Skill、Tool 与副作用

- 低风险动作：检查是否存在清晰的显式确认交互和独立提交。
- 高风险动作：检查角色、租户、Evidence、幂等、HITL wait/resume 和审计是否由服务端代码保证。
- 不额外要求任务书没有规定的 `confirmed=true` 字段。显式 UI 确认后发起认证 POST，可以构成确认，前提是没有自主 Agent 路径绕过它。
- 前端提示不能代替服务端授权；Prompt 不能代替代码策略。

#### 评测和真实性

- 检查 Golden Set 是否真实覆盖 C1–C8 的语义，而不只是 case 名称。
- 特别验证：C4 必须确有证据不足/冲突；C8 必须包含原 E2E 和真实回滚验证，不能用任意 smoke 冒充。
- 阅读 evaluator 源码。若它从 `expected_answer`、`expected_keywords` 或 `expected_citation_ids` 构造被评测输出，则仅算 policy/unit test。
- synthetic evaluator 明确标注且未进入生产回答时，不自动判 G2 失败；但其通过率不能计为真实检索或模型质量。
- 基线和候选必须同数据、同参数、同评分口径，并保留原始逐案例结果和失败分布。

#### Trace、Release、成本与报告

- 检查响应是否含 `release_id`、`trace_id`，Trace 是否能定位 Rewrite/Retrieve/Generate/Action/HITL 关键 Span。
- 检查 Trace 默认内容策略，不用“有 hash 字段”推断所有敏感原文都已关闭。
- Release 必须绑定实际 Git SHA 以及 Data/Index/Prompt/Skill/Service 版本。全零 SHA、未解释的版本名或只切换指针都属于绑定证据不足。
- 按任务书检查 p50/p95、生成/降级比、Token 或代理成本指标。单条 latency 不等于分位数报告。
- 对照教师指南逐项核验报告中的 G1–G6 含义；学员不得自行重新定义硬门槛。

### 5. 干净环境验证

在临时 worktree 中按 README 执行，不依赖学生私人环境：

```bash
cd <temporary-worktree>
cp infra/env/.env.example infra/env/.env.local
docker compose --env-file infra/env/.env.local -f infra/docker-compose.yml up -d --build
docker compose --profile capstone --env-file infra/env/.env.local \
  -f infra/docker-compose.yml run --rm capstone_bootstrap
docker compose --profile tools --env-file infra/env/.env.local \
  -f infra/docker-compose.yml run --rm devbox \
  pytest <student-contract-tests> -q
docker compose --profile tools --env-file infra/env/.env.local \
  -f infra/docker-compose.yml run --rm devbox \
  python -m scripts.capstone.verify_e2e
```

执行前：

- 查看 README 的准确命令，不盲目套用上述示例。
- 使用独立 Compose project name、容器、网络和 volumes。
- 检查固定 `container_name` 和端口冲突。不得停止无关服务；仅用临时 override 改宿主机端口或换隔离 runner。
- 端口占用、Docker 不可用等环境问题是阻塞或未验证，不是学生代码失败。

执行时记录：

- 镜像构建是否成功。
- Bootstrap 首次与二次运行结果。
- 学生新增测试和原测试结果。
- 官方 E2E 的顶层状态和准确错误。
- 每个失败的第一因果错误，不要只报告后续连锁降级。

如果只运行宿主机测试，使用 `PYTHONDONTWRITEBYTECODE=1`、禁用 pytest cache，并明确它不能替代 G1 Docker/Devbox 验证。

### 6. G1–G6 判定

始终引用当次教师指南原文。默认语义如下；指南变化时以指南为准：

| Gate | 通过所需证据 |
|---|---|
| G1 可运行 | 从仓库根目录按 README 在干净 Docker/Devbox 重跑，不依赖私人 venv 或未声明状态。 |
| G2 无伪证据 | 生产回答 citation 来自实际检索结果，不把手写 ID/URL 冒充检索证据。 |
| G3 租户与隐私 | Case 和 Evidence 不跨租户；Trace 默认不记录客户原文、密钥和 PII。两部分都满足才通过。 |
| G4 无失控副作用 | 高风险动作不可自动执行；权限、审批、幂等由代码或契约保证。 |
| G5 可回归 | 新增测试通过，原 `scripts.capstone.verify_e2e` 仍通过。 |
| G6 可追溯 | 响应有 Release/Trace ID，报告可从请求定位关键 Span 和版本。 |

判定格式统一使用：`通过`、`失败` 或 `未验证`；必要时加“有保留”，但不能用保留掩盖明确失败。

应用硬门槛时按指南计算。常见规则是：

- G2、G3 或 G4 失败：未通过，修复后复验。
- G1、G5 或 G6 失败：数字总分封顶 59。
- 加分不能抵消硬门槛。

### 7. C1–C8 真实性抽查

- C1：抽 citation 原文，确认支持诊断和步骤。
- C2：替换错误码/版本做随机变体，确认 rewrite、FTS 和回答仍保留标识。
- C3：使用不同措辞的含糊问题，确认澄清或安全拒答。
- C4：制造真实无答案或两文档冲突，确认空 citation/冲突标记和 abstain。
- C5：显式确认后执行低风险动作，复用同一 key 验证不双写。
- C6：普通角色不得审批；管理员批准后才 resume。
- C7：实际关闭模型、超时或非法 JSON，确认降级原因且不返回 500。
- C8：运行原 E2E，切回旧 Release，再验证指针、资产版本和能力行为。

不要只重放学员已经写死的原始问题；至少对关键案例做一个保持意图不变的随机变体。

### 8. 评分和报告

先给七项基础分，再给可选加分，最后应用硬门槛。不得先把总分压到 59 再倒推各维度。

每项得分都写明给分事实和直接证据；每项失分还要写明与标准的差距。通过的 Gate、C/D 状态、优点和加分同样需要证据，不能仅以“未发现失败”推定通过。未实现非必需 UI、GraphRAG、多模态或云部署不得扣基础分。

需要模板时读取 [references/report-template.md](references/report-template.md)。可以先给完整教师报告，但每次评估最终都必须给出以下四段式作业报告；用户没有要求完整报告时，直接输出这四段：

```markdown
作业等级：<优秀/良好/不及格>

作业优点：<1000 字以内>

作业不足：<1000 字以内>

改进方向：<1000 字以内>
```

四段式报告必须满足：

- `作业等级` 只能是 `优秀`、`良好`、`不及格`。若用户未给额外映射，默认将硬门槛调整后的 90–100 映射为 `优秀`，60–89 映射为 `良好`，低于 60、`需补交` 或 G2/G3/G4 导致的 `未通过` 映射为 `不及格`。
- `作业优点`、`作业不足`、`改进方向` 各自的可见正文不超过 1000 字；不能为了限字删除观点的最小充分依据。
- `作业优点`、`作业不足`、`改进方向` 各自优先列出 3–5 个独立要点。证据不足时不得为了凑数拆分同一观点或编造新观点，可以少于 3 个并说明证据范围。
- 优点按“正面观点 → 实现或实测事实 → 文件/命令证据 → 对应规则”写；不能仅复述学员总结。
- 不足按“观察事实 → 直接证据 → 对应规则或影响”写。定稿前逐条搜索反证，包括后续 migration、其他调用路径、已有测试和继承资产；发现能力存在但缺少学员个人证据时，写“未提交/未验证”，不能写“系统没有/未实现”。
- 改进方向必须与一个已证实不足一一对应，说明最小修复、依据和可判定的复验标准。可选能力不得写成必修；仅在某能力实际进入主链时使用条件式要求。
- 把复合句拆成可独立核验的原子观点。每个观点至少附一个具体文件行、原始 JSON、测试/查询结果、Trace、Release 记录或任务书条款；“未找到”类结论必须写清检查范围。

硬门槛失败时不要用“参考分较高”包装成通过；可以在完整教师报告中单独列“门槛前参考分”，但四段式报告中的等级必须应用硬门槛后的结论。

## 避免误判清单

- 不因 `.env.local` 未提交而判失败；先验证 `.env.example`、README 和 fallback。
- 不因学员知道 C1–C8 而怀疑作弊；它们是公开规则。
- 不因 synthetic evaluator 存在就自动判伪证据；先判断它是否被冒充为生产检索质量。
- 不因 Release ID 不同就判错；先区分 baseline、candidate 和 rollback，再检查绑定是否真实一致。
- 不因没有录屏或 UI 扣分，除非本次任务书明确必交。
- 不因端口占用、无 Docker 权限或机器资源不足判 G1 失败。
- 不用 Debug 的 `filters_applied` 代替 SQL/代码隔离证据。
- 不用提交的 `status=pass` 代替本次干净复现。
- 不把后续 E2E 降级当第一根因；先报告最早的 Bootstrap/依赖错误。

## 清理和最终自检

只清理本次创建的临时资源：

```bash
docker compose -p <grading-project> ... down -v --remove-orphans
git -C <student-repo> worktree remove --force <temporary-worktree>
```

若容器生成 root-owned 文件，使用一次性容器只对已确认的临时目录执行 `chown`，再删除；不要对学生仓库执行递归权限修改。

结束前确认：

- 学生仓库 `git status` 与开始时一致。
- 临时 worktree、override、报告、容器、网络和 volumes 已删除。
- 未停止或修改无关服务。
- 每个观点至少有一个可核验依据；优点、通过项和给分项不能只靠学员自述，失败项不能只靠推断。
- 每个 Gate、C/D 状态、分项得分和最终等级都能回指直接证据与对应规则。
- 每个改进方向都能回指一个已证实不足，并给出可验证的完成标准。
- 已逐条复核“作业不足”和“改进方向”：检查反证、删除过度推断、区分“能力不存在”与“学员未提交证据”，并确认每个原子观点都有依据。
- 最终包含四段式作业报告，等级只使用 `优秀/良好/不及格`，三个正文段落分别不超过 1000 字，并在证据充分时各列 3–5 个独立要点。
- 报告没有把“未验证”写成“失败”，也没有把“材料声称”写成“本次实测”。
