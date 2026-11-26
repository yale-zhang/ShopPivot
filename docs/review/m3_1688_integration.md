# 1688 Skill Hub 集成：选品与采购

> 本文分析「1688 Skill Hub + Agent 自动选品/下单」的实际能力边界，并记录店枢的接入实现。
> 结论先行：**选品可以自动化；下单只能做到"采购单 + checkout 创建 + 人工确认支付"，不能也不应代付。**

## 1. 文章与平台事实

微信文章《1688开放了Skill Hub，我用Grok完成了自动选品和下单》描述的是：
1. 在 Agent 中读取 `skill.md`，安装 `1688-shopkeeper` / `1688-distribution` / `1688-utp-shopping` 等 Skill；
2. 用自然语言让 Agent 搜索商品、筛选供应商、比价；
3. 通过 Skill 的 UI 卡片加购、创建 checkout；
4. **由用户在卡片/收银台点击确认并支付**。

关键事实（来自 1688 Skill Hub 文档与 Skill 源码）：
- Skill Hub（`clawhub.1688.com`）是 **Skill 注册表/分发平台**，不是 1688 交易 API；平台 API 提供检索、详情、版本、下载，AK 由平台登录后获取。
- `1688-distribution` 是确定性 Python CLI（`python3 scripts/cli.py ...`），输出 JSON，覆盖选品、商品详情、铺货、订单查询；需要 AK，选品接口是 `distribution_select_offer` / `same_img_offer_search`。
- `1688-utp-shopping` 走 UTP MCP/CLI，覆盖搜品→加购→checkout→支付；**HITL 硬约束**：下单/支付/取消必须由用户在卡片逐次确认，AI 不得代提交；支付在商业体收银台完成。
- 因而"自动下单"的准确含义是 **Agent 完成选品、比价、加购、生成订单确认卡**；最后一步提交/支付仍是人。

## 2. 店枢的接入设计

| 层 | 实现 |
|---|---|
| Skill 注册表 | `SkillHubClient`：搜索/详情/版本/下载；**不自动安装、不自动执行** |
| 选品提供方 | `SourcingProvider`：`Mock1688SourcingProvider`（演示） / `SkillCliSourcingProvider`（调用 1688-distribution CLI，JSON） |
| 采购提供方 | `PurchaseProvider`：`MockPurchaseProvider`（演示） / `UtpPurchaseProvider`（`utp invoke` 创建/查询 checkout，**绝不调用 complete/支付**） |
| 选品场景 | S10：关键词 → 候选 → 规则评分（价格/销量/包邮/起订/品牌风险）→ 落库 |
| 采购动作 | S11 `S11.purchase_order`：L2 计划 → 人工审批 → 创建 checkout → 回读状态；支付人工完成 |
| 页面 | P13 选品与采购：候选表、风险标签、创建采购单、采购单状态与「去 1688 确认支付」 |
| 安全边界 | 品牌未授权禁止采购、起订量校验、命令白名单、无 shell、超时、fail-closed、审计 |

## 3. 配置与使用

```bash
# 演示（默认，无需 AK）
SHOPPIVOT_SOURCE_1688_MODE=mock

# 真实 Skill（需先安装并登录）
# 1) 从 Skill Hub 安装 1688-distribution（手动/受控安装）
#    安装到 .agents/skills/1688-distribution
# 2) 安装并登录 UTP（1688-utp-shopping），确保 utp 可执行
SHOPPIVOT_SOURCE_1688_MODE=cli
SHOPPIVOT_SKILL_1688_DIR=.agents/skills/1688-distribution
SHOPPIVOT_UTP_BIN=utp

# 选品
PYTHONPATH=src:. python3 -m bootstrap.cli run-scene --scene S10
# 或 API：POST /api/v1/sourcing/search {"keyword":"垃圾袋"}
# 采购：POST /api/v1/write-plans（action=S11.purchase_order）→ P06 审批 → 支付人工完成
```

Skill Hub 检索：

```bash
python3 -m bootstrap.cli skills search 选品
python3 -m bootstrap.cli skills detail <skill_id>
```

## 4. 已验证与未验证

**已验证（mock）**
- S10 候选评分与风险标签；品牌未授权/低销量/起订量风险；
- S11 采购计划：L2 闸门、品牌未授权阻断、起订量阻断；
- 审批后只创建 checkout，状态 `AWAITING_PAYMENT`，返回 `continue_url`；
- 采购单查询/刷新；支付状态不回写为已支付；
- 迁移 0007、P13 页面、审计。

**未验证（需外部条件）**
- 真实 1688 AK / Skill CLI 的字段与分页差异；
- UTP checkout 的真实返回结构与 `continue_url`；
- 真实支付状态回读、退款/取消（UTP 为 app-only，系统不代取消）；
- 1688-distribution 的铺货动作（可作为下一步 S12 铺货，复用 L2）。

## 5. 风险与边界

1. **不代付**：支付必须由人完成；系统只创建 checkout 并回读状态。
2. **不自动安装 Skill**：Skill 是第三方代码；安装需人工/受控流程，CLI 调用仅白名单参数。
3. **品牌/侵权**：`isBrandOffer && !isBrandAuth` 直接阻断采购。
4. **数据真实性**：提供方不可用时 fail-closed（E008），不编造候选、不补价。
5. **平台规则**：批量采购/自动化下单需遵守 1688/UTP 规则；上线前做合规评估。
6. **多店/多买家**：AK 是按用户身份，群店采购需每店/每主体独立 AK 与地址，不能共用。

## 6. 下一步

- 用真实 AK 做 1 个关键词、1 个 SKU 的 UAT，校准 CLI 字段与错误码；
- 增加 S12 铺货（`distribute_offer`）作为 L2 动作；
- 采购单与库存/销量联动，做补货建议；
- 支付状态轮询与到货入库；
- 把「选品评分规则」抽成可配置的策略（按类目/店铺）。
