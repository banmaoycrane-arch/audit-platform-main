# datetime 代码审查标准

## 1. 概述

本标准规定了财务向量审计系统中日期时间处理的代码审查要求，确保跨系统、跨环境的时间处理一致性，避免因时区问题导致的数据错误。

## 2. 核心原则

### 2.1 时区感知原则

**所有涉及日期时间处理的代码必须使用时区感知的模式**，禁止使用不带时区信息的方法。

### 2.2 UTC 优先原则

**系统内部统一使用 UTC 时间**，仅在展示层转换为用户本地时区。

## 3. 强制规则

### 3.1 禁止使用的方法

以下方法**严格禁止**在代码中使用：

| 禁止方法 | 原因 | 替代方案 |
|---------|------|---------|
| `datetime.utcnow()` | 已弃用，将在 Python 3.12+ 移除 | `datetime.now(timezone.utc)` |
| `datetime.now()` | 不带时区信息，导致时区不一致 | `datetime.now(timezone.utc)` |
| `datetime.fromtimestamp(timestamp)` | 不带时区信息 | `datetime.fromtimestamp(timestamp, timezone.utc)` |
| `datetime.strptime(date_str, format)` | 返回无时区 datetime | 使用 `dateutil.parser.isoparse()` 或手动添加时区 |

### 3.2 强制使用的模式

所有日期时间创建必须使用时区感知模式：

```python
# ✅ 正确：使用 timezone.utc
from datetime import datetime, timezone

current_time = datetime.now(timezone.utc)
created_at = datetime.now(timezone.utc)

# ✅ 正确：从时间戳创建时指定时区
from_timestamp = datetime.fromtimestamp(timestamp, timezone.utc)

# ✅ 正确：SQLAlchemy 模型字段定义
from sqlalchemy import DateTime
from sqlalchemy.sql import func

class MyModel(Base):
    created_at = Column(DateTime(timezone=True), default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

### 3.3 导入规范

使用 `timezone` 时必须显式导入：

```python
# ✅ 正确：显式导入 timezone
from datetime import datetime, timezone

# ❌ 错误：缺少 timezone 导入
from datetime import datetime
```

### 3.4 时区转换规则

如需在 UTC 和本地时区之间转换：

```python
# UTC → 本地时区
local_time = utc_time.astimezone()

# 本地时区 → UTC
utc_time = local_time.astimezone(timezone.utc)

# 指定目标时区
from zoneinfo import ZoneInfo
beijing_time = utc_time.astimezone(ZoneInfo("Asia/Shanghai"))
```

## 4. 代码审查检查清单

### 4.1 必查项

审查时必须检查以下内容：

- [ ] 所有 `datetime.now()` 调用是否已替换为 `datetime.now(timezone.utc)`
- [ ] 所有 `datetime.utcnow()` 调用是否已完全移除
- [ ] 使用 `timezone.utc` 的文件是否已正确导入 `timezone`
- [ ] 数据库模型中日期时间字段是否使用 `DateTime(timezone=True)`
- [ ] 时区转换逻辑是否正确（特别是 UTC ↔ 本地时区）
- [ ] 跨系统时间传递是否使用 ISO 8601 格式（带时区信息）

### 4.2 审查工具

可以使用以下命令进行自动化检查：

```bash
# 检查未替换的 datetime.utcnow()
grep -r "datetime\.utcnow()" app/

# 检查缺少 timezone 导入的文件
python validate_batch_replace.py

# 运行 mypy 静态类型检查
python -m mypy app/ --config-file pyproject.toml
```

## 5. CI/CD 集成

### 5.1 静态检查

CI/CD 流程中必须包含以下检查：

1. **批量替换验证脚本**：`python validate_batch_replace.py`
2. **mypy 类型检查**：`python -m mypy app/ --config-file pyproject.toml`
3. **代码审查标准检查**：检查 `datetime.utcnow()` 和 `datetime.now()` 的使用

### 5.2 阻断条件

以下任何情况都应阻断构建流程：

- [ ] 发现未替换的 `datetime.utcnow()` 调用
- [ ] 发现使用 `timezone.utc` 但未导入 `timezone` 的文件
- [ ] mypy 报告错误级别问题
- [ ] 核心测试套件失败

## 6. 常见错误案例

### 6.1 错误案例 1：缺少 timezone 导入

```python
# ❌ 错误
from datetime import datetime
voucher.updated_at = datetime.now(timezone.utc)  # NameError: name 'timezone' is not defined

# ✅ 正确
from datetime import datetime, timezone
voucher.updated_at = datetime.now(timezone.utc)
```

### 6.2 错误案例 2：使用已弃用的方法

```python
# ❌ 错误
expire = datetime.utcnow() + timedelta(minutes=60)  # DeprecationWarning

# ✅ 正确
expire = datetime.now(timezone.utc) + timedelta(minutes=60)
```

### 6.3 错误案例 3：数据库字段未指定时区

```python
# ❌ 错误
created_at = Column(DateTime)  # 不带时区信息

# ✅ 正确
created_at = Column(DateTime(timezone=True))  # 带时区信息
```

## 7. 责任与执行

### 7.1 开发人员责任

- 编写代码时严格遵守本标准
- 提交代码前运行验证脚本
- 确保新增代码符合时区感知要求

### 7.2 代码审查人员责任

- 审查时检查所有日期时间处理代码
- 对违反标准的代码要求修改
- 确保时区转换逻辑的正确性

### 7.3 CI/CD 责任

- 自动化检查违反标准的代码
- 任何错误级别问题阻断构建
- 生成详细的错误报告

---

**文档版本**：1.0  
**创建日期**：2026-07-02  
**适用范围**：财务向量审计系统后端 Python 代码
