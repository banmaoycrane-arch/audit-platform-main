# 税务城市出口 IP 池 — 轮换与绑定设计规格

> **文档类型**: 基础设施 / 产品规格（Phase 0 原型）  
> **更新日期**: 2026-07-13  
> **状态**: draft — 仅设计，未接真实税局  
> **关联页面**: `/tax/connections`（UI 原型）  
> **边界**: 本文描述 **城市内 IP 池调度**，不替代乐企/税控服务商等官方通道

---

## 一、设计目标

| 目标 | 说明 |
|------|------|
| **城市聚焦** | 每个 `city_code` 独立 IP 池，禁止跨省混用 |
| **可轮换** | IP 故障、被封、运营商变更时可自动换池内另一条 |
| **可解释** | 每次换 IP 有审计记录与触发原因 |
| **会话粘性** | 同一纳税主体在 **lease 周期内** 固定一条出口，不做「每次请求换 IP」 |
| **运维简单** | 池内 N 条 IP，Worker 按绑定表出网 |

**不做的能力（产品红线）**：

- 全国无差别大轮换池
- 同一税号在单次登录会话内频繁跳 IP
- 伪造 MAC / 浏览器指纹欺骗税局风控

---

## 二、核心概念

```text
CityEgressPool（城市池）
  └─ EgressNode × N（单条出口 IP + Worker 节点）

TaxpayerBinding（主体绑定）
  └─ taxpayer_id → egress_node_id（带 lease 到期时间）

TaxSession（税局会话）
  └─ 必须走 binding 指定的 egress_node；会话存活期间禁止换 IP

RotationEvent（轮换事件）
  └─ 记录 old_ip → new_ip、trigger、operator
```

---

## 三、IP 池怎么「轮番」— 三种模式

### 3.1 模式对照

| 模式 | 何时换 IP | 适用 |
|------|-----------|------|
| **A. 粘性绑定（默认）** | lease 内不换；仅故障时换 | 电子税务局登录、开票 |
| **B. 池内自动轮换（故障）** | 健康检查失败 / 被封 / 连续 5xx | 运维容错 |
| **C. 新主体入池分配（轮询）** | 仅 **首次绑定** 时 round-robin | 均衡池内负载 |

**禁止模式 D**：同一 `taxpayer_id` 在活跃 `TaxSession` 期间按请求 round-robin — 极易行为异常。

### 3.2 推荐默认策略：`sticky_with_failover`

```text
1. 新主体绑定：
   pick = pool.select_for_new_binding(city_code)
   算法：weighted_round_robin（权重 = 剩余容量）
   条件：status=active AND current_bindings < max_tenants

2. 日常登录/开票：
   始终使用 binding.egress_node_id
   不换 IP

3. 自动轮换触发（仅以下）：
   T1  health_check_failed   连续 3 次 TCP/HTTPS 探活失败
   T2  bureau_blocked        税局返回明确封禁码（可配置关键字）
   T3  ip_blacklisted        池管理标记 blocked
   T4  lease_expired         lease 到期 + 策略允许续期时可选换槽
   T5  manual_admin          管理员强制换 IP

4. 轮换执行：
   a. 结束当前 TaxSession（若有）
   b. cooling_old_ip（旧 IP 进入冷却 24h，不立刻复用）
   c. new_node = pool.select_failover(city, exclude=[old_ip, ...cooling])
   d. 更新 binding + 写 RotationEvent
   e. 可选：通知用户重新扫码登录

5. 冷却与复用：
   - cooling 24h 默认
   - 同一税号 7 天内最多自动轮换 2 次（超限 → 人工）
```

### 3.3 池内选择算法（伪代码）

```python
def select_for_new_binding(pool: list[EgressNode]) -> EgressNode:
    candidates = [n for n in pool if n.status == "active" and n.load < n.max_tenants]
    if not candidates:
        raise PoolExhausted(city_code)
    # 权重 = 剩余槽位；同权重 round-robin
    return weighted_rr(candidates, key=lambda n: n.max_tenants - n.load)


def select_failover(pool, exclude: set[str]) -> EgressNode:
    candidates = [n for n in pool if n.ip not in exclude and n.status == "active"]
    if not candidates:
        raise FailoverExhausted(...)
    # 优先选负载最低，避免扎堆
    return min(candidates, key=lambda n: n.load)
```

---

## 四、数据模型

### 4.1 `tax_city_egress_pools`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | |
| city_code | string | 行政区划，如 `330100` |
| city_name | string | 杭州市 |
| bureau_province | string | 主管税务机关省 |
| pool_policy | enum | `sticky_with_failover` |
| max_rotate_per_taxpayer_7d | int | 默认 2 |
| cooling_hours | int | 默认 24 |

### 4.2 `tax_egress_nodes`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | |
| pool_id | int | FK |
| egress_ip | string | 固定出口公网 IP |
| worker_host | string | Worker 内网地址 |
| provider | string | aliyun / telecom / office_gateway |
| asn_type | enum | `residential` `enterprise` `datacenter` |
| status | enum | `active` `warming` `cooling` `blocked` |
| max_tenants | int | 单 IP 最大绑定税号数，建议 3–5 |
| current_bindings | int | 当前绑定数 |
| health_score | float | 0–1，探活与税局成功率加权 |
| last_health_at | datetime | |

### 4.3 `taxpayer_egress_bindings`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | |
| taxpayer_id | string | 纳税识别号 |
| ledger_id | int | 关联账簿 |
| city_code | string | 必须与注册地一致 |
| egress_node_id | int | 当前绑定节点 |
| lease_start | datetime | |
| lease_end | datetime | 默认 +90d |
| rotate_count_7d | int | 滚动计数 |
| last_rotate_at | datetime | |

### 4.4 `tax_rotation_events`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | int | |
| taxpayer_id | string | |
| old_node_id | int | |
| new_node_id | int | |
| trigger | enum | T1–T5 |
| reason_detail | text | |
| created_by | string | system / admin_user |

### 4.5 `tax_sessions`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | uuid | |
| taxpayer_id | string | |
| egress_node_id | int | 会话期间不可变 |
| auth_state | enum | `idle` `need_qr` `active` `expired` |
| browser_profile_id | string | 隔离 Profile，非 MAC 伪造 |
| started_at / expires_at | datetime | |

---

## 五、运行时架构

```text
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ Web UI      │────▶│ Tax Broker API   │────▶│ City Worker     │
│ /tax/...    │     │ (绑定/会话/轮换)  │     │ (Playwright/    │
└─────────────┘     └────────┬─────────┘     │  本地代理出网)   │
                             │                └────────┬────────┘
                             ▼                         │
                    ┌─────────────────┐              ▼
                    │ Pool Scheduler  │       固定 egress_ip
                    │ health + rotate │              │
                    └─────────────────┘              ▼
                                            省电子税务局
```

**Worker 出网**：iptables / tun2socks / 云厂商 EIP 绑定到 Worker，**不**在应用层每次换代理 URL。

---

## 六、健康检查与轮换状态机

### 6.1 EgressNode 状态机

```text
warming → active → cooling → active
              ↓
           blocked
```

| 状态 | 含义 |
|------|------|
| warming | 新 IP 上架观察 24h，不接新绑定 |
| active | 可绑定、可故障转移目标 |
| cooling | 轮换后冷却，不接新绑定 |
| blocked | 税局/运营商封禁，人工复核 |

### 6.2 探活

| 检查项 | 频率 | 失败阈值 |
|--------|------|----------|
| TCP 443 到税局登录域 | 5min | 连续 3 次 |
| 探针页 HTTP 200（可选） | 15min | 连续 2 次 |
| 最近 10 次真实登录成功率 | 实时 | < 50% 降权 |

---

## 七、API 草案（Phase 1）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/tax/egress/pools?city=` | 城市池概览 |
| GET | `/api/tax/egress/bindings?ledger_id=` | 账簿绑定列表 |
| POST | `/api/tax/egress/bindings` | 新主体入池分配 |
| POST | `/api/tax/egress/bindings/{id}/rotate` | 手动轮换 |
| POST | `/api/tax/sessions` | 发起税局登录会话 |
| GET | `/api/tax/sessions/{id}` | 会话状态（需扫码等） |
| GET | `/api/tax/rotation-events` | 审计日志 |

---

## 八、合规与风控说明（产品必读）

1. **城市池 ≠ 隐身**：税局仍可见出口 IP；设计重点是 **地理一致 + 行为稳定**，不是「看不出来」。  
2. **自动轮换仅用于容错**：避免把「躲检测」写成产品卖点。  
3. **一 IP 少税号**：`max_tenants` 限制，防止关联风控。  
4. **优先官方通道**：乐企/税控服务商 API 仍是长期正路；本池适用于 **RPA 过渡期**。  
5. **审计留存**：`RotationEvent` 保留 ≥ 1 年。

---

## 九、Phase 0 交付（当前）

- [x] 本规格文档  
- [x] UI `/tax/connections`（已接 API）  
- [x] 后端表结构 + API  
- [x] 合作商导入 SQL 模板（杭州 / 深圳 / 山西太原）  

---

## 十、合作商三城 IP 池配置（杭州 · 深圳 · 山西太原）

| 城市 | city_code | 税局口径 |
|------|-----------|----------|
| 杭州 | `330100` | 浙江省电子税务局 |
| 深圳 | `440300` | 广东省电子税务局（深圳） |
| 山西 | `140100` | 山西省电子税务局（太原） |

### 第一步：生产 `deploy/.env`

```env
TAX_EGRESS_SEED_ENABLED=false
TAX_EGRESS_MAX_ROTATE_PER_TAXPAYER_7D=2
TAX_EGRESS_COOLING_HOURS=24
TAX_EGRESS_DEFAULT_LEASE_DAYS=90
```

`SEED_ENABLED=false` 表示不用演示假 IP，只使用你导入的合作商池。

### 第二步：向合作商索取（每个城市至少 1 条）

| 字段 | 说明 | 示例 |
|------|------|------|
| **egress_ip** | 税局能看到的公网出口 IP | `58.x.x.x` |
| **worker_host** | 代理网关 `host:port` 或地区 Worker 地址 | `proxy-hz.partner.com:1080` |
| 协议 | HTTP / SOCKS5 / 专线 EIP | 与 Worker 实现一致 |
| 账号密码 | 若代理需认证 | 写在 Worker 环境变量，不进本系统 DB |

### 第三步：导入 SQL

编辑 `deploy/sql/seed_tax_egress_partner.sql`，把 `YOUR_*` 换成合作商真实值，然后：

```bash
# 上传 SQL 到服务器后
docker cp deploy/sql/seed_tax_egress_partner.sql deploy-backend-1:/tmp/seed_tax_egress_partner.sql
docker exec deploy-backend-1 sqlite3 /data/finance_audit.db < /tmp/seed_tax_egress_partner.sql
docker compose -f deploy/docker-compose.yml --env-file deploy/.env restart backend
```

### 第四步：系统里绑定纳税主体

1. 打开 https://47.122.117.76/tax/connections  
2. 选择城市（杭州 / 深圳 / 太原）  
3. 「新增绑定」→ 填税号、企业名  
4. 系统自动从该城市池分配固定 IP（lease 90 天）  
5. 「登录税局」→ Phase 1 仅记录会话状态；真实扫码在 Worker 完成  

### 若生产已有旧演示池（上海/广州）

```sql
-- 可选：清空后重新导入（会删掉已有绑定记录）
DELETE FROM tax_rotation_events;
DELETE FROM tax_egress_bindings;
DELETE FROM tax_egress_nodes;
DELETE FROM tax_city_egress_pools;
```

再执行 `seed_tax_egress_partner.sql`。

### API 入口

| 方法 | 路径 |
|------|------|
| GET | `/api/tax/egress/pools?city_code=330100` |
| GET | `/api/tax/egress/bindings` |
| POST | `/api/tax/egress/bindings` |
| POST | `/api/tax/egress/bindings/{id}/rotate` |
| POST | `/api/tax/egress/bindings/{id}/sessions` |
| GET | `/api/tax/egress/rotation-events` |

### 前端入口

https://47.122.117.76/tax/connections

---

## 十一、与 MVP 主线关系

| 优先级 | 项 |
|--------|-----|
| P0 | 记账 L6 验收 |
| P1 | 发票文件导入 → 凭证 |
| **P2** | 税务城市池 + 单城试点 |
| 冻结 | 全国代理、会话内频繁换 IP |
