# 店枢 ShopPivot · M1 前端工作台

个人工作室自用的 RPA 电商自动化运营平台，M1 运营工作台。本目录只包含前端，**
不修改后端 `src/`、`modules/`、`tests/`、`Makefile`**。

- 技术栈：Vue 3.5 + TypeScript + Vite + Vue Router 4 + Pinia + Element Plus（仅 ElSelect / ElButton / ElTable / ElTag）+ vitest + @vue/test-utils + vue-tsc
- 设计气质：克制、信息密度高的后台工具；深青蓝主色、4px 圆角、1px 边框、六类语义色；无渐变、无玻璃拟态、无营销插画、无装饰动效
- 当前交付页面：登录、P01 经营看板、P02 评价与口碑、P03 库存与补货、P05 我的待办、P06 变更单详情、P09 场景与模块、P10 口径与数据合同、P11 机器人与日志、P12 权限与订阅

## 快速开始

```bash
# 1. 安装依赖（缓存目录已覆盖，适配受限网络）
cd frontend
npm_config_cache=/tmp/npm-cache pnpm install --store-dir /tmp/pnpm-store

# 2. 构建（vue-tsc 类型检查 + vite build）
pnpm build

# 3. 单元测试
pnpm test

# 4. 本地开发（5173，/api 代理到 127.0.0.1:8000）
pnpm dev

# 5. 预览构建产物（同样代理 /api）
pnpm preview
```

后端启动（仓库根目录，另开终端）：

```bash
make serve
```

首次冒烟前建议先跑一次种子与演示日报：

```bash
make demo                 # 建表 + 种子 + 跑一次 S01 日报
PYTHONPATH=src:. python3 -m bootstrap.cli create-demo-approval --sla-seconds 3600   # 可选：造一条 L2 待办
```

测试账号：

| 账号 | 口令 | 角色 | 可访问页面 |
| --- | --- | --- | --- |
| `owner` | `owner123` | OWNER | P01 / P02 / P03 / P05 / P06 / P09 / P10 / P11 / P12 |
| `editor` | `editor123` | EDITOR | P01 / P02 / P03 / P05 / P06 |
| `viewer` | `viewer123` | VIEWER | P01 / P02 / P03 / P05 / P06 |

> M1 仍沿用平台闸门与角色约束：P10 / P11 / P12 仅 OWNER 可访问；P02 / P03 的派单、关闭、采纳、忽略等写入动作需要 `handle_todo`（OWNER / EDITOR），VIEWER 只读。

## 目录结构

```
frontend/
├─ index.html
├─ package.json
├─ tsconfig.json / tsconfig.node.json
├─ vite.config.ts
├─ README.md
├─ src/
│  ├─ main.ts / App.vue / router.ts
│  ├─ api/
│  │  ├─ client.ts              # fetch 封装、Bearer、错误信封、401 清理与跳转、xlsx 导出
│  │  └─ types.ts               # 与后端 /api/v1 对齐的类型
│  ├─ stores/
│  │  ├─ session.ts             # token / role / username 持久化
│  │  ├─ context.ts             # 平台 / 店铺 / 时间窗 / 口径版本
│  │  └─ shell.ts               # 导航 + 状态条数据
│  ├─ shell/
│  │  ├─ AppShell.vue
│  │  ├─ GlobalContextBar.vue
│  │  ├─ StatusBar.vue
│  │  └─ SideNav.vue
│  ├─ components/               # 通用组件 + 抽屉 / 弹窗 / Toast / KPI / 趋势条
│  ├─ pages/
│  │  ├─ LoginPage.vue
│  │  ├─ P01Dashboard.vue
│  │  ├─ P02Reviews.vue
│  │  ├─ P03Inventory.vue
│  │  ├─ P05Todos.vue
│  │  ├─ P06ChangeOrder.vue
│  │  ├─ P09Modules.vue
│  │  ├─ P10MetricCards.vue
│  │  ├─ P11Workers.vue
│  │  └─ P12Access.vue
│  ├─ i18n/zh-CN.ts             # 全部中文文案唯一来源
│  ├─ styles/{tokens.css,base.css}
│  └─ utils/{format.ts,status.ts}
└─ tests/{setup.ts,fixtures.ts,copy.spec.ts,states.spec.ts,m1.spec.ts}
```

## 页面与交互

### 应用外壳

- 顶部全局栏：品牌、平台 / 店铺 / 时间窗 / 口径版本四个下拉、当前角色、通知数、账号、退出登录。
- 状态条：`run_id`、最近采集时间、待办数、在线机器人数、只读徽标。
- 左侧三组导航：按后端 `/workbench/nav` 的 `menu` 字段分组；`available=false` 页面灰显、不可路由，点击提示「该页面在后续阶段交付」。
- 路由守卫：无 `localStorage['shoppivot.token']` 跳 `/login`；任意请求 401 时清空 token、角色、用户名并跳回登录页。
- 登录成功后写入 `shoppivot.token`、`shoppivot.role`、`shoppivot.username`（另存 `shoppivot.display_name`、`shoppivot.shops` 用于外壳展示）。

### P01 经营看板

- 4 张指标卡取 `rows[-1].cells` 的 `uv / paid_orders / gmv / cvr`；空值显示 `null_reason`，不显示 0。
- 日报主表：统计日期 + `report.columns`，表头带单位；`RATIO` 列标记「不可加（比率类）」，非可加列标记「不可加」。
- `raw === null` 或存在 `null_reason` 的单元格统一显示「不适用」，原因放入 `title`；不会出现 0 / 0.00 / 空白。
- 表格上方展示水印、取数通道、数据状态、平台闸门；空态显示 `report.empty_copy` 原文（默认「该时间窗暂无数据（非取数失败）」）。
- 告警条仅在 `alerts` 非空时展示，支持点击告警指标下钻。
- 单元格点击打开右侧「口径卡」抽屉：定义、公式、分母、单位、精度、可加性、空值策略、来源、探针 SQL、实测值、质量自检、发布闸门、ODS 证据引用、run_id 链接。
- 运行详情抽屉：节点状态 / 耗时 / 通道 / `payload_digest`、ODS 列表；ODS 可继续打开证据抽屉，展示脱敏提示与 JSON。
- 导出：`GET /reports/{id}/export`，blob 下载 `<report_id>.xlsx`，按钮旁展示水印摘要。
- 监听 context store 的 `platform / shopId / window / metricVersion`，任一变化重新请求日报。

### P05 我的待办

- Tab：全部 / L2 待确认 / 异常，带计数。
- 字段：类型徽标、标题、状态、倒计时（`mm:ss`）；PENDING 且 `remaining_seconds <= 0` 显示橙色「已超时」；EXPIRED 显示灰态「已超时自动作废，需重新发起变更单」。
- 点击 `TODO-APPROVAL` 从 `href` 提取 `/change-orders/{id}` 并跳转；异常项只读展示。
- 空态「暂无待办」。

### P06 变更单详情

- 单头摘要：变更单号、task_id、状态、gate_level、WritePlanHash（截断显示，`title` 全量）、口径版本、快照时间、申请人、场景、平台/店铺、SLA、Schema 版本。
- 前后对比表、影响范围、证据包（kind / label / ref，缺失时红字「证据缺失，禁止批准」）、风险与回滚、结果时间线。
- 操作区四个按钮：批准 / 驳回 / 转交 / 撤回；`readonly=true` 时全部 disabled，并显示 `readonly_copy` 原文「需审批后执行（当前只读模式）」。
- 无 id 或变更单不存在（E008）时显示空态「该变更单已归档或已作废」。

### P09 场景与模块

- 顶部显示 `kernel_api`、`platform_gate_max` 与只读徽标。
- 模块列表：名称、类别、版本、状态徽标、贡献 card_id 列表、是否 core；状态色 INSTALLED 绿、DEGRADED 橙、DISABLED 灰、REJECTED 红。
- blocked 区域使用红色 Alert 逐条显示「模块 {module} 未加载：{reason}」。
- 非 core 模块在 OWNER 下显示「禁用」，二次确认后调用 `POST /modules/{name}/disable` 并刷新；成功显示提示并同步刷新左侧导航与状态条。
- 组合包区域显示「暂无组合包」空态。

### P02 评价与口碑

- 数据接口：`GET /reviews/summary`（KPI + DSR 趋势）与 `GET /reviews/tickets`（工单列表）。
- 顶部 KPI：待处理 / 已派单 / 超时 / 已关闭；顶部常驻「买家信息已脱敏，原文证据仅审计角色可见」。
- DSR 趋势：纯 CSS 柱状条，展示 `stat_date`、保留 2 位的 DSR 均值与样本数；无数据显示子区块空态。
- 工单表：严重度徽标（HIGH 红 / MEDIUM 橙）、SKU / 评价 ID、评分、`content_masked`、命中规则、状态、SLA 倒计时（`hh:mm:ss` 或 `mm:ss`，超时显示橙色「已超时」）、处理人。
- OPEN / ASSIGNED 行在 OWNER / EDITOR 下显示「派单」「关闭」，弹窗必填；成功后同时刷新列表与 summary。VIEWER 隐藏操作列并显示「只读角色不可处理」。
- 空态使用接口 `empty_copy` 原文「暂无差评或问答待处理」。

### P03 库存与补货

- 数据接口：`GET /inventory/reconciliation`；KPI 取 `counts` 的 STOCKOUT / OVERSELL / MISMATCH / STAGNANT / CONSISTENT。
- 三方对齐表：SKU、平台 / ERP / WMS 可售、差异类型中文标签、delta、容差、三列独立快照时间（缺失显示 —）。
- 补货建议：SKU、动作（补货 / 暂停 / 同步）、数量、原因、状态；OPEN 建议在 OWNER / EDITOR 下可「采纳」「忽略」，弹窗可填备注，成功后刷新。
- 常驻 `snapshot_note`，并强调「只输出建议，不自动下单」；空态使用接口 `empty_copy` 原文「三方库存一致，无差异」。
- 文案树与页面均不包含「自动补货」「自动改库存」。

### P10 口径与数据合同

- 数据接口：`GET /metric-cards`、`GET /metric-cards/{code}`、`GET /metric-cards/{code}/diff`、`POST /metric-cards/{code}/release`。
- 口径卡表：指标编码、名称、版本、单位、可加性（RATIO 显示「不可加（比率类）」）、来源映射、最近自检（未自检 / 通过 / 未通过 + 时间）。
- 点击行打开右侧抽屉：定义、公式、分母、单位、精度、可加性、空值策略、来源映射、探针 SQL、质量自检、ODS 证据与实测值；底部「版本对比」调用 diff，字段差异按 before / after 展示，无历史版本时展示接口 note。
- 「运行发布自检」仅 OWNER 可用；成功展示 5 项检查全部通过，409 时读取 `details.release.checks` 逐项展示通过 / 失败与 detail，并显示「发布自检未通过，口径卡未发布」。
- 空态使用接口 `empty_copy` 原文「尚无已发布口径卡」；页面注明「口径卡是业务可读的语义契约，不是说明文字」。

### P11 机器人与日志

- 数据接口：`GET /workers`、`GET /exceptions?limit=100`、`POST /worker/register-demo`。
- 机群：在线数、Worker 表（ID / 类型 / 状态 / 能力 / 队列积压 / 最后心跳）；空态使用 `empty_copy` 原文「暂无在线机器人」。
- OWNER 显示「登记本机 Worker」，成功后刷新 Worker 列表与顶部状态条。
- 异常按 `err_layer` 的 UI / SYS / DATA / CODE 四层分组并显示每层计数；每条展示 `err_code`、message、`run_id`（点击打开运行详情抽屉）、`node_id`、时间与是否可重试；无异常时显示「暂无异常」，四层标签仍常驻。
- 顶部说明「E001~E008 分层定位；日志含 run_id，可反查到原始报文」。

### P12 权限与订阅

- 数据接口：`GET /identity/roles`、`GET/POST/DELETE /subscriptions`、`GET /notifications/templates`。
- 角色矩阵：3 角色 × permissions 列表；店铺授权按 `shops` 展示平台 / 店铺 / 角色。
- 订阅：列表 + 新建表单（名称、事件 EVT-01/02/03/04/07、接收人、渠道、时间窗、阈值 JSON 可选、静默窗口可选）；删除二次确认；事件 + 接收人重复时展示 409 冲突文案。
- 通知模板：event / title / body / module。
- 常驻「凭据不出现在界面；只显示引用与状态」；新建与删除仅 OWNER / EDITOR 可用，VIEWER 只读。
- 空态使用接口 `empty_copy` 原文「暂无订阅」。

## 文案与状态红线

所有中文文案集中在 `src/i18n/zh-CN.ts`，组件内无中文硬编码。以下常量被测试直接断言：

| 常量 | 文案 |
| --- | --- |
| `EMPTY_REPORT_COPY` | 该时间窗暂无数据（非取数失败） |
| `EMPTY_TODOS_COPY` | 暂无待办 |
| `EMPTY_BUNDLES_COPY` | 暂无组合包 |
| `EMPTY_REVIEWS_COPY` | 暂无差评或问答待处理 |
| `EMPTY_INVENTORY_COPY` | 三方库存一致，无差异 |
| `EMPTY_METRIC_CARDS_COPY` | 尚无已发布口径卡 |
| `EMPTY_WORKERS_COPY` | 暂无在线机器人 |
| `EMPTY_EXCEPTIONS_COPY` | 暂无异常 |
| `EMPTY_SUBSCRIPTIONS_COPY` | 暂无订阅 |
| `RATIO_BADGE` | 不可加（比率类） |
| `READONLY_COPY` | 需审批后执行（当前只读模式） |
| `READONLY_ROLE_COPY` | 只读角色不可处理 |
| `EXPIRED_COPY` | 已超时自动作废，需重新发起变更单 |
| `MASKED_COPY` | 买家信息已脱敏，原文证据仅审计角色可见 |
| `EVIDENCE_MISSING_COPY` | 证据缺失，禁止批准 |
| `UNAVAILABLE_PAGE_COPY` | 该页面在后续阶段交付 |
| `RELEASE_FAILED_COPY` | 发布自检未通过，口径卡未发布 |
| `SUGGESTION_ONLY_COPY` | 只输出建议，不自动下单 |
| `CREDENTIALS_COPY` | 凭据不出现在界面；只显示引用与状态 |
| `moduleBlockedCopy(name, reason)` | 模块 {name} 未加载：{reason} |

测试同时断言文案树中不存在「AI 自动执行」「一键优化」「已自动执行」以及「自动补货」「自动改库存」。

## 设计令牌

`src/styles/tokens.css` 定义并覆盖 Element Plus 变量：

```css
--sp-primary:#14505c; --sp-primary-hover:#1b6675; --sp-bg:#f5f7f8;
--sp-surface:#fff; --sp-border:#d7dee2; --sp-text:#1f2a30;
--sp-muted:#5c6b73; --sp-success:#2e7d5b; --sp-warning:#b26a00;
--sp-danger:#b3261e; --sp-info:#2f5d8a; --sp-readonly:#6b7a80;
--sp-radius:4px;
```

另含语义浅色底、边框色、字体、尺寸与浮层阴影；Element Plus 的 `--el-*` 变量映射到同一套令牌，确保 ElSelect / ElButton / ElTable / ElTag 与自绘组件风格一致。

## 验收记录

```text
$ pnpm install --store-dir /tmp/pnpm-store
（已有 node_modules，本次增量未重复安装）

$ pnpm build
✓ vue-tsc --noEmit 通过
✓ 1737 modules transformed
✓ built in 3.31s

$ pnpm test
✓ tests/errors.spec.ts (2 tests)
✓ tests/copy.spec.ts (7 tests)
✓ tests/states.spec.ts (6 tests)
✓ tests/m1.spec.ts (11 tests)
Test Files  4 passed (4)
Tests       26 passed (26)
```

测试覆盖：空态文案不含 0、只读按钮 disabled、模块阻断文案含模块名、比率标记、分母为零显示不适用、超时/作废文案、证据缺失禁止批准；M1 新增 P03 空态与禁用文案、P02 只读角色隐藏处理按钮、P10 409 五项检查逐项渲染、P11 四层标签、P12 空订阅文案。

## 路由入口

| 页面 | 路由 | 组件 |
| --- | --- | --- |
| P02 评价与口碑 | `/p02` | `src/pages/P02Reviews.vue` |
| P03 库存与补货 | `/p03` | `src/pages/P03Inventory.vue` |
| P10 口径与数据合同 | `/p10` | `src/pages/P10MetricCards.vue` |
| P11 机器人与日志 | `/p11` | `src/pages/P11Workers.vue` |
| P12 权限与订阅 | `/p12` | `src/pages/P12Access.vue` |

五个页面均作为 `AppShell` 子路由挂载；左侧导航仍由后端 `/workbench/nav` 的 `menu / title / roles / available` 驱动，`SideNav` 只补充 `page_id → route` 映射。

## 与规格的差异 / 说明

- `P06` 的批准 / 驳回 / 转交 / 撤回在 M1 仍没有对应前端写调用；非只读场景下点击只提示「M0 仅展示审批流，审批执行动作在后续阶段交付」，本次未改动该页面。
- `GET /reports/latest` 只按平台 / 店铺取最新日报，时间窗与口径版本作为全局上下文参与刷新与展示；后端忽略这两个查询参数时，页面仍按 context 变化重新请求。
- 运行详情中的节点集合完全来自 `GET /runs/{run_id}` 的 `nodes`，页面不伪造 T0~T6；demo 运行会返回 T0~T6。
- `P09` 的禁用按钮在只读模式下仍可用：写入平台经营数据的动作才受 L0 只读闸门约束，模块禁用属于控制面操作，后端同样允许 OWNER 调用。
- 未引入图表库；P02 的 DSR 趋势用纯 CSS 柱状条实现，固定 0~5 刻度，保留 2 位小数。
- `P02` / `P03` 未增加状态筛选器，按接口默认返回展示全部工单 / 差异；KPI 计数来自 summary 或 counts，空态只使用接口 `empty_copy` 原文，不用 0 冒充空态。
- `P10` 的「最近自检」直接使用 `GET /metric-cards` 返回的 `release` 字段；发布失败时再次读取 `details.release.checks`，不伪造检查项。版本对比不传 `from / to`，由后端判断是否存在可比较历史版本。
- `P11` 的 `run_id` 在页面内打开既有 `RunDetailDrawer`，不跳转 P01；没有 run_id 的异常显示 —。
- `P12` 的订阅阈值 JSON 仅接受数字值，空对象表示不设阈值；`silent_window` 为空时传 `null`。`shops` 来自 `identity/roles`，不额外请求凭据接口。
- Element Plus 使用全量样式表（仅使用 ElSelect / ElButton / ElTable / ElTag 及其子组件），便于覆盖下拉、表格等配套样式；JS 侧按需引入组件。
- 外壳品牌从 M0 更新为 M1，左侧导航底部署名同步为 M1；既有 P01 / P05 / P06 / P09 文案与行为保持不变。

## 环境变量

前端仅使用一个可选变量：

```bash
# 默认 /api/v1，由 Vite dev/preview 代理到 127.0.0.1:8000
VITE_API_BASE=/api/v1
```

Vite 配置：

```ts
server: {
  host: '127.0.0.1',
  port: 5173,
  strictPort: true,
  proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true } },
}
```
