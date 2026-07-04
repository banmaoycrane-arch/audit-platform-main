# Tasks

## 第一阶段 MVP（6 周）

- [ ] Task 1: 技术预研与样本准备
  - [ ] SubTask 1.1: 整理 50 份含印章的真实合同扫描件测试样本（覆盖清晰、模糊、重叠、倾斜、红/蓝章）
  - [ ] SubTask 1.2: 调研并确认传统 CV 印章检测方案（HSV 颜色分割 + 轮廓检测）与 PaddleOCR fallback 方案
  - [ ] SubTask 1.3: 输出《印章识别技术预研报告》与基线测试结果

- [ ] Task 2: 后端印章检测与提取服务
  - [ ] SubTask 2.1: 创建 `backend/app/services/seal_detection_service.py`，实现基于 HSV 颜色与轮廓的印章区域检测
  - [ ] SubTask 2.2: 创建 `backend/app/services/seal_extraction_service.py`，实现印章裁剪、去噪、倾斜校正、对比度增强
  - [ ] SubTask 2.3: 实现 PaddleOCR fallback 检测入口，并在结果中标记 detection_method
  - [ ] SubTask 2.4: 为检测与提取服务编写单元测试，覆盖正常、无印章、模糊印章场景

- [ ] Task 3: 后端印章 OCR 识别与坐标关联服务
  - [ ] SubTask 3.1: 创建 `backend/app/services/seal_ocr_service.py`，复用现有 EasyOCR/PaddleOCR 框架识别印章文字
  - [ ] SubTask 3.2: 实现环形文字按角度重组为完整字符串
  - [ ] SubTask 3.3: 建立每个识别文字的原始像素坐标记录
  - [ ] SubTask 3.4: 为 OCR 服务编写单元测试，覆盖清晰印章、模糊印章、无文字印章场景

- [ ] Task 4: ContractSeal 数据模型与持久化
  - [ ] SubTask 4.1: 在 `backend/app/db/models.py` 新增 `ContractSeal` 表映射（含 id、contract_id、source_file_id、page_no、bbox、seal_image_path、recognized_text、text_items、seal_type、confidence、detection_method、created_at、updated_at）
  - [ ] SubTask 4.2: 创建 `backend/app/models/contract_seal.py` Pydantic 模型
  - [ ] SubTask 4.3: 生成并执行 Alembic 迁移脚本
  - [ ] SubTask 4.4: 编写数据模型单元测试

- [ ] Task 5: 后端印章 API
  - [ ] SubTask 5.1: 创建 `backend/app/api/routes_seals.py`，实现 `POST /contracts/{contract_id}/seals/extract`
  - [ ] SubTask 5.2: 实现 `GET /contracts/{contract_id}/seals` 分页列表接口
  - [ ] SubTask 5.3: 实现 `GET /seals/{seal_id}` 详情接口
  - [ ] SubTask 5.4: 在 `main.py` 注册路由
  - [ ] SubTask 5.5: 使用 FastAPI 测试客户端编写 API 集成测试

- [ ] Task 6: 前端"印章证据"区域 UI 预留
  - [ ] SubTask 6.1: 在合同详情页新增"印章证据"页签
  - [ ] SubTask 6.2: 设计并实现左右分栏布局（左侧原图/预览 + bbox 高亮，右侧印章列表）
  - [ ] SubTask 6.3: 预留印章数据 TypeScript 类型定义（SealTextItem、ContractSeal）
  - [ ] SubTask 6.4: 在前端 API client 中预留印章相关方法
  - [ ] SubTask 6.5: 实现无印章数据时的友好空状态展示
  - [ ] SubTask 6.6: 通过前端 TypeScript 类型检查与 build

- [ ] Task 7: 数据安全与审计日志
  - [ ] SubTask 7.1: 在印章提取与查询接口中校验用户合同访问权限
  - [ ] SubTask 7.2: 记录印章提取操作的审计日志（操作人、时间、合同 ID、结果摘要）
  - [ ] SubTask 7.3: 印章图片通过受控接口或签名 URL 访问，不暴露原始服务器路径

- [ ] Task 8: 测试与验收
  - [ ] SubTask 8.1: 后端单元测试与集成测试覆盖率达到 ≥80%
  - [ ] SubTask 8.2: 在 50 份样本上统计印章检出率、误检率、文字识别准确率、坐标误差
  - [ ] SubTask 8.3: 修复准确率不达标的问题，或制定 fallback/人工复核策略
  - [ ] SubTask 8.4: 更新 API Swagger 文档

## 第二阶段 多模态 LLM 关联校验（4 周）

- [ ] Task 9: LLM 校验提示词工程
  - [ ] SubTask 9.1: 设计多模态 LLM 提示词模板，输入印章子图 + 文字 + 合同主体列表
  - [ ] SubTask 9.2: 定义输出 JSON Schema（seal_type、associated_party、confidence、anomalies）
  - [ ] SubTask 9.3: 在 20 份样本上验证提示词效果并迭代

- [ ] Task 10: LLM 校验服务
  - [ ] SubTask 10.1: 创建 `backend/app/services/seal_verification_service.py`
  - [ ] SubTask 10.2: 实现批量校验、失败重试、结果缓存
  - [ ] SubTask 10.3: 将校验结果写入 ContractSeal 模型扩展字段

- [ ] Task 11: 结果融合与人工复核队列
  - [ ] SubTask 11.1: 融合 OCR 识别结果与 LLM 校验结果
  - [ ] SubTask 11.2: 对冲突或低置信度结果生成"需人工复核"标记
  - [ ] SubTask 11.3: 前端增加复核操作入口（确认正确、标记异常、人工修正）

## 第三阶段 规则引擎与知识库匹配（6 周）

- [ ] Task 12: 印章规则库
  - [ ] SubTask 12.1: 设计可配置规则结构（合同金额阈值、印章类型限制、财务章禁用场景等）
  - [ ] SubTask 12.2: 实现规则引擎，支持至少 10 条规则配置化扩展
  - [ ] SubTask 12.3: 编写规则引擎单元测试

- [ ] Task 13: 主数据匹配
  - [ ] SubTask 13.1: 对接客户/供应商/往来单位主数据
  - [ ] SubTask 13.2: 实现印章企业名称、统一社会信用代码与主数据匹配
  - [ ] SubTask 13.3: 实现印章白名单/黑名单维护接口

- [ ] Task 14: 合规评分集成与底稿导出
  - [ ] SubTask 14.1: 在 `contract_validation_service.py` 中新增"印章合规"评分维度（建议权重 5%-10%）
  - [ ] SubTask 14.2: 实现印章合规评分可解释输出
  - [ ] SubTask 14.3: 支持审计底稿导出（印章图片、识别结果、校验意见）

# Task Dependencies

- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4 depends on Task 3
- Task 5 depends on Task 4
- Task 6 depends on Task 5（接口定义先行）
- Task 7 depends on Task 5
- Task 8 depends on Task 5, Task 6, Task 7
- Task 10 depends on Task 9
- Task 11 depends on Task 10
- Task 13 depends on Task 12
- Task 14 depends on Task 11, Task 13
