# 足球数据系统 - 部署文档

**版本**: 1.2.0
**更新日期**: 2026-05-24

---

## 一、环境要求

### 1.1 硬件要求

- NAS 设备（UniFi 内网架构）
- CPU: 4 核心
- 内存: 8 GB
- 存储: 50 GB 可用空间

### 1.2 软件要求

- Docker 20.10+
- Docker Compose 2.0+
- 网络：NAS 与内网互通

---

## 二、快速部署

### 2.1 克隆项目

```bash
cd /home/mk/project
git clone <repository_url> football_system
cd football_system
```

### 2.2 配置环境变量（可选）

```bash
# 系统 A 配置
cd system_a
cp .env.example .env
# 编辑 .env 文件，配置数据库密码等

# 系统 B 配置
cd ../system_b
cp .env.example .env
# 编辑 .env 文件，配置系统 A API 地址
```

### 2.3 启动服务

```bash
cd /home/mk/project/football_system
docker-compose up -d
```

> **v1.2.0 变更**: Dockerfile 改用 `python:3.11-slim` 基础镜像，添加 `PYTHONDONTWRITEBYTECODE` 和 `PYTHONUNBUFFERED` 环境变量，docker-compose.yml 新增 `build` 上下文配置。

### 2.4 验证服务

```bash
# 检查容器状态
docker-compose ps

# 检查系统 A API
curl http://localhost:8000/health

# 检查系统 B Streamlit
curl http://localhost:8501
```

---

## 三、服务访问

### 3.1 系统 A - 数据基础设施

| 服务 | 地址 | 说明 |
|------|------|------|
| REST API | http://localhost:8000 | 数据接口 |
| 管理后台 | http://localhost:8000/admin/ | HTML 管理界面 |
| API 文档 | http://localhost:8000/docs | Swagger 文档 |

### 3.2 系统 B - 量化分析平台

| 服务 | 地址 | 说明 |
|------|------|------|
| Streamlit | http://localhost:8501 | 用户界面 |

---

## 四、配置说明

### 4.1 Docker Compose 配置

```yaml
# docker-compose.yml 关键配置

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: football      # 用户名
      POSTGRES_PASSWORD: xxx       # 密码（生产环境请修改）
      POSTGRES_DB: football_data   # 数据库名

  system_a:
    environment:
      - DATABASE_URL=postgresql://football:xxx@postgres:5432/football_data

  system_b:
    environment:
      - SYSTEM_A_API_URL=http://system_a:8000
```

### 4.2 系统 A 配置

文件: `system_a/config/settings.py`

| 参数 | 说明 | 默认值 |
|------|------|--------|
| database_url | PostgreSQL 连接字符串 | - |
| api_host | API 监听地址 | 0.0.0.0 |
| api_port | API 监听端口 | 8000 |
| crawl_concurrency | 爬虫并发数 | 3 |
| request_delay_min | 请求延迟下限（秒） | 1.0 |
| request_delay_max | 请求延迟上限（秒） | 3.0 |
| proxy_enabled | 是否启用代理 | false |
| log_level | 日志级别 | INFO |

### 4.3 系统 B 配置

文件: `system_b/config/settings.py`

| 参数 | 说明 | 默认值 |
|------|------|--------|
| system_a_api_url | 系统 A API 地址 | http://localhost:8000 |
| sync_interval_hours | 自动同步间隔（小时） | 24 |
| sync_enabled | 是否启用自动同步 | true |

---

## 五、爬虫配置

### 5.1 代理设置

如果需要使用代理访问目标网站，在管理后台配置：

1. 访问 http://localhost:8000/admin/settings
2. 勾选"启用代理"
3. 选择代理类型（SOCKS5/HTTP）
4. 输入代理服务器地址、端口、用户名、密码
5. 保存配置

### 5.2 代理服务商（可选）

支持的代理服务：
- Oxylabs
- NexIP
- 自建 SOCKS5 代理

### 5.3 反爬策略

系统已内置以下策略：
- 随机 User-Agent
- 请求间隔随机化
- 错误重试机制
- 代理轮换（需配置）

---

## 六、数据管理

### 6.1 数据库备份

```bash
# 备份数据库
docker-compose exec postgres pg_dump -U football football_data > backup_$(date +%Y%m%d).sql

# 恢复数据库
docker-compose exec -T postgres psql -U football football_data < backup_20260412.sql
```

### 6.2 日志查看

```bash
# 系统 A 日志
docker-compose logs -f system_a

# 系统 B 日志
docker-compose logs -f system_b

# 数据库日志
docker-compose logs -f postgres
```

---

## 七、运维命令

### 7.1 常用命令

```bash
# 启动所有服务
docker-compose up -d

# 停止所有服务
docker-compose down

# 重启服务
docker-compose restart system_a
docker-compose restart system_b

# 查看服务状态
docker-compose ps

# 查看资源使用
docker stats
```

### 7.2 更新服务

```bash
# 拉取最新代码
git pull

# 重新构建镜像
docker-compose build

# 重启服务
docker-compose up -d
```

---

## 八、故障排查

### 8.1 服务无法启动

```bash
# 检查端口占用
netstat -tulpn | grep 8000
netstat -tulpn | grep 8501
netstat -tulpn | grep 5432

# 检查容器日志
docker-compose logs system_a
docker-compose logs system_b
```

### 8.2 数据库连接失败

```bash
# 检查数据库容器
docker-compose logs postgres

# 测试数据库连接
docker-compose exec system_a python -c "from config.database import engine; engine.connect()"
```

### 8.3 爬虫无法抓取

1. 检查网络连接
2. 确认代理配置正确
3. 查看错误日志
4. 尝试手动触发任务测试

---

## 九、安全建议

1. **修改默认密码**：首次部署请修改数据库密码
2. **限制访问**：生产环境请配置防火墙规则
3. **定期备份**：建立定时备份机制
4. **日志监控**：配置日志收集和告警

---

## 十、联系支持

如有问题，请查看：
- API 文档：http://localhost:8000/docs
- 管理后台：http://localhost:8000/admin/