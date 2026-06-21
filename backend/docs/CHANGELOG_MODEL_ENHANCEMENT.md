# 模型完善项目 - 变更记录

## 项目概述

**项目名称**：基础资料模型完善与数据追溯链修复  
**执行日期**：2026-06-21  
**涉及版本**：0004 - 0006

---

## 变更清单

### 1. 数据库模型变更

#### 1.1 AccountingEntry 模型扩展（Phase 1）

| 字段 | 类型 | 说明 |
|------|------|------|
| `source_file_id` | Integer, ForeignKey(source_files.id), nullable | 直接追溯到源文件 |
| `entry_source` | String(20), default="auto" | 分录来源：auto/manual |

**业务意义**：
- 实现会计分录到原始资料文件（发票、合同、银行流水等）的直接追溯
- 区分系统自动生成的分录与人工手工录入的分录

#### 1.2 Team 模型增强（Phase 2）

| 字段 | 类型 | 说明 |
|------|------|------|
| `parent_team_id` | Integer, ForeignKey(teams.id), nullable | 上级团队ID |

**业务意义**：
- 支持会计师事务所多层级组织架构
- 实现集团审计中的团队层级管理

#### 1.3 AccountingUnit 模型增强（Phase 3）

| 字段 | 类型 | 说明 |
|------|------|------|
| `entity_id` | Integer, ForeignKey(entities.id), nullable | 关联会计主体 |

**业务意义**：
- 内部核算单位（事业部、部门、项目）可直接追溯到会计主体
- 支持跨主体的内部考核分析

---

### 2. 服务层变更

#### 2.1 导入服务增强（import_service.py）

**变更内容**：
1. `attach_file` 函数：新增自动关联账套ID逻辑
   - 如果 ImportJob 没有 ledger_id，自动从同 organization 的其他 job 推断
2. `_process_accounting_file` 函数：新增分录来源标记
   - 自动设置 `entry_source="auto"`
   - 自动设置 `source_file_id=source_file.id`
   - 自动设置 `ledger_id=source_file.ledger_id`

#### 2.2 项目服务增强（project_service.py）

**新增方法**：
- `get_project_ledgers(db, project_id)`：获取项目关联的所有账套
- `get_consolidated_report(db, project_id, period_start, period_end)`：跨账套汇总报告
  - 按账套分组统计借贷方发生额
  - 按科目汇总借贷方发生额
  - 识别潜在内部交易

#### 2.3 团队路由增强（routes_team.py）

**新增 API**：
- `GET /api/teams/{id}/sub-teams`：查询直接子团队
- `GET /api/teams/{id}/hierarchy?depth=3`：查询团队层级结构

#### 2.4 项目路由增强（routes_project.py）

**新增 API**：
- `GET /api/projects/{id}/consolidated-report`：跨账套汇总报告

---

### 3. 数据库迁移脚本

| 脚本 | 版本 | 内容 |
|------|------|------|
| `0004_add_entry_trace_fields.py` | 0004 | accounting_entries 新增 source_file_id 和 entry_source |
| `0005_add_parent_team_id.py` | 0005 | teams 新增 parent_team_id |
| `0006_add_entity_id_to_accounting_units.py` | 0006 | accounting_units 新增 entity_id |

---

### 4. 数据修复脚本

**脚本路径**：`app/scripts/fix_entry_trace_data.py`

**功能**：
1. 修复 SourceFile 表中 ledger_id 为空的记录
2. 修复 AccountingEntry 表中 entry_source 为空的记录

---

### 5. 角色体系扩展

**文件**：`models/project_member.py`

**新增 AUDIT_ROLES 常量**：
```python
[
    "partner",    # 合伙人/项目负责人
    "manager",    # 经理/高级经理
    "senior",     # 高级审计员
    "staff",      # 审计员/初级人员
    "reviewer",   # 复核人
    "viewer",     # 查看者
    "leader",     # 现场带队（兼容旧角色）
    "member",     # 普通成员（兼容旧角色）
]
```

---

## 部署步骤

### 步骤 1：执行数据库迁移

```bash
cd backend
alembic upgrade head
```

### 步骤 2：执行数据修复

```bash
cd backend
python -m app.scripts.fix_entry_trace_data
```

### 步骤 3：验证 API 可用性

```bash
# 测试跨账套汇总 API
curl http://localhost:8000/api/projects/1/consolidated-report

# 测试团队层级 API
curl http://localhost:8000/api/teams/1/hierarchy
```

---

## 回滚方案

如需回滚，执行以下命令：

```bash
# 回滚到迁移前版本
alembic downgrade 0003
```

---

## 注意事项

1. **向后兼容**：所有新增字段均为 nullable 或有默认值，不影响现有数据
2. **性能影响**：跨账套汇总查询可能涉及大量数据，建议添加分页和缓存
3. **数据一致性**：数据修复脚本仅处理历史数据，新数据通过服务层自动维护

---

## 测试验证

| 测试项 | 结果 |
|--------|------|
| AccountingUnit 模型导入 | 通过 |
| AUDIT_ROLES 常量验证 | 通过 (8个角色) |
| 导入服务模块导入 | 通过 |
| 项目服务模块导入 | 通过 |

---

**文档编写日期**：2026-06-21  
**文档版本**：v1.0
