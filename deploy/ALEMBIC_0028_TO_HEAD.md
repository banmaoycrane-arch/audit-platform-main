# 生产 Alembic 0028 → head（含 0035）运维清单

> **Domain**: 运维收口（TD-020）  
> **In Scope**: 同步代码 → 重建镜像 → 备份 → `alembic upgrade head` → schema 审计  
> **Out of Scope**: 不代签 L6、不自动灌生产样例

## 为什么要升

| 层 | Alembic |
|----|---------|
| 本分支 / 合并后代码 tip | **`0035_document_tag_ledger_id`** |
| 生产（2026-07-21 记录） | **`0028_tax_city_egress_pool`** |

中间缺 `0029`–`0035`：

| 版本 | 内容 |
|------|------|
| 0029 | 合同 `deep_analysis` |
| 0030–0033 | 性能索引 / 完整性 / 脏数据清理 / 运维索引 |
| 0034 | 经济事件工单 4 表 |
| **0035** | **DocumentTag.ledger_id（账簿隔离）** |

> 注意：迁移文件打在 **Docker 镜像**里。只改服务器上的 git 文件、不重建 backend，容器内仍是旧迁移树，`upgrade head` 升不到 0035。

## 推荐：本机一键（有 PEM 的 Windows）

密钥默认在：`桌面\xlsx\*\id_banmao.pem`（与 `sync_and_deploy.ps1` 相同）。

在仓库根目录 PowerShell：

```powershell
# 1) 先切到含 0035 的分支并拉最新（本 PR 或已合并 main）
git fetch origin
git checkout cursor/auto-prod-alembic-head-e12f
git pull

# 2) 同步代码 + 全量部署（重建 backend/web + apply schema = upgrade head）
.\deploy\sync_and_deploy.ps1
```

若只想「同步后专门跑带备份的升级脚本」（仍会重建 backend，避免镜像缺迁移）：

```powershell
.\deploy\upgrade_prod_schema_to_head.ps1
```

## 仅在服务器上执行（代码已同步且已 rebuild）

```bash
cd /root/audit-platform-main
AUTO_YES=1 sh deploy/upgrade_prod_alembic_to_head.sh
```

等价日常路径（无交互备份确认，依赖 `apply_prod_schema.sh`）：

```bash
sh deploy/apply_prod_schema.sh
```

## 验收口令

- [ ] `docker exec -w /app/backend deploy-backend-1 alembic current`  
      含 **`0035_document_tag_ledger_id`**
- [ ] `prod_schema_audit.py` **PASS**
- [ ] 四表存在：`economic_events` / `economic_event_entries` / `economic_event_files` / `economic_event_steps`
- [ ] `document_tags` 表有列 **`ledger_id`**
- [ ] 登录 https://47.122.117.76:8443/login 后硬刷新（Ctrl+F5）不 500

## 回滚

```bash
# 替换时间戳为升级脚本打印的 backup 名
docker exec deploy-backend-1 \
  cp /data/backups/finance_audit_YYYYMMDD_HHMMSS.db /data/finance_audit.db
docker restart deploy-backend-1
```

## 责任边界

| 动作 | 谁做 |
|------|------|
| 本机 PEM + 执行 PowerShell / SSH | **有服务器权限的人（你）** |
| Cloud Agent 代跑 SSH | **做不到**（环境无 `id_banmao.pem`） |
| L6 人工签字 | 会计专业用户 |
| 样例账是否灌生产 | 产品决定（建议先 staging） |
