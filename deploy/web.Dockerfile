# Web 镜像：构建前端静态文件，并用 Caddy 同时承担
#   ① 提供前端网页  ② 反向代理 /api 到后端  ③ 自签 HTTPS（无域名场景）
#
# 多阶段构建：阶段1用 Node 打包前端，阶段2把产物交给 Caddy。

# 阶段 1：构建前端
FROM node:22-slim AS build
WORKDIR /app
RUN npm install -g pnpm@9

# 先复制 workspace 清单以利用缓存
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY frontend/ ./frontend/

# 安装依赖并打包（不设置 VITE_API_BASE_URL，前端将使用同源 /api，由 Caddy 反代到后端）
RUN pnpm --dir frontend install --frozen-lockfile || pnpm --dir frontend install
RUN pnpm --dir frontend build

# 阶段 2：Caddy 提供静态文件 + 反代 + 自签 HTTPS
FROM caddy:2-alpine
RUN sed -i 's/dl-cdn.alpinelinux.org/mirrors.aliyun.com/g' /etc/apk/repositories \
    && apk add --no-cache openssl
COPY --from=build /app/frontend/dist /srv/www
COPY deploy/Caddyfile /etc/caddy/Caddyfile
COPY deploy/web-entrypoint.sh /usr/local/bin/web-entrypoint.sh
RUN chmod +x /usr/local/bin/web-entrypoint.sh \
    && sed -i 's/\r$//' /usr/local/bin/web-entrypoint.sh
ENTRYPOINT ["/usr/local/bin/web-entrypoint.sh"]
