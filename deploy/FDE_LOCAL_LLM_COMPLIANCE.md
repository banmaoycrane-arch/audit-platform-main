# FDE 本地化大模型合规部署方案（律所 · 会计师事务所 · 中介机构）

> **适用读者**：项目负责人、IT、质控合伙人、信息安全负责人。  
> **产品对齐**：本仓库「财务向量审计系统」已支持 **规则引擎兜底**、**Qdrant 本地向量库**、**OpenAI 兼容本地推理（Ollama / vLLM）**、**本地/云端路由（manual / local / cloud / auto）**。  
> **财务边界**：大模型仅产出草稿、建议、标签与风险提示；正式凭证、结账与审计结论仍须 **确定性规则 + 人工复核**（见 `AGENTS.md`）。

---

## 1. 为什么中介机构要「本地化」

| 机构类型 | 典型保密义务 | 不适宜直接上公有云大模型的数据 |
| --- | --- | --- |
| 会计师事务所 | 质量控制准则、客户资料保密、审计档案 | 序时账、底稿、函证、客户名称/纳税人识别号 |
| 律师事务所 | 律师—当事人保密、案件材料 | 合同全文、庭审材料、当事人身份信息 |
| 税务师 / 评估 / 咨询 | 委托合同、涉税测算底稿 | 申报表、银行流水、股权结构 |

**本地化合规的目标**：客户原始资料与向量索引 **留在机构可控边界内**；可选地在严格脱敏后才调用外部 API。

---

## 2. 推荐部署形态（三档）

### 2.1 档 A — 纯所内闭环（强合规，推荐默认）

```text
[用户浏览器] ──HTTPS──> [审计平台 Docker：backend + web]
                              │
                              ├── SQLite/PostgreSQL（业务库）
                              ├── Qdrant 本地路径（向量，无 egress）
                              └── HTTP 内网 ──> [Ollama / vLLM @ :11434/v1]
```

- **数据出境**：无（不配置 `ai_cloud_*`）。
- **路由模式**：解析引擎配置 → `ai_routing_mode = local`。
- **适用**：年审季、涉密客户、等保/内控要求明确的所。

### 2.2 档 B — 所内优先 + 云端灾备（auto，须书面政策）

- 平时走 **本地模型**；本地不可用且 **机构政策允许** 时，回退云端（须配置 `ai_cloud_base_url` 等）。
- 代码行为：`resolve_effective_llm_config` 在 `auto` 下先 local，调用方再读 `_cloud_fallback`。
- **前置条件**：纸质或制度明确 **哪些任务允许上云**、**脱敏规则**、**禁止上云字段清单**。

### 2.3 档 C — 应用上云、模型仍留在客户机房

- 审计平台部署在机构 **机房或私有云**；公网仅 VPN / 零信任接入。
- 若应用容器在云上而模型在客户内网，须 **反代暴露** `http(s)://内网Ollama:11434/v1` 给 backend 可达地址（见前端配置页提示：frp / Nginx，**禁止**把客户财务库整体搬到公有云仅为了省钱）。

---

## 3. 硬件与模型选型（FDE 现场勘测表）

| 规模 | 并发用户 | GPU / 内存建议 | 解析模型（多模态/视觉） | 合规审查 / Agent 推理模型 |
| --- | --- | --- | --- | --- |
| 小型所（≤15 人） | 2–3 并行 | 16–32 GB 内存；可选单卡 12GB+ | `qwen2.5-vl` 或机构已购视觉 API 的 **本地替代** | `qwen2.5:7b` 或 `qwen2.5:14b` |
| 中型所 | 5–8 并行 | 单卡 24GB 或双卡；主机 64GB+ | 与上类似，**解析与推理分列**，避免 Ollama 互抢显存 | 14B 推理 + 规则兜底 |
| 大型 / 联盟所 | 分所独立 | **每法人实体一套闭环**，禁止跨省混库 | 统一镜像与版本，分所各自密钥 | 质控中心抽检日志 |

**原则**（与产品 UI 一致）：

1. **解析模型** 与 **推理模型（`ai_reasoning_model`）** 分开配置，勿强行共用一个权重。
2. `llm_max_concurrent_models = 1` 为保守默认，避免 OOM。
3. AI 留空时：**导入、规则风险、试算、结账控制仍可用** —— 适合试点期先上平台后上模型。

---

## 4. FDE 实施里程碑（建议 5 个工作日节奏）

| 阶段 | 交付物 | 验收标准 |
| --- | --- | --- |
| D0 合规访谈 | 《数据分级表》+《是否允许上云》决议 | 合伙人或授权人签字 |
| D1 基础部署 | `docker compose` 起 backend + web；`SECRET_KEY` 轮换 | `https://<IP>:8443` 可登录；`/health` 200 |
| D2 向量与存储 | `QDRANT_LOCAL_PATH` 落在持久卷；备份策略 | 导入样本后可向量检索 |
| D3 本地 LLM | Ollama 安装、`ollama pull` 两模型；配置页探活成功 | **连接测试** 返回模型存在 |
| D4 业务演练 | 序时簿导入 → 合规审查（SSE）→ 风险列表 | 借贷不平衡等 **规则必报**；LLM 为增强项 |
| D5 质控签收 | 运行 [`fde_preflight.sh`](./scripts/fde_preflight.sh) + 留档 | 脚本 `PASS`；培训记录 1 份 |

---

## 5. 操作步骤（档 A 快捷路径）

### 5.1 安装审计平台

与 [DEPLOYMENT.md](../DEPLOYMENT.md) 一致；数据卷 `app_data` 含库文件与 Qdrant。

### 5.2 安装 Ollama（所内主机或同网段 GPU 机）

```bash
# Linux 示例（以官方安装文档为准）
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:14b
# 若需票据/图片解析，另行拉取机构选定的视觉模型
export OLLAMA_HOST=0.0.0.0:11434   # 仅内网网卡，勿对公网裸暴露
```

### 5.3 一键叠加 Compose（可选）

```bash
cd /path/to/audit-platform-main
cp deploy/.env.example deploy/.env
# 编辑 SECRET_KEY；AI 三项可仍留空，改由 UI 写库

docker compose -f deploy/docker-compose.yml \
  -f deploy/docker-compose.local-llm.yml \
  --env-file deploy/.env up -d --build
```

> `docker-compose.local-llm.yml` 将 Ollama 与 backend 置于同一 Docker 网络，backend 通过 `http://ollama:11434/v1` 访问。**生产上更常见的是 Ollama 跑在裸机 GPU**，此时 backend 环境变量或 UI 填内网 IP 即可。

### 5.4 管理后台配置（推荐，可审计）

路径：**解析引擎配置** `/parser-engine/config`

| 字段 | 建议值（所内闭环） |
| --- | --- |
| `ai_provider` | `openai-compatible` |
| `ai_routing_mode` | `local` |
| `ai_local_base_url` | `http://<Ollama主机>:11434/v1` |
| `ai_local_model` | 解析用工单所需模型名 |
| `ai_reasoning_model` | 合规审查 / Agent 用语义模型 |
| `ai_fallback_to_rules` | **开启** |
| `ai_cloud_*` | **留空**（档 A） |

保存后点 **连接测试**；应看到 Ollama `/api/tags` 探活成功（见 `routes_config.test_ai_connection`）。

### 5.5 容器环境变量（与 UI 二选一或并存）

`deploy/.env` 扩展项见 [`.env.example`](./.env.example) 注释。数据库中的 `parser_engine` 配置 **优先于** `.env`。

---

## 6. 合规控制清单（质控 / 信息安全）

在机构《信息系统使用制度》中建议明确：

1. **账号与账簿**：`UserLedgerAuth` — 审计任务必须绑定账簿，禁止跨项目裸查全库。
2. **密钥**：`AI_API_KEY`、云端 Key 仅后端 / `deploy/.env`，禁止进前端仓库（产品已脱敏展示）。
3. **日志**：期间关闭、反结账、批量导入等关键操作须留存审计日志（产品方向与 `AGENTS.md` §10 一致）。
4. **备份**：`finance_audit.db` + Qdrant 目录 + 上传目录 **每日增量**；恢复演练每季度 1 次。
5. **模型输出**：界面与报告中标注 **「AI 建议，非审计/法律意见」**；合伙人复核后才能写入正式底稿结论字段。
6. **外联**：档 A 防火墙 **禁止** backend 访问公网 LLM；仅允许补丁更新窗口或离线介质升级。
7. **离职与设备**：GPU 机、备份盘纳入机构介质管理制度。

---

## 7. 与产品能力的映射

| 能力 | 本地化行为 | 无模型时 |
| --- | --- | --- |
| 序时账 / 票据解析 | 本地 LLM + 规则 TOP3 | 规则 + 模板映射 |
| 合规审查 SSE | 本地 `ai_reasoning_model` | 借贷平衡、科目规则等确定性检查 |
| 向量检索 / 风险 | Qdrant 本地路径 | 规则风险仍运行 |
| Agent 助手 | 读同一套 `parser_engine` 配置 | 规则意图 + 只读工具 |

---

## 8. 常见故障（FDE 一线）

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| 连接测试超时 | 首次 `ollama run` 拉起大模型 | 探活已改用 `/api/tags`，仍超时则查防火墙 |
| 解析慢 / OOM | 解析与审查共用一个 14B | 拆模型或降并发为 1 |
| 云端服务器访问 192.168.x.x | 模型在所内、应用在云上 | 反代或改档 A，应用也进所内 |
| 「合规」只靠 AI | 误配 `use_llm` 且关规则 | 保持 `ai_fallback_to_rules=true` |

运行预检：

```bash
bash deploy/scripts/fde_preflight.sh
```

---

## 9. 附录：档 B 脱敏上云（若机构决议允许）

仅作制度附录，**本仓库不自动脱敏上云** — 须由机构 ETL 或专用网关实现：

- 必删：姓名、身份证号、手机号、银行账号、详细地址、客户法定名称（可用「客户 A」替代）。
- 保留：科目代码、金额、期间、摘要泛化表述。
- 每次外呼须记录：操作者、任务 ID、脱敏版本号。

---

## 10. 文档维护

| 版本 | 日期 | 说明 |
| --- | --- | --- |
| 1.0 | 2026-11-18 | 首版：律所/会所中介 FDE 本地化闭环 |

相关链接：[DEPLOYMENT.md](../DEPLOYMENT.md) · [DEPLOY_SYNC.md](./DEPLOY_SYNC.md) · [README 生产部署](../README.md#生产部署)