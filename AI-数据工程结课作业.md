# AI 数据工程结课作业

# 前言：你到底要完成什么

**一句话任务｜**在现有 OmniSupport 上选择一个客服主题，新增一个小型知识包，并实现一张“问题处理方案卡”：它能基于证据给出诊断和步骤；证据不足时会澄清或拒答；需要动作时会经过权限、幂等和人工审批；最后用评测、Trace 和发布回滚证明它可上线。

| **项目边界** | **统一要求** |
|-|-|
| 必须复用 | 现有   Docker/Devbox、数据契约、RAG、Skill/Tool、评测、Phoenix、Release 主链 |
| 最小新增 | 2 份小文档 + 1   份 manifest + 1 个结构化产品能力 + 6–8 条 Golden Set |
| 不要求 | 重做整套前端、训练模型、新建向量库、上云、压测到生产规模、完整重做   GraphRAG |
| 最终证明 | 能跑、能解释、能复现、能拒答、能控制副作用、能看到   trace、能回滚 |

## 完成后你应能回答的六个问题

1. 这个能力解决了谁的什么问题，为什么不是普通聊天框？
2. 数据从哪里来，经过哪些契约、幂等和版本控制才变成可检索证据？
3. Query 改写、Hybrid RAG、引用和拒答各自解决什么失败？
4. 为什么某些动作可以执行，某些动作必须进入 HITL？
5. 你用什么 Golden Set、指标和 Trace 证明改动有效且没有破坏旧能力？
6. 发生错误时，数据、索引、Prompt、Skill 和服务怎样作为一个 Release 回滚？

# 01  为什么这样设计

从课程知识点回到一条真实的产品工程主线

课程从数据契约、采集、湖仓、建模和编排出发，逐步进入非结构化数据、RAG、Skills、受控 Agent、评测、可观测、GraphRAG、治理发布与上线收官。毕业作业不能把这些周次拆成十五道互不相关的小题，而应让学员沿一次用户请求看见所有关键控制点。

## 设计目标

| **目标** | **作业中的体现** | **避免的误区** |
|-|-|-|
| 好入手 | 基于当前   Capstone 扩展一个主题；提供固定命令、结构和验收用例 | 从零搭平台或陷入环境安装 |
| 能综合 | 一条请求贯穿数据→检索→生成→动作→评测→追踪→发布 | 按周堆砌截图 |
| 能区分能力 | 安全、证据、失败处理和回归是硬门槛 | 只凭回答看起来不错 |
| 能启发思考 | 要求解释边界、取舍、生产差距和下一步 | 把框架名背一遍 |

## 课程能力如何被一次作业覆盖

| **课程阶段** | **作业证据** | **验收要点** |
|-|-|-|
| Week01–03 基础与采集 | 环境、manifest、数据契约、幂等重跑 | 输入受控；重复运行不翻倍 |
| Week04–06 数据底座 | 原始对象、版本、建模或资产链证据 | 数据可追溯；流程可重放 |
| Week07–08 非结构化与   RAG | 解析、chunk、evidence、Hybrid   RAG、Query 改写 | 精确标识不丢；有引用或拒答 |
| Week09–10 Skills 与 Agent | 能力契约、工具白名单、幂等、HITL | 模型不能绕过代码策略 |
| Week11–12 评测与可观测 | Golden Set、回归报告、Phoenix   Trace | 结论可量化；坏案例可定位 |
| Week13–15 图谱、治理与收官 | 可选   GraphRAG；Release 绑定、回滚、成本性能 | 版本一致；知道本地与生产差距 |

 

**生产安全基线｜**影响权限、财务、账户和外部系统的动作必须最小权限、确定性授权并保留人工复核。这个要求与 NIST AI RMF 的全生命周期风险治理、OWASP 对 Excessive Agency 的最小功能/权限/自主性建议一致。

# 02  作业题目与业务场景

把“问得出来”升级为“处理得正确、可控、可追责”

## 统一业务背景

Northstar 客服团队已经使用 OmniSupport Copilot 查看工单、检索证据、执行内部备注和提交服务补偿审批。现在团队希望新增一项“问题处理方案卡”能力：坐席输入问题后，系统不仅回答，还要给出结构化诊断、按顺序排列的处理步骤、引用证据、置信度、下一步动作建议，以及是否需要审批。

## 四选一主题

| **主题** | **适合写入知识包的内容** | **可设计的边界案例** |
|-|-|-|
| A.   Workspace 账户恢复 | 身份校验、恢复步骤、管理员边界 | 安全问题必须澄清或转人工 |
| B. Webhook   错误排查 | HTTP   404/401、签名密钥轮换、重试 | 错误码和版本号必须保留 |
| C. Edge   Gateway TLS | 证书链、型号、固件版本、回滚步骤 | 型号/版本不一致时不能猜 |
| D. Studio 作业恢复 | 失败代码、checkpoint、重放与数据一致性 | 重复执行必须幂等 |

**推荐选择｜**第一次做建议选 B：Webhook 错误排查。当前 Capstone 已有 workspace-api-webhook 证据和可运行基线，新增两份补充文档即可形成清晰的正常、歧义、精确标识和高风险动作案例。

## 必须实现的输出契约

{

  "summary": "一句话诊断，不编造未证实原因",

  "steps": ["步骤1", "步骤2", "步骤3"],

  "citations": [{"evidence_id": "...", "source": "..."}],

  "confidence": 0.0,

  "needs_clarification": false,

  "abstain_reason": null,

  "proposed_action": {"operation": "none|add_internal_note|grant_service_credit",

                        "control": "none|confirm|hitl"},

  "release_id": "...",

  "trace_id": "..."

 }

前端卡片是加分项；API、CLI 或 OpenAPI 能完整展示结构化契约即可通过。

# 03  基线、边界与启动方式

先证明原系统是好的，再证明你的改动只改变了应该改变的部分

## 唯一推荐基线

1. 从最新 main 创建个人分支；不要同时启动旧周次 worktree，避免同名 omni\_\* 容器互相替换。
2. 先完成 Capstone bootstrap，保存确定性基线；再开始修改。
3. 默认本地模式可验证工程闭环；要声明生成质量，必须配置真实模型（课程推荐本机 Ollama或国内模型厂商提供的服务）并运行评测。

## 基线启动命令

cp infra/env/.env.example infra/env/.env.local



 docker compose --env-file infra/env/.env.local -f infra/docker-compose.yml up -d --build



 docker compose --profile capstone --env-file infra/env/.env.local \

  -f infra/docker-compose.yml run --rm capstone_bootstrap



 docker compose --profile tools --env-file infra/env/.env.local \

  -f infra/docker-compose.yml run --rm devbox \

  python -m scripts.capstone.verify_e2e

**通过信号｜**验证器顶层输出 status=pass，报告写入 reports/capstone/e2e-verification.json；重复 bootstrap 后工单和 chunk 不应翻倍。

## 明确不做

| **不要求** | **原因** |
|-|-|
| 从零搭建聊天系统 | 无法检验学员是否会复用真实工程边界 |
| 更换数据库或向量库 | 会把时间消耗在迁移，而非课程能力 |
| 训练或微调模型 | 本作业重点是应用工程、数据与控制面 |
| 强制新写 Tool | 优先复用   add_internal_note / grant_service_credit，重点验证控制 |
| 必须做完整 UI | API/CLI 的产品契约、证据和验收更重要 |
| 必须部署云上 | 本地 Compose   是参考实现；生产差距用文档说明 |

# 04  八步实施主线

每一步都有输入、动作、证据和完成定义

| **阶段** | **核心动作** | **完成证据** |
|-|-|-|
| 1. 建立基线 | 运行   bootstrap 与 E2E；记录 commit、release、数据数量、现有通过项。 | baseline.md + 原始 E2E JSON |
| 2. 定义产品问题 | 选择主题；写用户、触发条件、成功/拒答/审批边界；冻结输出契约。 | architecture.md   中的问题与非目标 |
| 3. 发布小型知识包 | 新增至少 2 份合成   Markdown/HTML 文档和 manifest；声明 source/version/license/PII。 | 契约校验通过；原始对象与版本可查 |
| 4. 走真实数据链 | 使用现有   parse/chunk/index；重复执行；记录新增 chunk、evidence 和 release。 | 二次运行无重复；可检索到新   evidence |
| 5. 实现方案卡 | 复用生产级   Query Rewrite + Hybrid RAG；返回结构化结果；不足时澄清/拒答。 | Schema 测试   + 真实 API 返回 |
| 6. 接入受控动作 | 最多建议现有动作；低风险显式确认，高风险进入   HITL；使用幂等 key。 | 直接完成/等待审批/批准恢复三种证据 |
| 7. 评测与追踪 | 构建 6–8 条   Golden Set；运行基线/候选对比；从 Phoenix 分析 1 个坏案例。 | eval_report.md   + trace_id + 修复说明 |
| 8. 发布与回滚 | 绑定   data/index/prompt/skill/service 版本；执行 dry-run/rollback；重跑旧 E2E。 | release_and_rollback.md   + 回归通过 |

## 实施纪律

- 每次只改一个责任边界：先契约和数据，再检索/生成，再动作，再发布。
- 所有判断都要有机器证据：JSON、测试结果、查询结果、trace 或 manifest；截图只能辅助。
- 保留失败记录。一个被定位、解释并修复的坏案例，比十个只展示成功的案例更有价值。
- 不要绕过 Product API 直接从浏览器调用内部 Tool/RAG 接口冒充用户或租户。

# 05  详细要求与完成定义

把“做了”转成可审阅、可复现的工程证据

| **要求** | **最低完成定义** | **必须提交的证据** |
|-|-|-|
| R1 数据与契约 | ≥2 份合成文档；有   manifest；字段/PII/版本校验；失败输入能被拒绝 | contract   test、manifest、失败报告 |
| R2 幂等与版本 | 首次新增、二次跳过或   upsert；数据与索引绑定 release | 两次运行计数对比 |
| R3 Query   Rewrite | 精确错误码、型号、CVE、版本号不得被删改；失败可降级 | 至少 1 条   identifier preservation case |
| R4 检索与证据 | Hybrid   Retrieval；有 evidence_id/source/section；无证据不生成确定答案 | 引用正确率/拒答案例 |
| R5 结构化输出 | 结果符合方案卡   Schema；字段缺失、类型错误会被检测 | schema   test 或契约测试 |
| R6 Skill/能力边界 | 能力用途、输入、输出、失败、权限和版本可发现 | Skill 定义或能力说明 |
| R7 受控动作 | 低风险确认；财务/权限/账户安全走   HITL；幂等 key 必填 | completed/awaiting_approval/resume |
| R8 评测 | 6–8 条   Golden Set；基线与候选同口径；报告含失败分布 | eval   report + 原始结果 |
| R9 可观测 | 关键链路能按   trace_id 关联；默认不记录敏感原文 | Phoenix trace + bad-case 分析 |
| R10 发布回滚 | 版本绑定、门禁、激活/回滚证据；旧   E2E 继续通过 | release   manifest + regression |
| R11 成本性能 | 记录 p50/p95、生成/降级比、平均   tokens 或代理指标 | 小样本报告，注明限制 |
| R12 生产差距 | 明确本地实现不等于   HA/容量/云安全完成 | reflection   中列 3 个下一步 |

**关于 Ollama｜**可以用本机 Ollama完成真实生成。报告中必须记录 provider/model、generation_mode、query_rewrite mode 和 fallback_reason；不能仅凭环境变量声称已经调用本地模型。

**也可以使用国内模型厂商提供的模型接口，项目已适配：DeepSeek、千问、月之暗面。也支持兼容 OpenAI 接口规范的第三方网关，详见项目中的 llm.py 和 config.py。**

## 生产级 Query Rewrite 的最低验收

- vector_query 用于语义召回，lexical_query 保留精确词，原始 question 用于 rerank 与答案生成；三者不得混为一个字段。
- LLM 输出必须通过 JSON、长度和 protected identifier 门禁；新增或删除受保护标识时拒绝候选并降级。
- 超时、重试、熔断、缓存、租户隔离、PII 最小化和 Prompt Release 可在 debug/trace 中证明。
- HyDE 默认关闭；只有独立评测证明收益且风险可控时，才可作为加分项启用。

# 06  统一验收用例

所有学员用同一类证据过关，同时保留主题选择空间

| **用例** | **输入意图** | **预期系统行为** | **核心证据** |
|-|-|-|-|
| C1 正常证据问答 | 问题与新知识包直接相关 | 返回诊断、≤3 步、至少   1 条正确 citation、release_id、trace_id | 回答内容与证据一致 |
| C2 精确标识保护 | 问题含错误码/型号/版本，如   EG-BOOT-004 | 改写后标识仍存在；FTS   可命中；回答不篡改 | query_rewrite   debug + trace |
| C3 歧义澄清 | 缺少产品/版本/错误信息 | needs_clarification=true   或安全拒答 | 不把猜测包装成高置信答案 |
| C4 证据不足/冲突 | 知识库无答案或两份文档冲突 | citations 为空或标出冲突；abstain_reason   非空 | 拒答被视为正确结果 |
| C5 低风险动作 | 建议写内部备注 | 用户确认后   completed；相同幂等 key 重放不重复写 | action +   audit + timeline |
| C6 高风险动作 | 财务、权限或账户安全相关 | 必须   awaiting_approval；管理员批准后才 resume | approval_id + wait/resume trace |
| C7 模型故障 | 关闭 Ollama/制造超时/非法   JSON | Rewrite 降级且   RAG 不返回 500；debug 说明 fallback | fallback_reason   + 服务健康 |
| C8 回归与回滚 | 运行原   Capstone E2E；切回旧 release | 原用例仍 pass；回滚后版本一致且新能力按预期关闭/还原 | 两份报告 +   release pointer |

 

## 建议 Golden Set 字段

{

  "case_id": "C2_identifier_preservation",

  "question": "How do I recover EG-3000 after EG-BOOT-004?",

  "expected_route": "hybrid",

  "required_identifiers": ["EG-3000", "EG-BOOT-004"],

  "required_evidence": ["doc:..."],

  "expect_abstain": false,

  "expected_action_control": "none",

  "tags": ["rewrite", "lexical", "regression"]

 }

## 推荐最小指标

| **维度** | **指标** | **合格建议值** | **说明** |
|-|-|-|-|
| 正确性 | 关键点通过率 | ≥ 80% | 6–8 条小样本，只用于课程验收 |
| 证据 | 引用支持率 | 100% | 出现   citation 时必须能支持对应结论 |
| 安全 | 高风险动作绕过数 | 0 | 一票否决项 |
| 稳健性 | 模型故障请求成功率 | 100% | 允许降级，不允许   500 |
| 回归 | 原 Capstone   E2E | pass | 证明没有破坏既有产品链 |
| 性能 | p95 延迟 | 报告并解释 | 不强设跨机器阈值；需对比基线 |

 

# 07  硬门槛与红线

任何一个安全或可复现硬门槛失败，都不能被漂亮页面抵消

| **硬门槛** | **判定标准** |
|-|-|
| G1 可运行 | 助教能从仓库根目录按   README 在 Docker/Devbox 重跑；不能依赖只存在于个人机器的私有 venv。 |
| G2 无伪证据 | 引用必须来自真实检索结果；不得把手写   URL/evidence_id 当成检索证据。 |
| G3 租户与隐私 | 不得跨 tenant   返回 case/evidence；Trace 默认不记录客户原文、密钥和 PII。 |
| G4 无失控副作用 | 高风险动作不得自动执行；权限、审批、幂等由代码/契约保证，不靠   Prompt 提醒。 |
| G5 可回归 | 新增契约/单测通过，原   scripts.capstone.verify_e2e 仍 pass。 |
| G6 可追溯 | 返回中有   release_id/trace_id；报告能从请求定位到关键 span 与版本。 |

 

**计分规则｜**G2、G3 或 G4 失败：本次作业判为未通过，修复后可重新验收。G1、G5 或 G6 失败：总分最高 59 分，补齐证据后可恢复正常评分。

## 禁止做法

- 为了“答案更像真的”而在 fallback 中写死标准答案或 citation。
- 浏览器直接携带内部 service token 调 Tool API，绕过 Product API 身份与租户控制。
- 删除失败样本、只截成功页面，或用不同数据分别跑基线和候选。
- 提交真实客户数据、真实密钥、未脱敏日志或包含 PII 的 trace。
- 把 deterministic fallback 的结果描述成真实模型生成质量。

# 08  提交物与目录模板

让助教在十分钟内找到代码、证据、报告和演示入口

## 推荐目录

assignments/final_capstone/<student_id>/

 ├── README.md

 ├── design/architecture.md

 ├── data/                  # 文档与 manifest（仅合成数据）

 ├── contracts/             # 方案卡/能力契约或变更说明

 ├── evals/golden_set.jsonl

 ├── reports/baseline.md

 ├── reports/eval_report.md

 ├── reports/e2e_report.json

 ├── reports/release_and_rollback.md

 ├── demo/demo_script.md

 └── reflection.md

## 八项必交物

| **提交物** | **最低内容** |
|-|-|
| D1 README | 一键启动、前置条件、配置、验收命令、预期输出、故障排查 |
| D2 设计说明 | 问题、用户、主链、边界、非目标、关键取舍；建议   2–4 页 |
| D3 数据与契约 | 2+ 文档、manifest、结构化输出/Skill   契约；全部为合成数据 |
| D4 代码与测试 | 功能实现、契约测试、失败测试、原有回归；提交到个人分支 |
| D5 Golden   Set | 6–8 条，覆盖   C1–C8；含预期证据、拒答和动作控制 |
| D6 评测与   Trace | 基线/候选对比、原始结果、1   个 bad-case、Phoenix trace_id |
| D7   Release/回滚 | 版本绑定、门禁结果、激活/回滚步骤、回滚后验证 |

## README 必须出现的验收摘要

```YAML
baseline_commit: <sha>
candidate_commit: <sha>
theme: webhook-troubleshooting
provider/model: ollama / <model> | deterministic fallback
release_id: <id>
golden_set: 8 cases, <n> passed
hard_gates: G1..G6 pass
capstone_e2e: pass
representative_trace_id: <id>
known_limitations: <three concise items>
```



# 9  学员反思题

最终掌握不是“我跑通了”，而是知道为什么这样设计、哪里仍不够

1. 你的能力为什么不是一个普通聊天框？它在哪个业务决策点创造价值？
2. 哪个问题必须拒答或澄清？把它回答出来反而会造成什么风险？
3. 你的 Query Rewrite 扩大了什么召回？它可能怎样改变用户原意？你如何约束？
4. 如果引用存在但不支持结论，系统为什么仍然算失败？你的评测怎样发现它？
5. 为什么低风险动作也需要显式确认和幂等？为什么高风险动作不能只靠 Prompt 要求审批？
6. 当数据、索引和 Prompt 版本不一致时，会出现什么“看似随机”的问题？
7. 你从 Phoenix 中看到的一个坏案例是什么？根因、修复和防回归措施分别是什么？
8. 本地 Compose 到真实生产还缺什么？请按安全、可靠性、容量与运维各列一项。
9. 如果再给你两周，你会先做哪一项，而不是堆更多功能？用收益、风险和成本说明。

## 反思的高质量写法

**推荐结构｜**事实证据 → 你的判断 → 采取的取舍 → 残余风险 → 下一步验证。不要写“未来可以优化性能”这样的空话，要说明哪个指标、当前值、目标值和验证方式。

 

# 附录 A  项目导航与命令

从产品入口倒推到数据、检索、控制、评测、追踪和发布

## 建议先读的现有文件

| **责任** | **路径** | **阅读目标** |
|-|-|-|
| 总体运行 | runbooks/enterprise-capstone.md | 启动、bootstrap、E2E、产品演示、Ollama |
| 架构蓝图 | docs/blueprints/capstone/enterprise-capstone-blueprint.md | 产品/数据/控制面与课程映射 |
| E2E 验收 | scripts/capstone/verify_e2e.py | 真实 API、RAG、KPI、动作、HITL、Phoenix |
| Query   Rewrite | services/rag_api/app/query_rewrite.py | 缓存、单飞、重试、超时、熔断、门禁 |
| 改写底座 | pipelines/query/rewriter.py | 确定性规范化、标识保护、fallback |
| 生产手册 | runbooks/query-rewrite-production.md | 配置、Ollama、评测、SLO   与回滚 |
| RAG 主链 | services/rag_api/app/routers/rag.py | 改写→检索→生成→审计 |
| 检索实现 | services/rag_api/app/retrieval.py | vector/lexical/rerank query 分工 |
| 工具契约 | contracts/tools/ 与 services/tool_api/ | 权限、幂等、HITL、审计 |
| 评测/可观测 | evals/ 与   observability/ | Golden Set、门禁、SLO、Phoenix |
| 发布治理 | release/、rollout/、governance/ | manifest、pointer、Canary、rollback |

 

## 本机 Ollama 配置示例

```Plain Text
LLM_PROVIDER=ollama
LLM_MODEL=qwen3:14b
LLM_BASE_URL=http://host.docker.internal:11434/v1
QUERY_REWRITE_ENABLED=true
QUERY_REWRITE_STRATEGY=llm
QUERY_REWRITE_PROVIDER=ollama
QUERY_REWRITE_MODEL=qwen3:4b
QUERY_REWRITE_BASE_URL=http://host.docker.internal:11434/v1
QUERY_REWRITE_HYDE_ENABLED=false
```



验证时查看响应中的 generation_mode/provider/model 和 query_rewrite_debug.mode/provider/model/fallback_reason。若 mode=fallback，说明工程仍可用，但不能把本次结果计为 Ollama 生成质量验收。

## 常用入口

| **入口** | **地址** | **用途** |
|-|-|-|
| 产品 | http://localhost:8010 | 主演示入口 |
| Dagster | http://localhost:3000 | 资产物化与运行证据 |
| Phoenix | http://localhost:6006 | 按 trace_id   查链路 |
| RAG   OpenAPI | http://localhost:8000/docs | 查看内部契约 |
| Tool   OpenAPI | http://localhost:8001/docs | 查看   Tool/HITL 契约 |
| MinIO | http://localhost:9001 | 原始知识对象 |

 

# 附录 B  可直接复制的报告模板

统一结构能降低写文档负担，也便于助教按证据评分

## 评测报告模板

# Evaluation Report

```Markdown
Candidate / baseline / dataset / commit / release
Metrics and acceptance thresholds
Per-case results (C1–C8)
Baseline vs candidate comparison
Failed cases and root-cause categories
One Phoenix trace walkthrough
Regression and hard-gate result
Limitations and next experiment
```



## Bad-case 模板

```YAML
case_id: <id>
observed: <what happened>
expected: <what should happen>
trace_id: <id>
failed_stage: rewrite | retrieve | rerank | generate | policy | tool | release
root_cause: <evidence-backed cause>
fix: <smallest responsible change>
regression_test: <case/test added>
residual_risk: <what remains>
```

## 发布与回滚报告模板

```YAML
release_id: <candidate>
data_release_id: <id>
index_release_id: <id>
prompt_release_id: <id>
skill/service release: <id>
gates: contract / eval / security / e2e = pass
activation_evidence: <pointer/audit id>
rollback_target: <previous release>
rollback_verification: <C8 + original e2e result>
```



# 附录 C  提交清单与参考标准

提交前逐项勾选，避免“功能做了，但证据没交”

## 学员自检清单

- [ ] 从最新 main 创建分支，并记录 baseline/candidate commit。

- [ ] Capstone bootstrap 首次与二次运行结果均已保存。

- [ ] 新知识包全部为合成数据，manifest、契约、PII 门禁通过。

- [ ] 方案卡 Schema、正常路径、拒答路径和非法输出测试通过。

- [ ] C1–C8 至少 6 条已进入 Golden Set，所有硬门槛均通过。

- [ ] 引用逐条核对；不存在手写假 citation。

- [ ] 高风险动作不能绕过 HITL；幂等重放无重复副作用。

- [ ] 报告能证明 Ollama 真调用或明确标注 deterministic fallback。

- [ ] Phoenix 中能按 trace_id 找到关键 span，且没有敏感原文。

- [ ] 候选 release 可激活、可回滚；原 Capstone E2E 回归 pass。

- [ ] README 在一台干净环境中按步骤复跑过。

## 公开标准与课程依据

| **来源** | **链接/文件** | **用于本作业** |
|-|-|-|
| 课程   Capstone | runbooks/enterprise-capstone.md；enterprise-capstone-blueprint.md | 现有产品边界、E2E、发布与本地/生产差距 |
| NIST AI   RMF | [NIST AI RMF 官方资料](https://www.nist.gov/itl/ai-risk-management-framework) | AI 风险治理与生命周期管理 |
| NIST AI   600-1 | [NIST AI 600-1 官方资料](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf) | 生成式 AI 风险管理参考 |
| OWASP   Excessive Agency | [OWASP Excessive Agency 官方资料](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/) | 最小功能、最小权限、最小自主性与人工复核 |
| Agent   Skills | [Agent Skills 官方资料](https://agentskills.io/specification) | 能力定义与可发现性的开放规范参考 |
| OpenTelemetry   GenAI | [OpenTelemetry GenAI 官方资料](https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/) | 生成式 AI   Trace 语义字段参考 |

 

**最终提醒｜**“生产级”不是形容词，而是一组可复现证据：契约、失败策略、权限、评测、Trace、发布和回滚。作业的真正价值，是让你第一次完整经历这条证据链。
