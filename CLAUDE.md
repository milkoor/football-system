```
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.
```

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

**项目名称：** 足球数据分析系统  
**技术栈：** Python, FastAPI, Streamlit, PostgreSQL, Docker  
**项目类型：** 体育数据分析与量化分析平台  

## 核心架构

### 系统组成

项目由两个主要系统组成：

#### 系统 A - 数据基础设施
**目录：** `/mnt/d/project/football_system/system_a/`
- **功能：** 数据采集、标准化、存储
- **技术：** FastAPI + PostgreSQL + Playwright
- **核心模块：**
  - `api/` - REST API 接口
  - `scraper/` - 赔率爬虫（Playwright）
  - `modules/x_calculator.py` - X值计算引擎
  - `admin/` - 管理后台
  - `config/models.py` - 数据模型定义

#### 系统 B - 量化分析平台
**目录：** `/mnt/d/project/football_system/system_b/`
- **功能：** 数据分析、可视化、量化计算
- **技术：** Streamlit + SQLite + ETL 管线
- **核心模块：**
  - `views/` - Streamlit 页面视图
  - `original_pages/` - 原始页面实现
  - `etl/` - ETL 管线（X值分类→轮次聚合→五大区间→护级→强度→信号生成）
  - `modules/` - 数据连接器、关注管理、X值计算器
  - `utils/` - 工具函数（Excel处理、数据迁移）

## 常用命令

### 开发环境管理

```bash
# 启动项目（Docker）
cd /mnt/d/project/football_system
./start.sh  # Linux/Mac
start.bat   # Windows

# 停止项目
./stop.sh   # Linux/Mac
stop.bat    # Windows

# 查看状态
./status.sh  # Linux/Mac
status.bat   # Windows

# 查看日志
docker-compose logs -f
```

### 开发调试

```bash
# 检查系统状态
cd /mnt/d/project/football_system
curl -s "http://localhost:8000/health"
curl -s "http://localhost:8000/api/leagues" | head -20

# 测试X值计算
curl -X POST "http://localhost:8000/api/x-values/calculate?league_id=2064&season_label=2025-2026"

# 查看任务状态
curl -s "http://localhost:8000/api/crawl/jobs?limit=3" | python3 -m json.tool
```

## 核心功能实现

### X值计算流程

```python
# system_a/modules/x_calculator.py
class XValueCalculator:
    def calculate_from_match(self, match_id: int) -> Dict[str, Any]:
        """从赔率数据计算X值"""
        # 1. 获取赔率变动历史
        # 2. 筛选早/即状态的赔率
        # 3. 检查初盘是否有红色*标记
        # 4. 计算X值
        # 5. 返回计算结果
```

### 智能同步策略

```python
# system_a/api/routes/x_values.py
def run_calculate_task(job_id: int):
    """运行X值计算任务"""
    # 智能过滤：只计算未完成或需要重新计算的比赛
    # 已完成且已有X值的比赛会被跳过
```

### ETL 管线流程

```python
# system_b/etl/pipeline.py
class ETLPipeline:
    def run_etl(self, data_source='postgresql'):
        """执行完整的ETL流程"""
        # 1. 读取数据
        # 2. X值分类
        # 3. 轮次聚合
        # 4. 五大区间计算
        # 5. 护级判定
        # 6. 强度升级
        # 7. 信号生成
```

## 数据库设计

### 核心表结构

**主要表（PostgreSQL）：**
- `league_index` - 联赛索引
- `seasons` - 赛季信息
- `matches` - 比赛日程（含爬虫状态）
- `odds_movements` - 赔率变动历史
- `x_value_results` - X值计算结果
- `crawl_jobs` - 爬虫任务记录

### 智能同步字段

```sql
-- matches表中的关键字段
ALTER TABLE matches ADD COLUMN crawl_status VARCHAR(20) DEFAULT 'pending';
ALTER TABLE matches ADD COLUMN is_completed BOOLEAN GENERATED ALWAYS AS (
    CASE WHEN score_ft IS NOT NULL AND score_ft != '' THEN TRUE ELSE FALSE END
) STORED;
```

## 文件修改约定

### 修改前必读

1. 先阅读项目架构文档（`docs/schema.md`, `docs/deployment.md`）
2. 检查相关模块的实现方式
3. 保持与现有代码风格一致

### 提交信息规范

```
[功能模块] 变更说明

例如：
[X值计算] 修复赔率变动数据查询条件
[系统B] 重构导航菜单，新增views目录
```

## 关键文件说明

### 配置文件

- `docker-compose.yml` - Docker 编排配置
- `.env.example` - 环境变量示例
- `system_a/config/settings.py` - 系统A配置
- `system_b/config/settings.py` - 系统B配置

### 启动脚本

- `start.sh / start.bat` - 一键启动
- `stop.sh / stop.bat` - 停止服务
- `status.sh / status.bat` - 状态查看

## 常见问题

### 网络连接失败

如果无法连接到 GitHub：
```bash
# 检查网络
ping github.com

# 尝试再次推送
cd /mnt/d/project/football_system
git push origin master
```

### 端口占用

如果 8000/8501 端口被占用：
```bash
# 查找占用进程
lsof -i :8000  # Linux
netstat -ano | findstr :8000  # Windows

# 或修改 docker-compose.yml 中的端口映射
```

## 参考文档

- `README.md` - 项目简介与快速开始
- `docs/api_doc.md` - API 接口文档
- `docs/schema.md` - 数据库设计文档
- `docs/deployment.md` - 部署说明
- `docs/INTELLIGENT_SYNC_IMPLEMENTATION.md` - 智能同步规则说明
