# 里程碑验收蓝图：工单解决率 (resolution_rate) 口径与安全边界规范

> 文档定位：阶段性里程碑业务验收口径 & 风险边界规范 (Week 01 - Week 05 贯通)  
> 责任团队：客服数据工程团队 (Support Data Engineering)  
> 版本：v1.0.0 (生产就绪)  
> 最后更新：2026-08-31  

---

## 1. 业务背景与指标定位

客服总监提出：「在 BI 看板和客服 Copilot 中能够准确查看工单解决率，按天、按产品线切片，同时严防模型幻觉、杜绝隐私泄露、管死权限边界。」

在企业级 AI 数据工程架构中，`resolution_rate`（工单解决率）与现有的 `first_resolution_rate`（首次解决率）有着本质区别：
- **`first_resolution_rate`（首次解决率）**：衡量客服初次响应即一次性闭环解决的能力（分子为 `first_resolution_count`，即无需多次来回交互的工单）。
- **`resolution_rate`（工单解决率）**：衡量业务总体交付闭环率（分子为最终达到已解决状态的工单量，分母为同期生成的工单总量）。

---

## 2. 指标精确业务口径与数学定义

### 2.1 口径定义

| 项目 | 规范定义 | 说明与边界 |
| :--- | :--- | :--- |
| **指标标识** | `resolution_rate` | 语义层、注册表与受控工具统一标识符 |
| **指标中文名** | 工单解决率 | 报表与 Copilot UI 显示名称 |
| **指标类型** | `ratio` (比率型) | 属于派生比率聚合指标 |
| **分子 (Numerator)** | `resolved_ticket_count` | 统计窗口内状态为已解决（`status = 'resolved'`）的工单总数。若未来业务规则扩展 `closed` 状态进入终态，需经数据契约修订。 |
| **分母 (Denominator)** | `ticket_count` | 统计窗口内创建的工单总量（`count(*)`）。 |
| **计算公式** | `resolved_ticket_count / nullif(ticket_count, 0)` | 强制执行除零保护（Null-division Safe），当分母为 0 时返回 NULL。 |
| **数值范围** | `[0.0000, 1.0000]` | 取值严格受限在 0 到 1 之间，保留 4 位小数（`numeric(12, 4)`）。 |
| **统计颗粒度 (Grain)** | `metric_date` × `tenant_id` × `product_line` × `priority` × `org_id` × `category` | 支持按天与多业务维度安全切片。 |
| **推荐分析维度** | `metric_date` × `product_line` | BI 看板与 Copilot 默认主分析切片。 |

### 2.2 状态判定与异常值处理
- **已解决判定**：基于 `ticket_contract.json` 枚举约束（`["open", "pending", "in_progress", "resolved", "closed", "escalated"]`），底层 `stg_tickets` 标准化为 `lower(status) = 'resolved'`。
- **缺失与空值处理**：工单若缺失创建日期，在入湖契约门禁阶段直接拦截阻断；若无已解决工单，分子为 0，比率为 0.0000。
- **跨周期工单口径**：分母基于工单创建日期（Cohort 方式归属在 `created_date`），保证同批次工单解决率计算口径的一致性与可回溯性。

---

## 3. PII 敏感度与数据安全分级

### 3.1 指标本身分级：`none` (聚合级安全)
- `resolution_rate` 本身是按日与组织维度的宏观统计比率（Ratio），不包含任何个人身份信息，因而指标本身的敏感度定级为 **`none`**。

### 3.2 严禁向 Agent 暴露 `customer_id` / PII 字段的根本原因
1. **防止横向越权与精准关联推断**：`customer_id`、`contact_email`、`subject`、`body` 属于 High PII。若大模型或 Copilot 能够直接获取带 `customer_id` 的细粒度数据，攻击者可通过特定过滤条件或少样本逆向推断出具体企业客户的运维状况、故障频率及个人身份。
2. **遵守最小特权原则 (PoLP)**：Copilot 进行 KPI 查询、宏观运营分析与健康度评估，只需要汇总统计值与业务分组维度（如 `product_line`, `category`, `priority`），无需访问个体身份。
3. **安全视图白名单物理隔离**：通过 `agent_tool_input_view` 视图实施物理列投影，严格剔除所有 PII 字段，从根本上杜绝 Prompt 注入引发的隐私泄露。

---

## 4. 访问控制、角色授权与 HITL 规范

### 4.1 角色授权矩阵 (RBAC)

| 角色 (Role) | 是否允许查询 `resolution_rate` | 约束条件 | 鉴权失败拒绝码 |
| :--- | :---: | :--- | :--- |
| `support_ops` | ✅ 允许 | 必须携带租户组织范围 `actor_org_ids`，只能查询本组织/部门范围内数据 | `ORG_SCOPE_REQUIRED` / `ROLE_DENIED` |
| `instructor` | ✅ 允许 | 教学与评测角色，允许全局分析，需记录完整审计轨迹 | `ROLE_DENIED` |
| `admin` | ✅ 允许 | 系统运维管理角色，拥有全域观测权限 | `ROLE_DENIED` |
| `support_agent` | ❌ 禁止 | 客服一线专员，仅具备单工单操作权限，无宏观 KPI 统计权限 | `ROLE_DENIED` |
| `end_user` | ❌ 禁止 | 外部终端用户，严禁跨工单或查看运营统计 | `ROLE_DENIED` |

### 4.2 人工介入 (HITL - Human-in-the-Loop) 触发节点
1. **未登记指标或未知维度查询**：Agent 尝试请求未经注册表或契约许可的指标时，工具层直接硬拒绝并告警（Action: `reject`），若涉及高风险外部操作需转工单人工审批。
2. **异常超大查询窗口**：查询时间窗口超过注册表设定的最大阈值（如 `max_window_days = 90` 天）时，禁止自主执行，必须由数据管理人员人工核准导出需求。
3. **跨多租户大范围聚合异常分析**：非 admin 角色发起异常大范围 cross-tenant 汇总时，记录安全告警并触发安全审计复核。

---

## 5. 系统红线与反模式（绝对禁止）

1. 🛑 **严禁 Agent 直接拼接裸 SQL**：任何场景下都不允许 Agent 生成 SQL 字符串并直接在 PostgreSQL 或 Lakehouse 上执行。所有数据访问必须封装在强类型、受控的参数化工具接口（`query_support_kpis_v1`）中。
2. 🛑 **严禁绕过指标注册表直接暴露底层表**：底层物化表 `support_kpi_mart` 及各类原始事实表对 Agent 不可见；Agent 唯一且仅能读取经过安全脱敏、字段白名单约束的 `agent_tool_input_view`。
3. 🛑 **严禁隐式指标放行**：遵循「四处显式开口子」原则——模型 Mart、安全 View、指标注册表 (Metric Registry)、工具契约 (Tool Contract) 四重闭环，任一处未放行则坚决不予暴露。
4. 🛑 **严禁无审计调用**：每一次工具调用、每一次拒绝（Denial）都必须生成全局唯一的 `audit_id` 与 `trace_id`，并持久化到审计日志表中。
