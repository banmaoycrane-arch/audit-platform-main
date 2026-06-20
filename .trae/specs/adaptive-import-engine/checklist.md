# 自适应文件导入引擎 - 验收清单

## Phase 1: 格式模板系统
- [x] `format_template.py` 已创建
- [x] 支持中文/英文模板
- [x] 支持字段别名映射
- [x] 模板可扩展

## Phase 2: 字段映射引擎
- [x] `file_parser_service.py` 已重构
- [x] 基于模板的智能映射
- [x] 表头行自动检测
- [x] 映射失败时返回 unknown

## Phase 3: 数据验证
- [x] `data_validator.py` 已创建
- [x] 必填字段检查
- [x] 质量评分功能
- [x] 导入报告生成

## Phase 4: 流程分离
- [x] `import_service.py` 已重构
- [x] 凭证处理独立路径
- [x] 原始文件处理独立路径
- [x] 流程可追踪

## Phase 5: AI 辅助（可选）
- [x] `ai_assist_mapping()` 函数已实现
- [x] AI 映射结果可缓存

## Phase 6: 前端展示
- [x] 导入报告页面
- [x] 质量评分展示
- [x] 异常分录标记

## Phase 7: 凭证字自动推荐
- [x] `suggest_voucher_type()` 函数已实现
- [x] 支持银/现/转/记 四种凭证字
- [x] 根据科目和摘要智能识别
- [x] 集成到标签推荐中

## 测试验证
- [x] 导入标准格式 CSV 成功
- [x] 导入自定义格式 CSV 成功
- [x] 质量评分正确显示
- [x] 前端报告展示页面/API client 已实现，浏览器 E2E 待环境
- [x] 凭证字推荐功能正常
