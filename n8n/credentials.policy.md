# n8n 业务编排面 · 凭据策略与命令白名单（M1）

## 定位
n8n 只是**业务编排面**（画布、定时、Wait 审批交互壳），不是执行面，也不是安全边界。
执行仍由控制面 Kernel 与 Worker API 完成；写入凭据只由闸门服务持有。

## 启动
```bash
docker compose -f deploy/docker-compose.yml --profile n8n up -d n8n
# http://127.0.0.1:5678
```

## 命令白名单（唯一入口）
`POST /api/v1/n8n/command`，请求头 `X-Api-Token: <只读/建议 token>`。

```json
{"command": "job.start", "scene": "S01", "day": "2026-11-25", "requested_by": "canvas"}
```

- 允许的 token scope：`READONLY` / `SUGGEST`；写入类 token 一律拒绝。
- 允许的命令：仅 `job.start`；允许场景：`S01` / `S05` / `S07`。
- 每次放行/拒绝都写 `n8n_command_log` 与审计；不接受画布直调 `/write`。
- 只读 token 可触发只读/内部记录类场景（S01/S05/S07），但画布仍无法审批 L2、无法签发 WriteToken。

token 获取：`python -m bootstrap.cli seed` 会在 `storage/worker.token` 生成只读 token（文件权限 600）。

## 红线
1. 画布凭据库**只放只读/建议 token**，绝不放入写入凭据、平台账号口令或机器人会话。
2. 不把 n8n 编辑器 / Webhook 暴露到公网；仅内网或本机访问。
3. 社区版无 RBAC、工作流与凭据全局可见：风险按「防自己误操作」处理，命令白名单必须开启。
4. Wait 节点只是暂停/恢复的交互壳，**不是安全边界**；写入强校验在 Worker 侧。
5. 升级前复核 n8n 许可证与版本功能（主文档 ADR-15 三触发器）。
