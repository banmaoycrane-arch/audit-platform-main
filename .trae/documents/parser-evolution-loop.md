# Parser Evolution Loop（生产机制）

> **定位**：上线后持续运行的产品机制，不是上线前集中训练。  
> **更新**：2026-07-05  
> **Status**: production-v1

---

## 一、双通道架构

```text
┌─────────────────────────────────────────────────────────────┐
│  主信号（生产）                                              │
│  上传 → 解析 → 用户改错 → ParseCorrection                    │
│       → 自动 enqueue draft 提案（regex / mapping / 字段兜底） │
└───────────────────────────────┬─────────────────────────────┘
                                ▼
                    draft ParsingRulePatch 队列
                                │
                                ▼  审批台批量采纳 / 驳回
┌─────────────────────────────────────────────────────────────┐
│  active 规则库 → 下次同型文档解析自动加载                    │
└───────────────────────────────┬─────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────┐
│  标尺（nightly）                                             │
│  TOP3 固定样本 → 只测质量指标 → 防退化，不自动激活规则        │
└─────────────────────────────────────────────────────────────┘
```

| 通道 | 触发 | 产出 | 是否自动激活 |
|------|------|------|--------------|
| **生产改错** | 每次 `POST /corrections` | draft 提案 | 否，需审批 |
| **TOP3 扫描** | 可选 `POST /evolution/run` | column_header 提案 | 否 |
| **Nightly 回归** | cron `run_nightly_parser_evolution.py` | 质量 JSON 报告 | 否 |

**不是**：无人值守自动改生产规则。  
**不是**：用 TOP3 替代真实业务改错。

---

## 二、代码入口

| 组件 | 路径 |
|------|------|
| 进化服务 | `parser_evolution_service.py` |
| 修正入队 | `create_correction_record()` → `enqueue_proposals_from_correction()` |
| 生产修正 API | `POST /api/parser-engine/corrections`（可选 `original_text`） |
| 提案列表 | `GET /api/parser-engine/evolution/proposals?status=draft` |
| 批量采纳 | `POST /api/parser-engine/evolution/proposals/batch-approve` |
| Nightly 回归 | `POST /api/parser-engine/evolution/nightly-regression` |
| Nightly CLI | `backend/scripts/run_nightly_parser_evolution.py` |
| TOP3 扫描 CLI | `backend/scripts/run_parser_evolution.py` |
| 前端审批台 | `/parser-engine/evolution` |
| Nightly 报告 | `samples/top3/evolution/nightly_regression.json` |

---

## 三、规则类型

| rule_type | 来源 | 说明 |
|-----------|------|------|
| `regex` | 生产改错 | 从原文 + 修正值生成 |
| `mapping` | 生产改错 | 原值 → 修正值精确映射 |
| `production_field` | 生产改错兜底 | 无法自动提取时，字段级提案 |
| `column_header` | TOP3 扫描 | Excel 表头 → 标准字段 |

生产提案 meta 示例：

```json
{
  "source": "production_correction",
  "file_name": "苏小西工行.xlsx",
  "field": "counterparty_name",
  "original_value": "",
  "corrected_value": "某某公司",
  "correction_id": 42
}
```

---

## 四、你的操作（每周 5–10 分钟）

1. 打开 **解析进化审批台**，查看「生产改错」与「TOP3 扫描」提案。
2. 勾选可信提案 → **批量采纳**。
3. （可选）驳回明显错误映射。
4. （可选）查看 nightly 报告，确认 TOP3 质量未退化。

---

## 五、云端定时（建议）

```bash
# 03:00 nightly 回归（标尺）
cd backend && python scripts/run_nightly_parser_evolution.py

# 02:00 可选：TOP3 column_header 扫描提案
cd backend && python scripts/run_parser_evolution.py
```

或通过 HTTP：

```http
POST /api/parser-engine/evolution/nightly-regression
POST /api/parser-engine/evolution/run
```

---

## 六、与 ParseCorrection 的关系

- 共用 `parse_correction` + `parsing_rule_patch` 表
- **创建修正即入队**，无需再手动点「提取规则」
- `extract-rules` 接口保留，供补跑或调试
- 采纳走 evolution 审批台（或 corrections apply），统一写入 `active`

---

## 七、审计

- 生产提案带 `source_correction_id`、`file_name`
- TOP3 提案带 `run_id`、`evidence_file`、`shadow_note`
- nightly 报告带 `delta_vs_previous`（相对上次 journal/bank 指标）
