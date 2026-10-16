# Day 12 · 部署上线记录

日期：2026-10-16
服务器：腾讯云轻量应用服务器（81.71.101.43 / 北京 / 2核4G / Ubuntu 22.04.4 LTS）
**在线地址：http://81.71.101.43:8080/doc.html**

## 服务器上的架构

```
┌─ 腾讯云服务器 81.71.101.43（Ubuntu）──────────────────────────┐
│                                                              │
│  ┌─ Docker ──────────────────────────────────────────────┐   │
│  │                                                       │   │
│  │   ┌ book-net（自定义内部网络，容器之间实名互访）┐        │   │
│  │   │                                            │       │   │
│  │   │  [book-system]   [book-mysql]  [book-redis]│       │   │
│  │   │     :8080           :3306         :6379    │       │   │
│  │   │      ▲                                     │       │   │
│  │   └──────┼─────────────────────────────────────┘       │   │
│  └──────────┼─────────────────────────────────────────────┘   │
│             │  ← 唯一对外开放的口：-p 8080:8080                │
│  防火墙规则：TCP 8080 放行                                     │
└─────────────▲────────────────────────────────────────────────┘
              │  公网
   [浏览器]  [手机流量]  [任何人]
```

- `book-mysql`（mysql:8.0，**无端口暴露**，数据卷 `book-mysql-data`）
- `book-redis`（redis:7-alpine，**无端口暴露**）
- `book-system`（服务器本机构建的镜像，`-p 8080:8080` 唯一对外）
- 三个容器均配置 `restart=unless-stopped`（服务器重启自动回来）

## 部署流程（实际执行）

1. 装 Docker：`curl -fsSL https://get.docker.com | sh -s -- --mirror Aliyun` + 配镜像加速器
2. `docker network create book-net`
3. 起 book-mysql（新密码 + TZ + 数据卷）和 book-redis
4. **数据搬迁**：本地 `mysqldump` → `scp` → `docker exec -i book-mysql mysql < dump.sql`
   - 结果：book 7 条 / sys_user 5 条（与本地一致）
5. 传 jar + Dockerfile → 服务器 `docker build -t book-system:1.0 .`
6. 起应用容器：`-e` 注入数据库地址（`book-mysql`）、密码、Redis 地址（`book-redis`）
7. 腾讯云控制台**防火墙**放行 TCP 8080
8. 验收：公网 `doc.html` 200 + 登录接口 + 图书列表接口全通

## 服务器日常命令（备忘）

```bash
# 看所有容器状态
docker ps -a

# 看应用日志
docker logs book-system --tail 50

# 重启整套服务
docker restart book-mysql book-redis book-system

# 数据库操作（密码从凭据文件读取）
source /root/.db_pw && docker exec -i book-mysql mysql -uroot -p"$MYSQL_PWD" -e "SELECT COUNT(*) FROM book_system.book;"

# 更新代码上线的完整链路（五步）：
# 1) 本地 mvn package  2) scp 新 jar 到 /root/book-system/target/
# 3) 服务器 docker build -t book-system:1.0 .  4) docker rm -f book-system
# 5) docker run（参数同首次，见下方记录）
```

首次 run 参数（更新代码时复用）：

```
docker run -d --name book-system --network book-net -p 8080:8080 \
  -e "SPRING_DATASOURCE_URL=jdbc:mysql://book-mysql:3306/book_system?useUnicode=true&characterEncoding=utf-8&serverTimezone=Asia/Shanghai&useSSL=false&allowPublicKeyRetrieval=true" \
  -e "SPRING_DATASOURCE_PASSWORD=<数据库密码>" \
  -e "SPRING_DATA_REDIS_HOST=book-redis" \
  book-system:1.0
```

## 安全实践

- MySQL / Redis **不对公网暴露**（从外部连 3306/6379 连不上）
- 数据库用**新密码**（旧密码随 yaml 上过公开仓库，视为已泄露，弃用）
- 配置通过 `-e` 环境变量注入，不进代码、不进镜像
- 服务器上凭据文件 `/root/.db_pw`（600 权限，只有 root 可读）
- SSH 已配置**密钥登录**（本地 `~/.ssh/id_ed25519`）
- **SSH 仅密钥登录**（2026-10-16 晚加固）：`/etc/ssh/sshd_config.d/99-hardening.conf` 中 `PasswordAuthentication no` + `PermitRootLogin prohibit-password`；密码通道已关闭
- **fail2ban 已安装**：SSH 多次失败自动封禁 IP

> 背景：服务器上线当天即遭遇机器人爆破（auth.log 记录 15 次失败尝试，来自多个陌生 IP，尝试 admin/root/elasticsearch 等用户名）——这是公网服务器的常态，所以做了上述加固。


## 踩坑记录（真实事故，都是经验）

1. **服务器拉镜像卡死 10 分钟**：原加速器（1ms.run/daocloud）对 eclipse-temurin 拉取异常缓慢 → 换成 `docker.1panel.live` / `docker.xuanyuan.me` 后秒下。
2. **`systemctl restart docker` 停掉了所有容器**：book-mysql/book-redis 因为没有 restart 策略被停（应用连不上数据库报 UnknownHostException）→ `docker start` 恢复 + 全部配 `unless-stopped`。
3. **中文验证要带参数**：`docker exec mysql` 查询中文必须加 `--default-character-set=utf8mb4`，否则显示 `???`（数据本身没问题）。
4. 端口"内通外不通" = 云平台防火墙没放行（永远先查防火墙规则）。
