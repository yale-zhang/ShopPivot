# 店枢 ShopPivot · M0/M1/M2（L2 人工闸门）

> 多店归一枢：数据自动归集，决策与签字归人。
> 个人工作室自用；不对外提供服务、不成为多租户产品。架构依据见仓库根目录《店枢_RPA电商自动化运营平台_功能架构与技术架构设计_V241.docx》。

范围：
- **M0（已完成）**：单平台、单店铺、单场景 S01 经营日报，纯只读 L0；不部署桌面池、不调用 `/write`。
- **M1（已完成）**：平台上限 **L1**，新增 S05 评价巡检、S07 库存对账、P02/P03/P10/P11/P12、口径卡发布自检（ReleaseGate）、订阅与 n8n 只读编排 ACL。
- **M2（进行中）**：平台上限 **L2**，新增 L2 写入闸门闭环（WritePlan → 人工审批 → 一次性 WriteToken → 执行 → 回查 → 归档/补偿）；写入动作覆盖 S02 价格批量维护、S03 活动提报（本地模拟页面写入）；新增审批转交与 S04 投放归集/投产比预警（只出建议）；桌面池与真实平台页面写入仍未启用。

目标始终是验证架构骨架与口径可信：`触发 → 三级取数 → 标准化脱敏 → 口径计算/巡检 → 出报/工单/建议 → 推送 → 留痕归档` 全链可用、`run_id` 可反查原始报文。

## 快速开始

```bash
# 0) 自检：确认 python3 指向装了依赖的解释器
make doctor

# 1) 依赖（本机 Python 3.12+）
python3 -m pip install -e ".[dev]"
# 若构建隔离下载卡住，可改用：python3 -m pip install --no-build-isolation -e ".[dev]"

# 2) 建库 + 模块装配 + 种子数据（账号/店铺授权/机器 token）
make seed

# 3) 跑一次 S01 日报（输出 run_id、节点耗时、报表路径）
make demo

# 4) M1：评价巡检 / 库存对账
PYTHONPATH=src:. python3 -m bootstrap.cli run-scene --scene S05
PYTHONPATH=src:. python3 -m bootstrap.cli run-scene --scene S07

# 5) M2 写入闭环（默认 L2；必须人工批准）
PYTHONPATH=src:. python3 -m bootstrap.cli create-price-plan --sku SKU-A --after 79.00
PYTHONPATH=src:. python3 -m bootstrap.cli approve-plan --plan-id <plan_id>
PYTHONPATH=src:. python3 -m bootstrap.cli create-campaign-plan --campaign C-618 --sku SKU-B --price 119.00

# 6) 启动（二选一）
make dev          # 一键：API(8000) + 前端(5173)，自动等待 API 就绪
# 或者两个终端：
#   make serve      # http://127.0.0.1:8000/docs
#   cd frontend && pnpm dev
```

默认数据库是 SQLite（`storage/shoppivot.db`），无 Docker 也能跑。生产/联调切 PostgreSQL：

```bash
make up           # postgres + redis（compose；M0 默认用 SQLite，可不启）
export SHOPPIVOT_DATABASE_URL=postgresql+psycopg2://shoppivot:shoppivot@localhost:5432/shoppivot
make init-db && make seed && make demo
```

## 演示账号（仅 dev）

| 角色 | 账号 | 口令 | 能做什么 |
|---|---|---|---|
| OWNER | `owner` | `owner123` | 全部；模块禁用/启用、审计、原文证据 |
| EDITOR | `editor` | `editor123` | 看板、导出、触发运行（M0 无写入） |
| VIEWER | `viewer` | `viewer123` | 只读 |

非 dev 环境必须通过 `SHOPPIVOT_OWNER_PASSWORD` 等环境变量提供口令，否则 `seed` 拒绝执行。

## 代码结构

```
src/kernel/contracts/     Worker API / ModuleManifest / 扩展点 Protocol / MetricCard 契约
src/kernel/contexts/      7 个限界上下文（orchestration/approval/metric_data/integration/
                          execution/observability/identity），领域层不 import 框架
src/kernel/module_loader.py  Discovery → Resolution → Loading → Mounting → Startup + 8 项强校验
src/kernel/registry.py    扩展点注册表（稳定 ID，禁用按 ID 精确摘除）
src/kernel/persistence/   统一数据模型（ODS/DWD/DWS + 治理表）
src/worker/               Worker API 客户端与心跳进程（M0 执行在控制面进程内）
src/bootstrap/            容器装配、FastAPI、CLI、Celery
modules/                  mod_core / mod_worker_headless / mod_platform_demo / mod_platform_pdd /
                          mod_daily_report / _template
frontend/                 Vue3 + TS 工作台（P01/P05/P06/P09）
tests/                    unit / contract / modules / integration / e2e / security
docs/                     ADR 索引、许可台账、模块手册、契约 schema、验收证据
```

## 关键机制

- **写入分级 L0~L3**：S01 恒 L0；S05/S07 的工单与补货建议为 L1；S02 价格维护为 L2，只能经 WritePlan + 人工批准 + 一次性 WriteToken 执行；`POST /api/v1/write` 对外仍 403，写入必须走 `/write-plans` 审批链路。
- **三级取数**：官方接口 → 后台导出 → 网页兜底。M0 只实现前两级，第三级 fail-closed，绝不绕过鉴权补数。
- **口径版本化**：口径卡是 `modules/mod_daily_report/data/metric_cards/*.yaml`；代码里没有硬编码公式。分母为零记「不适用」，比率类标「不可加」。
- **run_id 贯通**：`指标 → 口径卡 → run_id → ODS 原始证据` 三步下钻；证据默认脱敏，原文仅 OWNER 且留访问审计。
- **模块化**：装第二个模块只加 `modules/` 目录，不改 Kernel；`gate_level_max` 超过平台上限（M0=L0 / M1=L1）的模块启动即拒绝。
- **发布自检**：`POST /api/v1/metric-cards/{code}/release` 跑 5 项检查（公式/映射/策略/探针/证据），任一失败不发布；探针只允许白名单表参数化 SELECT。
- **L2 写入闸门**：`POST /write-plans` 冻结前后值/影响范围/回滚方案 → 运营批准（证据四要素）→ 一次性 WriteToken（哈希入库、单次消费）→ 执行 → 回查一致才归档；参数漂移/校验不一致进失败与补偿，不假装成功。
- **n8n 只读编排**：`POST /api/v1/n8n/command` 仅接受只读/建议 token 与命令白名单（job.start，场景 S01/S05/S07）；画布拿不到写入能力。

## 常用命令

```bash
make test          # 后端全量测试
make verify        # lint + typecheck + 测试 + 文档检查
make web-install   # 前端依赖
make web-dev       # 前端 dev（代理 /api → 127.0.0.1:8000）
make web-build     # 前端构建
python -m bootstrap.cli modules              # 模块装配报告
python -m bootstrap.cli seed                 # 账号/授权/机器 token
python -m bootstrap.cli run-daily --day 2026-11-25
python -m bootstrap.cli run-scene --scene S05 --day 2026-11-25
python -m bootstrap.cli run-scene --scene S07 --day 2026-11-25
python -m bootstrap.cli create-price-plan --sku SKU-A --after 79.00
python -m bootstrap.cli approve-plan --plan-id <plan_id>
python -m bootstrap.cli create-demo-approval --sla-seconds 120   # F-04 演示
python -m bootstrap.cli expire-approvals
PYTHONPATH=src:. python3 -m bootstrap.cli --help
```

## 数据来源

M0 默认 `SHOPPIVOT_PLATFORM_SOURCE=demo`：`mod_platform_demo` 读取 `modules/mod_platform_demo/fixtures/*.csv`（日期占位符 `{D0}`/`{D-1}` 按运行窗口解析），走「后台导出」通道，端到端断言与真实平台一致。
真实拼多多店铺授权到位后：

```bash
export SHOPPIVOT_PLATFORM_SOURCE=pdd
export SHOPPIVOT_PLATFORM=pdd
# 把商家后台导出文件放到 storage/exports/pdd_{order,traffic,ad,review,inventory}.csv
```

`mod_platform_pdd` 的 OpenAPI 通道需要 `PDD_CLIENT_ID/SECRET/ACCESS_TOKEN`，M0 仅留骨架；缺凭据时 fail-closed，不会回退到网页抓取。

## 明确不做（M0）

- 真实平台页面的 L2 写入（当前 S02 用本地受控状态模拟页面写入；桌面池/UIA 未启用）
- S03 活动提报的真实资格/库存/活动互斥校验与平台页面提交
- S04 调价/调预算执行（当前只出建议）与财务回写
- Windows 机器人池、UIA/OCR、桌面会话
- 多平台 Adapter、SKU 映射全量、本体与语义问数
- 多租户、SSO、项目级 RBAC
- n8n 画布拖拽编排（M1 只做命令 ACL 与 compose profile，业务方自助编辑留待 M2）

## 常见问题

### `make seed` 报 `No module named alembic` / 解释器不对
说明当前 `python3` 指向一个没有安装依赖的解释器（最常见：IDE 自动激活了一个空的 `.venv`）。
```bash
make doctor                 # 打印实际使用的解释器与关键依赖版本
deactivate                  # 若终端处于某个 venv 中
which python3               # 应指向已安装依赖的解释器
make seed PYTHON=/path/to/python3   # 或显式指定
```
仓库不提交 `.venv`；如需虚拟环境，请先创建再 `pip install -e ".[dev]"`，不要在空环境里直接 `make`。

### 登录提示「后端服务不可达」
说明 8000 端口没有 API 进程（Vite 代理返回 500/502 时前端会明确提示，而不是泛化的「请求处理失败」）。
```bash
curl -s http://127.0.0.1:8000/api/v1/healthz   # 应返回 {"status":"ok",...}
make serve                                     # 或 make dev 一键启动
```
只启动前端（`pnpm dev`）而不启动后端，就会出现该提示。

## 与文档的已知差异

1. 主文档表 4-1/4.3 仍残留「影刀企业版」表述，但 ADR-02 已锁定开源执行栈；代码按 ADR-02 实现（不引入影刀）。
2. M0 的 headless 执行在控制面进程内完成，`src/worker` 只做能力登记与心跳；Worker API 契约已固定，M2 拆独立执行进程不改契约。
3. `E001~E008` / `LOG-01~05` 定义在外部模板中，本仓库先按出现上下文建临时注册表（`shared/errors/registry.py`），模板齐备后只改该文件。
4. 前端 M0 交付 P01/P05/P06（只读态）/P09；M1 增补 P02/P03/P10/P11/P12；M2 增补 P04/P07。P08 仍为占位并标注后续阶段。

## 安全与合规

- 买家昵称/电话/地址/备注/物流单号/IM 内容默认脱敏；原文证据仅 OWNER 可读且写访问审计。
- 审计表只增不改（PostgreSQL 触发器 + 仓储层无更新/删除方法）。
- 机器 token 只存 sha256；JWT 默认 dev 密钥仅用于本地，部署必须替换。
- 平台接口授权、账号风控、脱敏、L2 人工确认、审计留痕是 P0 红线，不因「自用」降级。
