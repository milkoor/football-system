# FOOTBALL SYSTEM KNOWLEDGE

**项目:** Streamlit足球管理系统
**复杂度:** 高 (双系统架构)

## OVERVIEW
足球数据管理与分析系统，含爬虫系统(system_a)和前端系统(system_b)

## STRUCTURE
```
football_system/
├── system_a/              # 数据爬虫
│   ├── scraper/        # 爬虫模块
│   │   ├── odds_crawler.py
│   │   ├── league_crawler.py
│   │   ├── team_normalizer.py
│   │   └── handicap_normalizer.py
│   └── config/         # 配置
├── system_b/            # 显示前端
│   ├── pages/         # Streamlit页面
│   │   ├── dashboard.py
│   │   ├── 5_ETL執行.py
│   │   ├── 7_聯賽管理.py
│   │   ├── 8_隊伍分組.py
│   │   └── ...
│   ├── modules/       # 业务模块
│   ├── etl/         # ETL流程
│   └── config/      # 配置
└── docs/            # 中文文档
```

## WHERE TO LOOK
| 任务 | 位置 |
|------|------|
| 赔率爬虫 | system_a/scraper/odds_crawler.py |
| 联赛爬虫 | system_a/scraper/league_crawler.py |
| 数据ETL | system_b/etl/*.py |
| 前端页面 | system_b/pages/*.py |
| 配置 | system_b/config/settings.py |

## CONVENTIONS
- 中文文件名和界面
- Streamlit多页面架构
- ETL流程: 原始数据 → 处理 → 验证 → 展示
- 页码命名: 数字_功能.py

## ANTI-PATTERNS
- system_a和system_b数据库独立
- 避免循环依赖

## COMMANDS
```bash
# 启动爬虫系统
cd system_a && python -m scraper

# 启动前端
cd system_b && streamlit run app.py

# Docker
docker-compose up -d
```