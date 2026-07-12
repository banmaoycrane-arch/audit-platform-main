# 代码 + 数据层统一上线流程

生产环境必须保证：**Docker 镜像里的代码** 与 **SQLite 卷里的表结构** 与 **SQLAlchemy 模型** 三者一致。只同步代码、不跑 schema 补丁，会出现「页面能开、一登录就系统异常」。

## 环境

| 项目 | 值 |
|------|-----|
| 服务器 | `root@47.122.117.76` |
| 代码目录 | `/root/audit-platform-main` |
| Compose | `/root/audit-platform-main/deploy` |
| 数据库 | Docker 卷内 `/data/finance_audit.db` |
| SSH 密钥 | `C:/Users/banmao/Desktop/xlsx/工作空间部署方案/id_banmao.pem` |

## 标准流程（推荐）

```
本地改代码
    ↓
sync_and_deploy.ps1（打包上传 + 远程一键部署）
    ↓
prod_deploy_full.sh
    ├─ 1. 无缓存重建 backend 并启动
    ├─ 2. apply_prod_schema.sh（数据层）
    │      ├─ fix_legacy_db.py（legacy 库补列）
    │      ├─ alembic upgrade head（若有 alembic_version）
    │      └─ prod_schema_audit.py（模型对照，失败则阻断）
    ├─ 3. 重建 web 并启动
    └─ 4. health + API 冒烟
    ↓
浏览器 Ctrl+F5 硬刷新
```

### Windows 一键（本地执行）

```powershell
cd e:\projects\finance-vector-audit\audit-platform-main
.\deploy\sync_and_deploy.ps1
```

### 仅服务器端（代码已上传后）

```bash
ssh -i <pem> root@47.122.117.76 "sh /root/audit-platform-main/deploy/prod_deploy_full.sh"
```

### 仅补数据层（不改代码）

```bash
ssh -i <pem> root@47.122.117.76 "sh /root/audit-platform-main/deploy/apply_prod_schema.sh"
```

## 审计脚本说明

| 脚本 | 作用 |
|------|------|
| `deploy/prod_schema_audit.py` | **全量**：所有模型表/列 vs 生产 DB，失败 exit 1 |
| `deploy/audit_model_schema.py` | 同上（精简输出） |
| `deploy/fix_legacy_db.py` | legacy 库手工补列（须与 Alembic 迁移保持同步） |
| `deploy/apply_prod_schema.sh` | 补丁 + 可选 Alembic + 审计 |

## 2026-07-08 生产库审计结果（修复后）

| 检查项 | 结果 |
|--------|------|
| 模型表缺失 | 0 |
| 模型列缺失 | 0 |
| 功能表（staging / parse_quality / vouchers） | 全部存在 |
| `alembic_version` | **缺失**（legacy 库，靠 `fix_legacy_db.py` 维护） |
| DB 表总数 | 116 |

**已修复的历史问题：** `ledgers.is_working`、`ledgers.project_id` 缺失导致登录后 `/api/auth/context` 500。

**当前风险：** 今后若在模型里新增字段，必须同时更新 `backend/alembic/versions/` **和** `deploy/fix_legacy_db.py`，并在部署时跑 `apply_prod_schema.sh`。否则 legacy 生产库会再次漂移。

## 开发者检查清单（每次改数据库相关代码）

1. 新增/修改模型字段 → 写 Alembic migration（`alembic revision`）
2. 同步更新 `deploy/fix_legacy_db.py` 的 `PATCHES`（legacy 生产仍依赖它）
3. 本地 `alembic upgrade head` 验证
4. 部署时用 `prod_deploy_full.sh`，确认 `prod_schema_audit.py` 输出 `PASS`

## 迁移到正式 Alembic（一次性）

legacy 库（无 `alembic_version`）升级为 Alembic 跟踪：

```bash
ssh -i <pem> root@47.122.117.76 "sh /root/audit-platform-main/deploy/migrate_to_alembic.sh"
```

脚本会：备份 DB → schema 审计 PASS → `alembic stamp head` → `alembic upgrade head`（无操作）→ 再审计。

**迁移后**每次部署的 `apply_prod_schema.sh` 会自动执行 `alembic upgrade head`。`fix_legacy_db.py` 仍作为 legacy 补列兜底保留，直至所有环境均已 stamp。

## 禁止事项

- 不要只 `docker compose build` 而不跑 schema 审计
- 不要用 tar 覆盖 `deploy/.env`（含生产密钥）
- 不要在生产直接改 SQLite 文件而不备份
