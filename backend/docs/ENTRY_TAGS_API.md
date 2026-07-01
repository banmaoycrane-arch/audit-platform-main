# EntryTag / TagCategory / TagMappingRule API 文档

所有接口前缀：`/api/entry-tags`

FastAPI 自动生成 OpenAPI 文档地址：
- Swagger UI：`http://127.0.0.1:8000/docs`
- ReDoc：`http://127.0.0.1:8000/redoc`

---

## 一、TagCategory 标签维度分类

### 1. 创建分类

```http
POST /api/entry-tags/categories?ledger_id={ledger_id}
```

请求体：

```json
{
  "code": "counterparty",
  "name": "往来单位",
  "description": "客户、供应商、关联方等交易对象",
  "parent_id": null,
  "value_type": "entity",
  "source_table": "counterparties",
  "is_mandatory": false,
  "sort_order": 1
}
```

响应：

```json
{
  "id": 1,
  "code": "counterparty",
  "name": "往来单位"
}
```

### 2. 查询分类树

```http
GET /api/entry-tags/categories?ledger_id={ledger_id}
```

响应：树形结构列表，每个节点包含 `children`。

### 3. 查询单条分类

```http
GET /api/entry-tags/categories/{category_id}
```

### 4. 更新分类

```http
PUT /api/entry-tags/categories/{category_id}
```

### 5. 删除分类

```http
DELETE /api/entry-tags/categories/{category_id}
```

---

## 二、EntryTag 分录标签

### 1. 创建标签

```http
POST /api/entry-tags/tags
```

请求体：

```json
{
  "entry_id": 100,
  "ledger_id": 1,
  "category_code": "counterparty",
  "tag_value": "山西岚县尚德鑫",
  "value_id": null,
  "display_name": "山西岚县尚德鑫",
  "weight": 1.0,
  "tag_source": "manual",
  "confidence": 1.0
}
```

### 2. 查询标签

```http
GET /api/entry-tags/tags?entry_id={entry_id}&ledger_id={ledger_id}&category_code={category_code}
```

### 3. 更新标签

```http
PUT /api/entry-tags/tags/{entry_tag_id}
```

### 4. 删除标签

```http
DELETE /api/entry-tags/tags/{entry_tag_id}
```

### 5. 查询标签历史

```http
GET /api/entry-tags/tags/{entry_tag_id}/history
```

### 6. 按分类聚合标签

```http
GET /api/entry-tags/aggregate/{category_code}?ledger_id={ledger_id}
```

响应示例：

```json
[
  { "tag_value": "A公司", "count": 15, "avg_weight": 1.0 },
  { "tag_value": "B公司", "count": 8, "avg_weight": 1.2 }
]
```

---

## 三、TagMappingRule 标签映射规则

### 1. 创建规则

```http
POST /api/entry-tags/mapping-rules?ledger_id={ledger_id}
```

请求体：

```json
{
  "source_pattern": "100201",
  "source_type": "account_code",
  "target_category_code": "bank_account",
  "target_value": "招商银行",
  "priority": 10,
  "is_regex": false,
  "description": "银行存款-招商银行"
}
```

### 2. 查询规则

```http
GET /api/entry-tags/mapping-rules?ledger_id={ledger_id}&source_type=account_code
```

### 3. 更新规则

```http
PUT /api/entry-tags/mapping-rules/{rule_id}
```

### 4. 删除规则

```http
DELETE /api/entry-tags/mapping-rules/{rule_id}
```

### 5. 应用规则

```http
POST /api/entry-tags/mapping-rules/apply?ledger_id={ledger_id}
```

请求体：

```json
{
  "source_type": "account_code",
  "source_values": ["100201", "100202"],
  "fallback_category_code": "bank_account"
}
```

响应示例：

```json
[
  {
    "source_value": "100201",
    "matched": true,
    "category_code": "bank_account",
    "target_value": "招商银行",
    "target_value_id": null,
    "rule_id": 1,
    "fallback": false
  },
  {
    "source_value": "100202",
    "matched": true,
    "category_code": "bank_account",
    "target_value": "100202",
    "target_value_id": null,
    "rule_id": null,
    "fallback": true
  }
]
```

---

## 四、旧标签导入兼容层

### 导入旧标签

```http
POST /api/entry-tags/import/legacy
```

请求体：

```json
{
  "ledger_id": 1,
  "records": [
    { "entry_id": 1, "raw_tag": "counterparty:山西岚县尚德鑫" },
    { "entry_id": 1, "raw_tag": "project:审计项目2026" },
    { "entry_id": 2, "raw_tag": "未知标签值" }
  ],
  "default_category_code": "legacy",
  "auto_create_category": true
}
```

响应示例：

```json
{
  "total": 3,
  "success": 2,
  "failed": 0,
  "warning": 1,
  "items": [
    {
      "entry_id": 1,
      "raw_tag": "counterparty:山西岚县尚德鑫",
      "status": "success",
      "category_code": "counterparty",
      "tag_value": "山西岚县尚德鑫",
      "message": "导入成功"
    },
    {
      "entry_id": 2,
      "raw_tag": "未知标签值",
      "status": "warning",
      "category_code": "legacy",
      "tag_value": "未知标签值",
      "message": "使用默认分类 legacy 导入"
    }
  ]
}
```

---

## 五、向量同步

### 同步待处理标签到向量库

```http
POST /api/entry-tags/sync-vector?limit=100
```

---

## 六、数据模型说明

### TagCategory（标签维度分类）

| 字段 | 说明 |
|---|---|
| `code` | 分类编码，同一 ledger 下唯一 |
| `name` | 分类名称 |
| `parent_id` | 父分类 ID，支持多级层级 |
| `level` | 层级深度 |
| `value_type` | text / entity / enum |
| `source_table` | 可选主数据来源表 |
| `is_mandatory` | 是否必填 |
| `is_system` | 是否系统内置 |
| `status` | active / disabled / archived |

### EntryTag（分录标签）

| 字段 | 说明 |
|---|---|
| `entry_id` | 关联分录 ID |
| `ledger_id` | 关联账簿 ID |
| `category_id` | 关联分类 ID |
| `tag_value` | 标签值 |
| `value_id` | 关联主数据 ID |
| `display_name` | 展示名称 |
| `weight` | 权重，默认 1.0 |
| `confidence` | 置信度 |
| `tag_source` | 来源：manual / rule / ai / import |
| `vector_pending` | 是否待向量同步 |

### TagHistory（标签历史）

记录每次 create / update / delete 的变更前后值与权重。

### TagMappingRule（映射规则）

| 字段 | 说明 |
|---|---|
| `source_pattern` | 外部模式 |
| `source_type` | account_code / summary / tag |
| `target_category_code` | 内部分类编码 |
| `target_value` | 内部标签值 |
| `priority` | 优先级 |
| `is_regex` | 是否正则 |
