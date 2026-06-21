#!/bin/sh
# Web 容器启动脚本：首次启动时自动生成自签 TLS 证书（无域名场景），随后启动 Caddy。
# 证书写入持久化卷 /data/certs，重启复用，不会每次变化。
set -e

CERT_DIR=/data/certs
mkdir -p "$CERT_DIR"

if [ ! -f "$CERT_DIR/server.crt" ] || [ ! -f "$CERT_DIR/server.key" ]; then
  echo "[web-entrypoint] 生成自签 TLS 证书 ..."
  # EXTRA_SAN 可选：在 .env 设置服务器公网 IP 可让证书包含该 IP，例如 EXTRA_SAN=IP:1.2.3.4
  SAN="DNS:localhost,IP:127.0.0.1"
  if [ -n "$EXTRA_SAN" ]; then
    SAN="$SAN,$EXTRA_SAN"
  fi
  openssl req -x509 -newkey rsa:2048 -nodes \
    -keyout "$CERT_DIR/server.key" -out "$CERT_DIR/server.crt" \
    -days 3650 -subj "/CN=finance-audit" \
    -addext "subjectAltName=$SAN"
  echo "[web-entrypoint] 证书已生成于 $CERT_DIR"
fi

exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
