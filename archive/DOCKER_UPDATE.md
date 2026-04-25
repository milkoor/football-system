# Docker 更新说明

## 更新内容

### 1. system_b/Dockerfile 更新
- 移除了特定的 PyPI 镜像源配置，使用默认源以确保一致性
- 移除了不必要的 Playwright 依赖安装
- 添加了 curl 工具以支持健康检查

### 2. docker-compose.yml 更新
- 移除了过时的 `version` 字段（新版 Docker Compose 不再需要）
- 保持了所有其他配置不变

## 配置检查

### 环境变量配置
- **system_a**: 使用 `DATABASE_URL=postgresql://football:football_secure_pass@postgres:5432/football_data`
- **system_b**: 使用 `SYSTEM_A_API_URL=http://system_a:8000`

### 依赖文件
- **system_a/requirements.txt**: FastAPI, PostgreSQL, 爬虫相关依赖
- **system_b/requirements.txt**: Streamlit, pandas, PostgreSQL 客户端等

## 使用方法

### 在 Windows 上
1. 确保 Docker Desktop 正在运行
2. 双击 `start.bat` 启动所有服务
3. 等待几分钟让服务初始化
4. 访问 http://localhost:8501 (系统 B) 或 http://localhost:8000 (系统 A)

### 在 Linux/Mac 上
1. 确保 Docker 守护进程正在运行
2. 运行 `./start.sh` 启动所有服务
3. 等待几分钟让服务初始化
4. 访问 http://localhost:8501 (系统 B) 或 http://localhost:8000 (系统 A)

### 手动启动
```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

## 系统同步页面功能

更新后的系统同步页面功能更加清晰：

1. **快速操作**
   - 清除所有同步资料
   - 同步联赛列表（只同步联赛，不同步赛季）

2. **联赛信息**
   - 查看当前启用的联赛列表

3. **同步赛季赛程**
   - 选择具体联赛
   - 同步该联赛的赛季赛程
   - 查看比赛数量
   - 获取下一步操作指引

## 注意事项

- 首次启动会下载 Docker 镜像，可能需要几分钟
- 确保端口 8000、8501、5432 未被占用
- 爬虫需要网络访问 Titan007 网站
