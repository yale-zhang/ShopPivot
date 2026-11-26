# Skill 运行时（S0/S1）验收与说明

## 定位

把外部 Skill（1688 Skill Hub 等）提升为平台能力：业务模块声明 capability，运行时负责目录、信任/风险校验、执行路由、运行记录。S0/S1 范围：**只读目录 + 运行时 + 迁移 S10**，安装/启用/绑定留 S2。

## 组成

| 层 | 实现 |
|---|---|
| 领域 | `kernel/contexts/skill/domain/models.py`：SkillManifest、SkillCapability、SkillBinding、SkillRun、SkillOutput、TrustLevel、SkillRisk |
| 目录 | `infrastructure/catalog.py`：读取 `skills.lock` 与 `skills/adapters/*.yaml`，校验版本/能力/风险/适配器 |
| 运行时 | `application/runtime.py`：能力路由、信任/风险校验、适配器执行、`skill_run` 记录 |
| Runner | `infrastructure/runners.py`：CLI 子进程（无 shell、环境白名单、超时） |
| 数据 | `skill_run` 表；迁移 0008 |
| 业务模块 | `mod_skill_hub`：P14 卡片、健康、CQ（只读） |
| 1688 适配 | `modules/mod_1688_ops/skill_adapter.py`：仅字段映射；S10 通过 `ctx.skills.execute("sourcing.search")` |
| 页面/API | `skill_router.py`：`/skills/catalog`、`/skills/{id}`、`/skills/runs`；P14 只读 |

## 锁文件与清单

- `skills.lock` 固定 id/version/manifest/checksum/status/binding；当前两条均为 `adapter-only`，真实安装后替换为包校验和。
- `skills/adapters/1688-distribution.yaml`：`sourcing.search`（L0，official）。
- `skills/adapters/1688-utp-shopping.yaml`：`purchase.checkout`（L2，official）；S11 尚未迁移到 Runtime（S2）。

## 安全边界

- 运行时拒绝 `L3`（支付/财务）能力；社区 Skill 只能 L0；未信任 Skill 不可执行。
- 风险超过平台上限时 fail-closed。
- 适配器不可用/提供方失败 → `E008`，不编造候选。
- `SkillOutput` 只作为数据，不进入控制面指令流。
- CLI runner 无 shell、环境变量白名单、超时；真实 Skill 的沙箱强化在 S2。

## 验收

- 目录加载/版本不一致拒绝：`tests/integration/test_skill_runtime.py`。
- S10 经 Runtime 执行并写入 `skill_run`（skill/version/capability/status/digest/latency）。
- `/skills/catalog`、`/skills/{id}`、`/skills/runs` OWNER 可读，VIEWER 403。
- 迁移 0001→0008 全新库通过。
- 前端 P14 只读，无安装/执行入口。

## 未完成（S2+）

1. 安装/校验/启用/停用/绑定/升级/回滚 API 与 P14 操作。
2. 校验和/签名、发布者白名单、凭据引用/加密、社区 Skill 隔离。
3. UTP MCP Runner 与 S11 迁移。
4. 按店铺限流、成本、灰度、死信。
5. 契约测试包与适配清单模板。

## S2a（已落地）：生命周期与按店铺绑定

- **安装（清单级）**：`POST /skills/{id}/install` 计算 manifest SHA256，校验发布者白名单/信任等级/社区 Skill 仅 L0；写入 `skill_installation`。
- **校验**：`POST /skills/{id}/verify` 重算并对比，返回 expected/actual。
- **启用/停用**：`ENABLED`/`DISABLED`；Runtime 对 DISABLED/FAILED 直接拒绝（E008）。
- **绑定**：`skill_binding` 按 `(skill_id, platform, shop_id)` 唯一；`GET/PUT/DELETE /skills/{id}/bindings`；`credential_ref` 只存引用，不存明文。Runtime 优先使用动态绑定（禁用则拒绝），无动态绑定时回退 `skills.lock` 静态绑定。
- **审计**：install/verify/enable/disable/bind/unbind 全部写审计。
- **迁移**：`0009_skill_lifecycle.py`（skill_installation / skill_binding）。
- **验证**：`test_skill_runtime.py` 覆盖安装/校验/停用阻断/启用恢复、绑定禁用阻断/启用恢复/删除；后端 132 用例。
- **边界**：当前是清单级安装，真实 zip 包的下载/解压/签名在 S2b；P14 操作由 OWNER 完成。

## S2b-1（已落地）：安装包与 S11 迁移

- **安装包安装**：`POST /skills/{id}/install` 支持 `{source:"package", package_path:"xxx.zip"}`；包只能放在 `storage/skill_packages/` 下。
  - 安全解压：拒绝绝对路径、`..`、符号链接、超量文件/体积（500 文件 / 50MB）。
  - 校验：zip SHA256（锁文件非 adapter-only 时强校验）、包内 `skill.yaml` 的 id/version/adapter 必须与登记清单一致。
  - 落盘：`storage/skills/<id>/<version>/`；记录 manifest checksum 与 package checksum；**不自动执行包内脚本**。
- **S11 迁移**：采购通过 `ctx.skills.execute("purchase.checkout")` 走 Runtime；状态回读走 `purchase.status`，取消走 `purchase.cancel`；S11 运行写入 `skill_run`。
- **UTP 适配**：mock 与 CLI 均由 `UtpPurchaseAdapter` 承接；真实 UTP 仍受 HITL 约束，不代提交/代付。
- **测试**：新增安装包/zip-slip/路径越界、S11 skill_run 断言；后端 133 用例。

## 仍未完成

1. Skill Hub 在线下载（当前只接受本地受控目录 zip）；签名/发布者公钥校验。
2. `credential_ref` 解析（Vault/加密）与按店凭据注入。
3. 按店限流/并发/灰度/成本；升级/回滚 UI。
4. 真实 UTP MCP Runner（当前 CLI 适配器）。
