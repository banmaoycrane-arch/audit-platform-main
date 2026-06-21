# 上线部署手册（无域名 · Docker · HTTPS · SQLite）

本手册面向**非技术使用者**，一步步把"审计风险识别系统"部署到你自己的 **Ubuntu 服务器**（有公网 IP、暂无域名）。
部署后通过 `https://你的公网IP` 访问，自带 HTTPS 加密（自签证书，首次访问浏览器会提示一次，点继续即可）。

> 这套方案已在云端实测跑通：HTTPS 健康检查、前端网页、注册、登录、数据持久化全部正常。

---

## 一、它会启动什么

一条命令会启动两个容器：

| 容器 | 作用 |
| --- | --- |
| `backend` | 后端 API（FastAPI），数据存在 SQLite |
| `web`（Caddy） | 提供前端网页 + 把 `/api` 转发给后端 + 负责 HTTPS 加密 |

所有数据（数据库、上传文件、向量库、证书）都保存在 Docker 数据卷里，**升级重建容器不会丢数据**。

---

## 二、准备：在服务器安装 Docker（只需一次）

用 SSH 登录你的 Ubuntu 服务器，依次执行：

```bash
# 1) 安装 Docker（官方一键脚本）
curl -fsSL https://get.docker.com | sudo sh

# 2) 验证安装成功（能看到版本号即可）
sudo docker --version
sudo docker compose version
```

---

## 三、拿到代码

```bash
# 把仓库克隆到服务器（替换成你的仓库地址）
git clone https://github.com/banmaoycrane-arch/audit-platform-main.git
cd audit-platform-main
```

> 以后要更新到最新代码：在该目录执行 `git pull`，然后回到第五节重新构建即可。

---

## 四、配置密钥（必做一次）

```bash
# 1) 复制配置模板
cp deploy/.env.example deploy/.env

# 2) 生成一个随机密钥并写入 .env（用于登录令牌签名，务必保密）
echo "SECRET_KEY=$(openssl rand -hex 32)" >> deploy/.env
```

打开 `deploy/.env` 确认里面有一行 `SECRET_KEY=`（后面跟着一长串随机字符）。
`AI_BASE_URL / AI_API_KEY / AI_MODEL` 三项**先留空**——留空时系统用内置规则，核心审计功能照常可用。等以后要启用大模型时再填（见第九节）。

> （可选）想让自签证书包含你的公网 IP，可在 `deploy/.env` 追加一行：`EXTRA_SAN=IP:你的公网IP`

---

## 五、构建并启动

在仓库根目录执行：

```bash
sudo docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
```

第一次会下载基础镜像、安装依赖、打包前端，需要几分钟。完成后查看状态：

```bash
sudo docker compose -f deploy/docker-compose.yml ps
```

两个容器都显示 `Up` 即成功。

---

## 六、放行端口

在你的**云服务商安全组/防火墙**放行 **80** 和 **443** 端口（对外）。
如果服务器开了 ufw 防火墙，也执行：

```bash
sudo ufw allow 80
sudo ufw allow 443
```

---

## 七、访问与首次使用

1. 浏览器打开 `https://你的公网IP`
2. 因为是自签证书，会出现"您的连接不是私密连接"提示——点 **“高级”→“继续前往…（不安全）”**（流量仍是加密的）。
3. 进入登录页 → 点“注册” → 创建你的第一个账号（用户名 + 手机号 + 密码 + 勾选同意）。
4. 注册后自动登录，进入工作台，即可开始使用审计/记账功能。

---

## 八、日常运维

```bash
# 查看日志（排查问题时用）
sudo docker compose -f deploy/docker-compose.yml logs -f

# 重启
sudo docker compose -f deploy/docker-compose.yml restart

# 停止
sudo docker compose -f deploy/docker-compose.yml down

# 更新到最新代码后重新部署
git pull
sudo docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build
```

### 数据备份（重要）

数据库在 Docker 卷 `deploy_app_data` 里。定期备份：

```bash
# 把数据库文件复制到当前目录（带日期）
sudo docker compose -f deploy/docker-compose.yml exec backend \
  sh -c 'cat /data/finance_audit.db' > backup_$(date +%F).db
```

把备份文件再下载/转存到安全位置即可。

---

## 九、（以后）启用大模型 AI

等你准备好云端大模型 API（OpenAI 兼容）时：

1. 编辑 `deploy/.env`，填写三项（`AI_BASE_URL` 填到 `/v1` 为止、结尾不带斜杠）：
   ```
   AI_BASE_URL=https://你的API地址/v1
   AI_API_KEY=你的密钥
   AI_MODEL=你的聊天模型名
   ```
2. 重启使其生效：
   ```bash
   sudo docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d
   ```

> key 只存在服务器本地的 `deploy/.env` 中，已被 `.gitignore` 忽略，不会进入代码仓库。

---

## 十、（以后）换成正式域名 + 浏览器信任的证书

买了域名并把它解析到服务器公网 IP 后：

1. 编辑 `deploy/Caddyfile`：
   - 把 `:443` 改成你的域名，例如 `audit.example.com`
   - 删除 `tls /data/certs/server.crt /data/certs/server.key` 这一行
   - 把全局块里的 `auto_https off` 删除
2. 重新构建 web 容器：
   ```bash
   sudo docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d --build web
   ```

Caddy 会自动向 Let's Encrypt 申请免费且**浏览器信任**的证书，从此不再有"不安全"提示。

---

## 常见问题

- **打不开 / 转圈**：检查安全组是否放行 80/443；用 `... logs -f` 看后端是否报错。
- **证书警告**：自签证书的正常现象，点“继续”即可；想去掉就按第十节换域名。
- **改了代码没生效**：记得加 `--build` 重新构建后再 `up -d`。
