#!/bin/sh
# Probe key production APIs via web container (HTTPS localhost)
BASE="https://127.0.0.1"
endpoints="
/health
/api/ledgers
/api/files?project_id=1
/api/entries?ledger_id=2&limit=1
/api/accounting-periods?ledger_id=2
/api/projects
/api/chart-of-accounts?ledger_id=2
/api/counterparties?ledger_id=2
/api/parser-engine/evolution/proposals?limit=5
"

echo "=== API probe $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
for path in $endpoints; do
  code=$(curl -sk -o /tmp/probe_body.txt -w '%{http_code}' "${BASE}${path}")
  body=$(head -c 120 /tmp/probe_body.txt | tr '\n' ' ')
  echo "$code  $path  |  $body"
done

echo ""
echo "=== Unique OperationalError columns (full backend log) ==="
docker logs deploy-backend-1 2>&1 | grep -oE 'no such column: [a-z0-9_.]+' | sort -u

echo ""
echo "=== Unique 500 endpoints (full backend log) ==="
docker logs deploy-backend-1 2>&1 | grep '500 Internal Server Error' | sed 's/.*"\([A-Z]* [^"]*\)".*/\1/' | sort | uniq -c | sort -rn | head -25

echo ""
echo "=== no such table (full backend log) ==="
docker logs deploy-backend-1 2>&1 | grep -oE 'no such table: [a-z0-9_]+' | sort -u

echo ""
echo "=== ImportError / ModuleNotFound (full backend log) ==="
docker logs deploy-backend-1 2>&1 | grep -iE 'ImportError|ModuleNotFoundError' | tail -5
