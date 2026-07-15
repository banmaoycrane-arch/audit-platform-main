-- 合作商城市 IP 池导入模板（杭州 / 深圳 / 山西太原）
-- 用法：
--   1. 将下方 YOUR_* 替换为合作商提供的真实值
--   2. 生产库执行：docker exec deploy-backend-1 sqlite3 /data/finance_audit.db < /tmp/seed_tax_egress_partner.sql
--
-- 字段说明：
--   egress_ip   = 税局看到的公网出口 IP（合作商告知或 ip.sb 实测）
--   worker_host = 合作商代理网关 host:port 或地区 Worker 内网地址
--   provider    = 合作商名称 + 城市备注

-- ---------- 城市池（幂等） ----------
INSERT OR IGNORE INTO tax_city_egress_pools (city_code, city_name, bureau_province, pool_policy, max_rotate_per_taxpayer_7d, cooling_hours)
VALUES ('330100', '杭州市', '浙江省', 'sticky_with_failover', 2, 24);

INSERT OR IGNORE INTO tax_city_egress_pools (city_code, city_name, bureau_province, pool_policy, max_rotate_per_taxpayer_7d, cooling_hours)
VALUES ('440300', '深圳市', '广东省', 'sticky_with_failover', 2, 24);

INSERT OR IGNORE INTO tax_city_egress_pools (city_code, city_name, bureau_province, pool_policy, max_rotate_per_taxpayer_7d, cooling_hours)
VALUES ('140100', '太原市', '山西省', 'sticky_with_failover', 2, 24);

-- ---------- 杭州节点（可增删多条） ----------
INSERT OR IGNORE INTO tax_egress_nodes (pool_id, node_key, egress_ip, worker_host, provider, status, max_tenants, current_bindings, health_score)
SELECT id, 'hz-partner-1', 'YOUR_HANGZHOU_EGRESS_IP', 'YOUR_HANGZHOU_PROXY_HOST:PORT', '合作商-杭州', 'active', 5, 0, 1.0
FROM tax_city_egress_pools WHERE city_code = '330100';

-- 杭州备用 IP（可选，取消注释并改 IP）
-- INSERT OR IGNORE INTO tax_egress_nodes (pool_id, node_key, egress_ip, worker_host, provider, status, max_tenants, current_bindings, health_score)
-- SELECT id, 'hz-partner-2', 'YOUR_HANGZHOU_EGRESS_IP_2', 'YOUR_HANGZHOU_PROXY_HOST_2:PORT', '合作商-杭州-2', 'active', 5, 0, 1.0
-- FROM tax_city_egress_pools WHERE city_code = '330100';

-- ---------- 深圳节点 ----------
INSERT OR IGNORE INTO tax_egress_nodes (pool_id, node_key, egress_ip, worker_host, provider, status, max_tenants, current_bindings, health_score)
SELECT id, 'sz-partner-1', 'YOUR_SHENZHEN_EGRESS_IP', 'YOUR_SHENZHEN_PROXY_HOST:PORT', '合作商-深圳', 'active', 5, 0, 1.0
FROM tax_city_egress_pools WHERE city_code = '440300';

-- ---------- 山西太原节点 ----------
INSERT OR IGNORE INTO tax_egress_nodes (pool_id, node_key, egress_ip, worker_host, provider, status, max_tenants, current_bindings, health_score)
SELECT id, 'sx-partner-1', 'YOUR_TAIYUAN_EGRESS_IP', 'YOUR_TAIYUAN_PROXY_HOST:PORT', '合作商-山西太原', 'active', 5, 0, 1.0
FROM tax_city_egress_pools WHERE city_code = '140100';

-- 验证
SELECT p.city_code, p.city_name, n.node_key, n.egress_ip, n.worker_host, n.provider, n.status
FROM tax_city_egress_pools p
JOIN tax_egress_nodes n ON n.pool_id = p.id
WHERE p.city_code IN ('330100', '440300', '140100')
ORDER BY p.city_code, n.node_key;
