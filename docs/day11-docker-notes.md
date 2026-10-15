# Day 11 · Docker 打包记录

日期：2026-10-15

## 三笔数字

- jar 大小：**46.7 MB**（48,947,163 字节）
- 镜像大小：**157 MB**（`docker images` 的"内容大小"列；占磁盘 531 MB，含与基础镜像共享的部分）
- 容器启动耗时：**3.493 秒**（`docker logs`：Started BookSystemBootApplication in 3.493 seconds）

## 今天最反直觉的一个点

- 容器里的 localhost 不是我的电脑——同一个 jar、同一份 yaml，本机跑能连上 MySQL，装进容器就连不上，要改用 `host.docker.internal`。
  "运行环境"不只是 JDK 版本，网络也是环境的一部分。

## 踩的坑

- **镜像拉取卡死 2000+ 秒**：`docker build` 卡在下载基础镜像 eclipse-temurin:17-jre。
  排查发现 daemon.json 里配的 3 个镜像加速器（dockerproxy.com / hub.rat.dev / docker.nju.edu.cn）**已全部失效**（连 hello-world 都拉不动）。
  修复：实测候选源后换成 4 个可用源（docker.1ms.run / docker.m.daocloud.io / docker.1panel.live / docker.xuanyuan.me），
  重启 Docker 引擎生效——拉取同一个镜像只用 **1 分 38 秒**。
  教训：**拉镜像卡死，先查镜像加速器**（Docker Desktop → Settings → Docker Engine）。

## 常用命令备忘

- 构建镜像：`docker build -t book-system:1.0 .`
- 跑容器：`docker run -d --name book-system -p 8080:8080 -e "SPRING_DATASOURCE_URL=jdbc:mysql://host.docker.internal:3306/book_system?..." -e "SPRING_DATA_REDIS_HOST=host.docker.internal" book-system:1.0`
- 看日志：`docker logs book-system`
- 进容器：`docker exec -it book-system sh`
- 停 / 启：`docker stop book-system` / `docker start book-system`
