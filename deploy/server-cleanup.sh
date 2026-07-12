#!/bin/sh
# 服务器精简：删除部署/测试残留，保留 Docker 数据卷与运行中容器
set -e

echo "=== Before ==="
df -h / | tail -1

rm -f /tmp/audit-deploy.tgz /tmp/client.ts /tmp/ParserEvolutionPage.tsx \
  /tmp/pyproject.toml /tmp/backend.Dockerfile /tmp/web.Dockerfile \
  /tmp/backend-build.log /tmp/deploy.env.bak /tmp/patch-caddy-on-server.sh \
  /tmp/fix-caddy-on-server.sh /tmp/mahjong-caddy-snippet.txt
rm -f /root/tower-defense-upload.tar.gz /root/remote_patch.py 2>/dev/null || true

PROJ=/root/audit-platform-main
cd "$PROJ"

rm -rf backend/htmlcov backend/qdrant_local_storage qdrant_local_storage storage temp seal_cov_html 2>/dev/null || true
rm -f backend/finance_audit_test_delete.db backend/finance_audit_test_delete.db-shm backend/finance_audit_test_delete.db-wal \
  backend/finance_audit_api_test.db backend/boundary_ledger_test.db boundary_ledger_test.db finance_audit.db \
  backend/*.log backend/pip_*.log backend/p3_test_output.log backend/pytest_out.log 2>/dev/null || true
rm -f backend/finance_audit.db.pre_voucher_cleanup.* 2>/dev/null || true
rm -f full_test_output.txt pytest_output.txt pytest_result.txt 2>/dev/null || true
rm -f backend/mypy_*.txt backend/*test_output*.txt backend/test_*.txt backend/e2e_output.txt \
  backend/seal_*output*.txt backend/pytest_*.txt backend/test_summary.txt 2>/dev/null || true
rm -f backend/fix_*.py backend/batch_*.py backend/add_timezone_imports.py backend/analyze_mypy.py \
  backend/wrap_audit_services.py backend/validate_batch_replace.py backend/replace_data_extract.py \
  backend/run_p3_test.py backend/performance_test.py backend/test_fix_*.py 2>/dev/null || true
rm -f deploy/Caddyfile.bak.* 2>/dev/null || true

# 开发用 storage（生产上传在 Docker 卷 /data）
rm -rf backend/storage 2>/dev/null || true

docker image prune -af
docker builder prune -af

echo "=== After ==="
df -h / | tail -1
docker system df
cd "$PROJ" && docker compose -f deploy/docker-compose.yml ps
curl -sk https://127.0.0.1/health
echo
du -sh "$PROJ" /tmp 2>/dev/null
