# Checklist

## 第一阶段 MVP 验收

### 印章区域检测
- [ ] 传统 CV 印章检测服务实现并可通过单元测试
- [ ] 支持红色/蓝色印章的 HSV 颜色分割与轮廓检测
- [ ] 返回 bbox（像素坐标）、confidence、seal_shape 初判
- [ ] PaddleOCR fallback 入口实现并标记 detection_method
- [ ] 覆盖无印章、清晰印章、模糊印章、重叠印章的测试用例

### 印章区域提取与预处理
- [ ] 印章裁剪服务实现，输出标准化印章子图
- [ ] 实现颜色通道增强、背景漂白、二值化、轻微透视校正
- [ ] 子图存储路径规范，支持后续受控访问
- [ ] 预处理效果在样本集上可接受（目视检查通过）

### 印章文字识别与坐标关联
- [ ] OCR 识别服务复用现有 EasyOCR/PaddleOCR 框架
- [ ] 返回每个文字的 text、x、y、width、height、confidence
- [ ] 环形文字按角度重组为完整字符串
- [ ] 文字坐标基于原始页面像素坐标系
- [ ] 覆盖清晰印章、模糊印章、无文字印章的测试用例

### ContractSeal 数据模型
- [ ] `backend/app/db/models.py` 新增 `ContractSeal` 表
- [ ] 字段包含 id、contract_id、source_file_id、page_no、bbox、seal_image_path、recognized_text、text_items、seal_type、confidence、detection_method、created_at、updated_at
- [ ] 创建 `backend/app/models/contract_seal.py` Pydantic 模型
- [ ] Alembic 迁移脚本生成并执行成功
- [ ] 数据模型单元测试通过

### 后端 API
- [ ] `POST /api/v1/contracts/{contract_id}/seals/extract` 实现并可调用
- [ ] `GET /api/v1/contracts/{contract_id}/seals` 分页列表实现并可调用
- [ ] `GET /api/v1/seals/{seal_id}` 详情接口实现并可调用
- [ ] 路由在 `main.py` 注册
- [ ] API 在 Swagger/OpenAPI 中可见
- [ ] API 集成测试通过

### 前端"印章证据"区域
- [ ] 合同详情页新增"印章证据"页签
- [ ] 左右分栏布局实现（左侧原图/预览 + bbox 高亮，右侧印章列表）
- [ ] TypeScript 类型 `SealTextItem`、`ContractSeal` 已定义
- [ ] 前端 API client 预留印章相关方法
- [ ] 无印章数据时显示友好空状态，不报错、不空白
- [ ] 前端 TypeScript 类型检查通过
- [ ] 前端 `pnpm build:frontend` 通过

### 数据安全与审计
- [ ] 印章提取与查询接口校验用户合同访问权限
- [ ] 印章提取操作记录审计日志
- [ ] 印章图片通过受控接口或签名 URL 访问，不暴露原始路径
- [ ] 权限隔离测试通过

### 性能与准确率
- [ ] 单页 A4 印章检测平均耗时 ≤ 3 秒
- [ ] 单合同多印章（≤5 个）整体提取耗时 ≤ 10 秒
- [ ] 并发 5 个合同提取时系统稳定
- [ ] 印章检出率 ≥ 85%
- [ ] 印章误检率 ≤ 15%
- [ ] 印章文字识别准确率 ≥ 70%
- [ ] 坐标位置误差 ≤ 10 像素

### 代码工程
- [ ] 新增后端模块代码覆盖率 ≥ 80%
- [ ] 后端全量 pytest 通过
- [ ] 代码符合项目命名与注释规范（参见 AGENTS.md）
- [ ] 关键函数/类包含中文业务注释

## 第二阶段 多模态 LLM 关联校验验收

- [ ] LLM 校验提示词模板设计完成
- [ ] 输出 JSON Schema 定义完成（seal_type、associated_party、confidence、anomalies）
- [ ] `seal_verification_service.py` 实现批量校验、失败重试、结果缓存
- [ ] LLM 校验结果写入 ContractSeal 扩展字段
- [ ] OCR 与 LLM 结果融合逻辑实现
- [ ] 冲突或低置信度结果生成"需人工复核"标记
- [ ] 前端增加复核操作入口（确认正确、标记异常、人工修正）
- [ ] 印章类型分类准确率 ≥ 85%
- [ ] 印章主体关联准确率 ≥ 80%
- [ ] 异常标记召回率 ≥ 75%

## 第三阶段 规则引擎与知识库匹配验收

- [ ] 印章规则库可配置规则 ≥ 10 条
- [ ] 规则覆盖合同金额阈值、印章类型限制、财务章禁用场景、主体一致性
- [ ] 规则引擎单元测试通过
- [ ] 印章企业名称/统一社会信用代码与主数据匹配实现
- [ ] 印章白名单/黑名单维护接口实现
- [ ] 主数据匹配准确率 ≥ 90%（数据已维护前提下）
- [ ] `contract_validation_service.py` 新增"印章合规"评分维度
- [ ] 印章合规评分可解释，每条扣分附带原因与证据
- [ ] 审计底稿导出支持印章图片、识别结果、校验意见

## 通用验收

- [ ] 所有新增 API 具备 Swagger 文档
- [ ] 所有关键操作记录审计日志
- [ ] 文档更新：开发文档、API 文档、用户操作手册
- [ ] 项目排期三阶段共 16 周，里程碑节点明确
- [ ] 风险与应对措施文档化
