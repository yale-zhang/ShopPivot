# 模块模板（_template）

复制到 `modules/mod_<domain>/` 后按主文档表 9-20 的 8 步修改。

## 必须遵守
- `depends` 只声明直接依赖；不要为了省事把平台适配器写进业务模块依赖（新增平台应只加 adapter）。
- `provides` 每项带稳定 ID：`card.*` / `metric.*` / `gate.*` / `health.*`，发布后不可改名。
- `data[]` 顺序：`security/permissions.csv` → `data/metric_cards/*` → `data/workbench/*` → `data/seed/*`。
- `gate_level_max` 默认 `L0`；提高写入级别必须走变更单 + ReleaseGate + 平台上限调整。
- `on_install` 不承担升级逻辑，升级只放 `migrations/<version>/`。
- 模块自身表使用 `table_prefix`，禁止跨模块 join。

## 自检
```bash
PYTHONPATH=src:. python3 -m pytest tests/modules -q
```
