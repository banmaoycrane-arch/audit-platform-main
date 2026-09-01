# 生产 Alembic 0028 → 0034 运维清单

> **Domain**: 运维收口（配合 D14 经济事件）  
> **In Scope**: 备份、升级、审计、验收检查项  
> **Out of Scope**: 不代签 L6、不自动灌生产样例（样例脚本另见 `scripts/seed_demo_ledger.py`）

## 为什么要升

| 层 | Alembic |
|----|---------|
| 代码 `origin/main` | `0034_add_economic_event_workorder` |
| 生产（2026-07-21 记录） | `0028_tax_city_egress_pool` |

中间缺 `0029`–`0034`（合同 deep_analysis、性能索引、完整性约束、脏数据清理、运维索引、**经济事件 4 表**）。

## 执行步骤（生产机）

```bash
cd /root/audit-platform-main   # 或实际仓库路径
git pull
sh deploy/upgrade_prod_alembic_to_0034.sh
```

脚本会：

1. 检查容器 `deploy-backend-1`
2. 打印当前 alembic
3. 备份 `/data/finance_audit.db` → `/data/backups/finance_audit_*.db`
4. 跑 `fix_legacy_db.py`（含 `contracts.deep_analysis` + 经济事件表兜底）
5. `alembic upgrade head`
6. `prod_schema_audit.py`
7. 校验 `economic_events` 等 4 表存在

也可日常部署走原有路径（效果等价，但无交互确认）：

```bash
sh deploy/apply_prod_schema.sh
```

## 验收口令

- [ ] `alembic current` = `0034_add_economic_event_workorder`
- [ ] schema 审计 PASS
- [ ] 四表存在：`economic_events` / `_entries` / `_files` / `_steps`
- [ ] 登录后打开「经济事件」页不 500
- [ ] （可选）跑样例账：`python scripts/seed_demo_ledger.py`

## 回滚

用备份文件覆盖容器内 DB（需停写或短暂维护窗）：

```bash
# 示例：把备份拷回（请替换时间戳）
docker exec deploy-backend-1 \
  cp /data/backups/finance_audit_YYYYMMDD_HHMMSS.db /data/finance_audit.db
docker restart deploy-backend-1
```

## 责任边界

| 动作 | 谁做 |
|------|------|
| SSH 执行本脚本 | 运维 / 有服务器权限的人 |
| L6 人工签字 | 会计专业用户 |
| 样例账是否灌生产 | 产品决定（建议先 staging） |
