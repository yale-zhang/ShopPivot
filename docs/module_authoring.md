# 新增业务模块 SOP（对应主文档表 9-20 的 8 步）

> 目标：**加功能只加模块，底座最多加扩展点**。若一次需求需要改 Run 主链、闸门状态机或统一数据模型，先停下来重新划边界。

## 1. 复制脚手架
```bash
cp -R modules/_template modules/mod_<domain>
```
把 `manifest.name` 改成 `mod_<domain>`，目录名必须与 manifest.name 一致，否则启动期 M01 阻断。

## 2. 写 manifest.py
- `depends` 只写**直接依赖**；业务模块不要依赖具体平台适配器（新增平台应只加 adapter）。
- `api_compat` 与 Kernel 契约版本匹配（当前 `>=1.0,<2.0`）。
- `gate_level_max` 默认 `L0`；提高写入级别必须走变更单 + ReleaseGate + 平台上限调整。
- `requires` 声明能力（`FETCH_HTTP` / `EXPORT_PARSE` / `SQL` / `FS`；M2 起 `BROWSER` / `UIA` / `OCR` / `COM`）与凭据范围。
- `provides` 每项带稳定 ID（`card.*`、`metric.*`、`gate.*`、`health.*`），发布后不可改名。

## 3. 实现扩展点
- 场景：`ScenePackage` 的 `factory` 指向一个类，构造函数接收 manifest 里的 config；`run(ctx)` 只能通过 `RunContext` 端口访问数据与通知。
- 口径卡：`data/metric_cards/*.yaml`，字段见 `docs/contracts/metric_card.schema.json`；公式只允许四则运算与变量名。
- 卡片：`WorkbenchCard` 必须给 `card_id` / `page_id` / `data_endpoint` / `empty_state_copy`。
- 健康检查：零参数工厂返回 `(bool, str)`，失败模块降级 DEGRADED（不阻断其他模块）。

## 4. 登记 data 文件
`data[]` 顺序固定：`security/permissions.csv` → `data/metric_cards/*` → `data/workbench/*` → `data/seed/*`。
**所有实际存在的模块文件都必须登记**，否则启动期 M06 阻断（防「本地能跑、新库装不上」）。

## 5. migrations 与 hooks
- `on_install/on_upgrade/on_uninstall` 必须幂等、可重跑；升级逻辑只放 `migrations/<version>/`。
- 卸载默认保留数据；只有显式 PURGE 才清表。

## 6. 测试
- `tests/modules/` 里补：装第二个模块不改 Kernel、循环依赖阻断、声明越权被拒、禁用无残留。
- 契约测试：新增/修改 Worker API 字段必须同步 `scripts/gen_schemas.py` 与 `docs/contracts/`。
- CQ 自检：每个模块至少两条能力问题（如「零分母是否记不适用」）。

## 7. 本地四步验证
```bash
PYTHONPATH=src:. python3 -m bootstrap.cli modules          # 装配报告
PYTHONPATH=src:. python3 -m bootstrap.cli seed
PYTHONPATH=src:. python3 -m bootstrap.cli run-daily
PYTHONPATH=src:. python3 -m pytest tests/modules -q
```
再验证禁用：`POST /api/v1/modules/<name>/disable`（OWNER），确认卡片/调度/路由贡献摘除、无残留。

## 8. 组合包
成套能力用薄 `bundle_*` 组合包声明 `depends`，**不写业务逻辑**；bundle 的 `provides` 必须为空。

## 禁止事项
- 直接改 Kernel 表结构或跨模块 join。
- 在 Kernel 里写 `if module_x` 分支。
- 模块自行持有写入凭据或直接调用平台页面。
- 把平台字段/状态枚举写进领域模型（必须经 Adapter → CanonicalRecord）。
