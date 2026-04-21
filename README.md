# ⚽ 足球博彩数据系统

[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-green)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-orange)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-red)](https://streamlit.io/)

集成了爬虫、数据标准化、X值计算、ETL管线和决策信号生成的足球博彩量化分析系统。

---

## 📋 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        足球博彩数据系统                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────┐          ┌──────────────────────┐        │
│  │      系统 A          │          │      系统 B           │        │
│  │    数据基础设施      │   REST   │    量化分析平台       │        │
│  │                      │   API    │                      │        │
│  │  ┌──────────────┐   │◄────────►│  ┌──────────────┐    │        │
│  │  │  爬虫模块    │   │   Pull   │  │ X值计算模块  │    │        │
│  │  │ (Playwright) │   │          │  │ (分析逻辑)   │    │        │
│  │  └──────────────┘   │          │  └──────────────┘    │        │
│  │          ↓          │          │          ↓           │        │
│  │  ┌──────────────┐   │          │  ┌──────────────┐    │        │
│  │  │  数据标准化  │   │          │  │  ETL 管线    │    │        │
│  │  │ (队名/盘口)  │   │          │  │              │    │        │
│  │  └──────────────┘   │          │  └──────────────┘    │        │
│  │          ↓          │          │          ↓           │        │
│  │  ┌──────────────┐   │          │  ┌──────────────┐    │        │
│  │  │  PostgreSQL  │   │          │  │  Streamlit   │    │        │
│  │  │   (原始数据) │   │          │  │   (报表看板) │    │        │
│  │  └──────────────┘   │          │  └──────────────┘    │        │
│  │          ↓          │          │                       │        │
│  │  ┌──────────────┐   │          │                       │        │
│  │  │  FastAPI API │   │          │                       │        │
│  │  │ + 管理后台   │   │          │                       │        │
│  │  └──────────────┘   │          │                       │        │
│  └──────────────────────┘          └──────────────────────┘        │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## ✨ 功能特性

### 系统 A：数据基础设施

| 功能 | 说明 |
|------|------|
| 🕷️ 爬虫模块 | 使用 Playwright 抓取 Titan007 动态赔率数据 |
| 🔄 数据标准化 | 队名简繁转换、盘口标准化 |
| 📊 REST API | 完整的 CRUD 接口，供系统 B 调用 |
| 🎛️ 管理后台 | 联赛管理、任务监控、数据质量检查 |

### 系统 B：量化分析平台

| 功能 | 说明 |
|------|------|
| 📈 X值计算 | 从原始赔率数据计算 X 值（分析逻辑） |
| ⚙️ ETL 管线 | X值分类 → 轮次聚合 → 五大区间 → 护级 → 强度 → 信号生成 |
| 📊 报表看板 | 按分组/玩法/时段展示决策信号 |
| 🔍 信号追踪 | 比较不同版本的信号变化 |
| ⚙️ 参数设置 | 可配置算法参数 |
| 📥 数据同步 | 从系统 A API 拉取数据（手动 + 自动） |

---

## 🚀 快速开始

### 前置要求

- Docker & Docker Compose
- 4GB+ 可用内存

### 一键启动

```bash
# Windows
双击 start.bat

# Linux/Mac
./start.sh
```

### 访问地址

| 服务 | 地址 |
|------|------|
| 系统 A API | http://localhost:8000 |
| 系统 B 前端 | http://localhost:8501 |
| PostgreSQL | localhost:5432 |

---

## 📖 使用流程

### 完整工作流程

```
1. 选择联赛/赛季
       ↓
2. 触发数据采集（系统 A 爬虫抓取赔率）
       ↓
3. 计算 X 值（系统 B 分析逻辑）
       ↓
4. 执行 ETL 处理（分类→轮次聚合→五大区间→护级→强度→信号）
       ↓
5. 查看报表看板（决策信号）
       ↓
6. 信号追踪（版本对比）
```

### 数据同步

- **手动触发**: 在系统 B 前端选择联赛 → 点击"采集赔率数据"
- **自动同步**: 配置定时任务（APScheduler），默认每日凌晨执行

### 结算功能

系统支持自动结算比赛结果：

- **让球盘 (HDP)**: 根据盘口和比分计算主赢/客赢/走盘
- **大小球 (OU)**: 根据盘口和总进球数计算大/小

---

## 📚 API 接口文档

### 联赛接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/leagues` | GET | 获取联赛列表 |
| `/api/seasons/{league_id}` | GET | 获取赛季列表 |

### 比赛接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/matches` | GET | 获取比赛列表（支持分页、筛选） |
| `/api/matches/{match_id}/odds` | GET | 获取赔率变动历史 |
| `/api/matches/{match_id}/score` | POST | 更新比赛比分 |

### X值接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/x-values` | GET | 获取 X 值计算结果 |
| `/api/x-values` | POST | 保存 X 值计算结果 |

### 结算接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/matches/{match_id}/auto-settle` | POST | 自动结算单场比赛 |
| `/api/matches/auto-settle` | POST | 批量自动结算 |
| `/api/matches/{match_id}/settlement` | GET | 获取比赛结算结果 |

### 爬虫接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/crawl/start` | POST | 触发爬取任务 |
| `/api/crawl/stats` | GET | 获取爬取统计 |

---

## 🛠️ 管理命令

```bash
# 查看状态
./status.sh        # Linux/Mac
status.bat         # Windows

# 停止服务
./stop.sh          # Linux/Mac
stop.bat           # Windows

# 查看日志
docker-compose logs -f

# 重启服务
docker-compose restart
```

---

## 🔧 技术栈

| 组件 | 技术 |
|------|------|
| 后端框架 | FastAPI + Streamlit |
| 数据库 | PostgreSQL + SQLite |
| 爬虫 | Playwright + Requests |
| 任务调度 | APScheduler |
| 前端 | Jinja2 + Streamlit |
| 容器化 | Docker + Docker Compose |

---

## 📁 项目结构

```
football_system/
├── system_a/                 # 系统 A：数据基础设施
│   ├── config/              # 配置（settings, database, models）
│   ├── scraper/             # 爬虫模块
│   ├── api/                 # FastAPI 路由
│   │   └── routes/          # API 端点
│   ├── admin/               # 管理后台
│   └── requirements.txt
│
├── system_b/                 # 系统 B：量化分析平台
│   ├── config/              # 配置
│   ├── modules/             # 核心模块
│   │   ├── x_calculator.py  # X值计算
│   │   ├── data_connector.py# 数据连接器
│   │   └── settlement_calculator.py # 结算计算
│   ├── etl/                 # ETL 管线
│   │   ├── classifier.py    # X值分类
│   │   ├── round_aggregator.py
│   │   ├── five_zone.py     # 五大区间
│   │   ├── guard.py         # 护级判定
│   │   ├── strength.py      # 强度升级
│   │   ├── signal.py        # 信号生成
│   │   └── pipeline.py      # 主管道
│   ├── pages/               # Streamlit 页面
│   ├── utils/               # 工具函数
│   └── requirements.txt
│
├── docker-compose.yml       # Docker 编排
├── start.bat / start.sh     # 一键启动
├── stop.bat / stop.sh       # 一键停止
├── status.bat / status.sh   # 状态查看
└── README.md                # 本文件
```

---

## ⚠️ 注意事项

1. 首次启动会下载 Docker 镜像，可能需要几分钟
2. 确保端口 8000、8501、5432 未被占用
3. 爬虫需要网络访问 Titan007 网站

---

## 📄 许可证

MIT License

---

*最后更新: 2026-04-16*