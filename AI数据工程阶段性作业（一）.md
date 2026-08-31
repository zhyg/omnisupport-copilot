<title>AI 数据工程阶段性作业（一）</title>

# 一个新指标「从源头走到能被安全调用」

从「为什么 AI Demo 不能直接上线」讲到「契约、入湖、Iceberg、dbt 语义层」，每一周你都在同一个项目 omnisupport-copilot 上往前推了一小步。但很多同学都会疑惑：单周的东西都会，串起来就懵——契约是契约、入湖是入湖、指标是指标，中间是断的。

这次作业不增加新知识点：专门挑一个全新的客服运营指标，把它从最源头的数据契约，一路打通到 Agent 能安全调用为止。 走完这一遍，你才算真正理解什么是 AI 数据工程。

## **一、背景与场景**

假设你是客服数据团队的工程师。客服总监周会上拍板：

| 「我想在 BI 看板和客服 Copilot 里都能看到**工单解决率**——就是『已解决工单 ÷ 总工单』。要按天、按产品线看，而且 Copilot 答这个数的时候不能瞎编、不能把客户隐私带出来，权限也得管住。下周一上线。」 |
|-|

听起来就一句话，但要真把它「安全地上线」，你得让这个指标具备和现有 11 个指标一样的工程资质：**有契约口径、入了湖能回溯、dbt 算得出、注册表登记在案、只能通过受控工具按角色查询、还带测试和审计**。

这正是你这次要交付的东西。

**为什么是「工单解决率」这个指标？**

项目里现在已经有 11 个指标了（ticket_count、escalation_rate、sla_breach_rate、first_resolution_rate、avg_first_response_minutes 等等）。注意：**\`first_resolution_rate\`（首次解决率）和我们要做的 \`resolution_rate\`（整体解决率）不是一回事**——前者是「一次就解决」，后者是「最终解决了没有」。所以这是一个**全新的、清单里没有的指标**，你没法偷懒复用，必须老老实实走一遍全链路。

| 不想做 resolution_rate 的同学，可以二选一改做 **\`avg_resolution_hours\`（平均解决时长 = resolved_at − created_at 的小时数）**，难度相当。下文以   resolution_rate   为主线讲。 |
|-|

## **二、任务总览**

你要让 resolution_rate 这个新指标，沿着下面这条链路一路打通：

![图片展示了resolution_rate新指标的打通链路。从源数据（工单）出发，经契约校验、采集入湖 addCriterion图片展示了resolution_rate新指标的打通链路。从源数据（工单）出发，经契约校验、采集入湖、制造缺口、时间旅行验证一致性、dbt语义层、受控查询工具等环节，最后到Agent/BI安全消费。链路中还涉及中间表、事实表、新指标分子/分母口径写入SQL、注册表、安全视图等 addCriterion图片展示了resolution_rate新指标的打通链路。从源数据（工单）出发，经契约校验、采集入湖、制造缺口、时间旅行验证一致性、dbt语义层、受控查询工具等环节，最后到Agent/BI安全消费](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=NzRjYzQzZTJiYjcwNTk0YzU4ZTU5NjQxZmQyYzY5YmNfZjE5N2UxNjIwMjIyNDAzNjczZTc4Zjg2Yzc2YWNlYzBfSUQ6NzY0NzgyMjk4NDg0NTQ0NjA3NF8xNzg4MTYyNjcwOjE3ODgxNjYyNzBfVjM)

## **三、分阶段要求**

| 每个阶段都给了「要做什么 / 产出物 / 验收标准 / 老司机提示」。改的文件路径都写在项目里真实存在的位置，照着找就行。 |
|-|

### **阶段一：先把「Done」和边界定下来（Week 1）**

**要做什么**

**1.** 在 docs/blueprints/ 下新建一份 milestone_resolution_rate_acceptance.md，参考已有的 boundary-checklist.md 写法，把这个指标的验收口径和风险边界讲清楚：

- 指标的精确口径：分子是什么（status = resolved/closed 的工单数？）、分母是什么（当天创建的工单？还是当天活跃的工单？）、按哪些维度（建议 metric_date × product_line）。
- PII 分级：这个聚合指标本身该是 none 还是 low？为什么 Agent 拿到的视图里不能出现 customer_id？
- 谁能查：哪些角色（support_ops / instructor / admin）；哪些场景需要人工介入（HITL）。
- 明确「不可执行」红线：比如 Agent 不允许直接拼 SQL 访问原始工单表。

**产出物**：docs/blueprints/milestone_resolution_rate_acceptance.md（半页到一页即可）

**验收标准**：口径里分子分母无歧义；PII 等级有结论且给了理由；明确写了角色与 HITL 节点。

| 老司机提示：90% 的指标事故不是算错，是**口径没对齐**。「解决率」分母到底是「当天创建的」还是「当天处理的」，业务方和你脑子里很可能是两个数。先写下来、先对齐，比啥都强。 |
|-|

### **阶段二：把口径写进契约（Week 2）**

**要做什么**

**1.** 打开 contracts/data/ticket_contract.json，确认你算 resolution_rate 要用的字段（status、created_at、resolved_at）都在契约里、类型和枚举值对得上。

**2.** 在你的验收文档或一个 contracts/ 旁的小 YAML/MD 里，补一条**指标级口径声明**：分子分母用到哪些字段、哪些 status 算「已解决」、空值/异常怎么处理。

**3. 做一次契约门禁演练**：故意把一条样本工单的 status 改成一个契约枚举里没有的值（比如 done），跑一下契约校验，证明它能被拦下来。

**怎么跑**：项目里有 tests/contract/test_week02_gate.py，用 pytest tests/contract/test_week02_gate.py -q 验证；或者直接拿坏数据喂给校验逻辑看它报错。

**产出物**：指标口径声明（文字即可）+ 契约拦截的证据（报错截图或日志）

**验收标准**：能说清「哪些 status 算已解决」；演示了一次契约把脏数据拦下来。

| 老司机提示：契约不是摆设，它是你和上游之间的「合同」。上游哪天把 resolved 改成 Resolved（大小写），你的解决率第二天就崩——契约门禁就是用来在这种事发生时**当场报警**，而不是等业务方发现数据不对来骂你。 |
|-|

 

### **阶段三：入湖、制造缺口、补数（Week 3）**

**要做什么**

**1.** 跑通工单的采集入湖（pipelines/ingestion/ticket_ingest.py / seed_loader.py），确认数据落盘、ingest_state 有记录。

**2. 制造一个数据缺口**：人为删掉/跳过某一天的工单分区，模拟「那天采集挂了」。

**3.** 用 pipelines/ingestion/replay_backfill.py 做一次**补数干跑（dry-run）**，把这天补回来，并确认重复跑不会写重（幂等）。

**怎么跑**：参考 runbooks/ingestion_runbook_v1.md；干跑测试可看 tests/integration/test_replay_backfill_dry_run.py，跑 pytest tests/integration/test_replay_backfill_dry_run.py -q。

**产出物**：补数过程日志 + 一句话说明「为什么重复跑不会污染数据」

**验收标准**：缺口能被识别并补回；能解释幂等是怎么保证的（按 ingest_batch_id / 分区覆盖写之类）。

| 老司机提示：「补数」是数据工程师的家常便饭。面试官最爱问的就是「你的链路挂了一天，第二天怎么补、怎么保证不写重」。这一步就是练这个肌肉记忆。 |
|-|

 

### **阶段四：Iceberg 时间旅行 + 性能基线（Week 4）**

**要做什么**

**1.** 确认工单事实表已物化成 Iceberg（pipelines/lakehouse/materialize.py）。

**2.** 跑一次**时间旅行**（pipelines/lakehouse/demo_time_travel.py），用补数前/后的两个快照对比，验证你阶段三补的数据确实进去了、历史快照还能查到旧状态。

**3.** 记录一份**性能基线**：

|    python -m   pipelines.lakehouse.perf_baseline --all-core --out   reports/week04/iceberg_baseline_report.md |
|-|

记录行数、快照数、文件数、平均文件大小、最新快照 id。**Week4 阶段先别手动 compaction**，我们要的是「自然状态」的基线。

**产出物**：时间旅行对比结果 + reports/week04/iceberg_baseline_report.md

**验收标准**：能用两个快照 id 证明数据变化；性能基线该有的字段都记了。

| 老司机提示：Iceberg 的时间旅行不是炫技。真实场景是——线上某个指标突然异常，你能用   snapshot_id 把表「倒回」到昨天，对比到底哪条数据变了。这是定位 Bad Case 的杀手锏。 |
|-|

 

### **阶段五（重头戏）：dbt 语义层 + 注册表 + 安全工具（Week 5）**

这是分量最重的一步，把新指标真正「造」出来并管起来。

**5.1 在 dbt 里把指标算出来**

**1.** 确认 analytics/models/intermediate/int_ticket_activity_daily.sql 里有没有 resolved_ticket_count（已解决工单数）。已有就直接用；没有就补一个 count(\*) filter (where is_resolved)。

**2.** 在 analytics/models/marts/support_kpi_mart.sql 的指标列表（那个 values 长表展开）里，**新增一行 \`resolution_rate\`**，口径 = resolved_ticket_count / nullif(ticket_count, 0)。注意它是个 ratio，要做好除零保护。

**3.** 在 analytics/models/marts/agent_tool_input_view.sql 的指标白名单过滤里，**把 \`resolution_rate\` 加进去**——不加，Agent 就查不到它（这是故意的安全设计）。

**5.2 登记到指标注册表**

**4.** 打开 analytics/metric_registry_v1.yml，照着现有 ratio 指标（比如 escalation_rate）的格式，**给 \`resolution_rate\` 补一条完整登记**：name / label / business_name_zh / description / business_definition_zh / owner / metric_type: ratio / formula / unit / sensitivity / definition_status: production / version / allowed_roles / quality_tests。ratio 类记得声明分子分母。

**5.3 加 dbt 测试**

**5.** 复用 analytics/tests/ 里现成的测试思路：ratio_metrics_between_0_and_1.sql（解决率必须在 0–1 之间）、metric_values_non_negative.sql、还有 no_pii_columns_in_agent_tool_input_view.sql（确认你没把 PII 字段带进视图）。让这些测试覆盖到新指标。

**5.4 让受控工具能查它**

**6.** 打开 contracts/tools/tools/query_support_kpis_v1.json，把 resolution_rate 加进**允许查询的 metric 枚举**里。

**7.** 确认 services/tool_api/app/kpi_query.py / metric_registry.py 走的是注册表 + safe_view 那条受控路径（不需要大改，理解它怎么挡住越权和裸 SQL 即可）。

**怎么跑验收**

```Plain Text
cd analytics && dbt build        # 跑模型 + 测试
pytest tests/integration/test_week05_metric_registry.py -q
pytest tests/integration/test_week05_kpi_query_tool.py -q
pytest tests/contract/test_week05_metric_contracts.py -q
```

**产出物**：改动后的 dbt 模型 / 注册表 / 工具契约 + 测试通过截图

**验收标准**：dbt build 通过且新指标算出了合理的 0–1 之间的值；注册表登记完整；工具能查到 resolution_rate；PII 测试通过。

| 老司机提示：注意 5.1 和 5.4 的设计哲学——**指标默认是「查不到」的，你必须显式地在 mart、视图、注册表、工具四个地方都「开口子」，它才可查。** 这套「白名单层层放行」就是企业级数据安全的精髓：宁可漏放，不可错放。 |
|-|

### **阶段六：端到端串一遍（综合验收）**

把前五段连成一条能演示的链路，录一段 2–3 分钟的操作（或截图序列）证明：

**1.** 改一条源工单的 status 为 resolved →

**2.** 重新采集入湖（幂等，不写重）→

**3.** Iceberg 产生新快照（时间旅行能看到变化）→

**4.** dbt build 后 resolution_rate 的值相应变化 →

**5.** 用 support_ops 角色通过工具查到了新值；**再用一个没权限的角色查，拿到 \`denial_code\` 被拒** →

**6.** 查询过程在审计日志里留了痕。

**产出物**：一段端到端演示（视频/GIF/有序截图均可）+ 文字说明

**验收标准**：六步连贯、有证据；尤其要演示「有权限能查 + 越权被拒」这一正一反两个case。

## **四、交付与提交方式**

**1.** 把你的改动**提交到你自己 fork 的 GitHub 或 Gitee 仓库**（基于 omnisupport-copilot），保留清晰的 commit。

**2.** 在仓库里放一份 **《里程碑验收报告.md》**（模板如下），把六个阶段的产出和证据贴进去。

![图片展示的是《里程碑验收报告》模板内容。模板包含基本信息、指标口径、契约禁用、入湖与补数、时间序列与基线、dbt +image_id>注册表+工具、端到端演示等七个部分，每个部分有具体要求，如指标口径需明确分母、维度等，契约禁用需列出字段与枚举，入湖与补数要说明缺口、补全金全结果等，时间序列与基线需提供补数前后使用id、性能基线关键字等，dbt + 注册表+工具部分需改动代码清单、dbt build结果等，端到端演示需有测试结果、缺陷截图等。该模板用于记录AI数据工程阶段性作业各阶段产出和证据。](https://internal-api-drive-stream.feishu.cn/space/api/box/stream/download/authcode/?code=NTZlOWI1MWI1MTQ4N2YxZWIzYjVkYWI0NGEzZDZlMDhfMTJiNTA1MDRiYTJjMGY3OTIyMjIxYzAzNTliMDJjYWNfSUQ6NzY0NzgyMzIzMjQ3MDA5MzAyNF8xNzg4MTYyNjcwOjE3ODgxNjYyNzBfVjM)

**3.** 把你的**仓库链接**复制粘贴到本作业的评论框里，点「提交」。

## **五、常见坑 & FAQ**

**Q：解决率算出来大于 1 或者是负数？**

A：八成是分母用错了，或者没做除零保护。分母记得 nullif(ticket_count, 0)；分子的 status 集合（resolved/closed）要和分母的口径对齐到同一批工单。

**Q：dbt build 报错说找不到 \`resolved_ticket_count\`？**

A：先去 int_ticket_activity_daily.sql 确认这个计数字段存在，不存在就先在 intermediate 层补出来，再到 mart 引用。别跳过 intermediate 直接在 mart 里硬算，那就破坏了分层。

**Q：工具能查到别的指标，就是查不到我新加的 `resolution_rate`？**

A：检查你是不是漏了「四处开口子」里的某一处——mart 的 values、agent_tool_input_view 的白名单、metric_registry 的登记、工具契约的 metric 枚举。少一个都查不到。

**Q：我电脑 8G 内存跑不动整个 Docker 栈。**

A：走「阶段一/阶段二」。dbt 那部分对内存要求最低，优先把阶段五跑通；阶段三/四跑不动就写清设计 + 贴关键命令和你的理解。

| 阶段一 | 写出设计与口径（阶段一、二）+ 给出五个阶段的关键代码/配置   diff + 验收报告（哪怕没全跑通） |
|-|-|
| 阶段二 | 在项目里真实改代码，dbt build 与 Week5 测试跑通，阶段五完整落地 |
| 阶段三 | 六个阶段全打通 + 端到端演示 + 越权被拒的反例   + 性能基线/时间旅行证据齐全 |

跑不动完整环境的同学看下一节的「交付分档」，**至少交设计 + 关键代码 diff + 验收报告也能及格。**

**Q：PII 测试 `no_pii_columns_in_agent_tool_input_view` 挂了？**

A：你大概率把 customer_id 或 assignee_id 这类字段带进了 agent_tool_input_view。聚合视图里只能有维度（product_line、priority、org_id、category）和指标值，不能有任何能定位到个人的字段。