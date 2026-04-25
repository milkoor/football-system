# 数据库 Schema 文档

**版本**: 1.0.0
**更新日期**: 2026-04-12
**数据库**: PostgreSQL

---

## 一、概述

本系统使用 PostgreSQL 存储足球相关数据，包括联赛、赛季、比赛、赔率变动和 X 值计算结果。

---

## 二、表结构

### 2.1 league_index - 联赛索引表

存储联赛基本信息，一个联赛可有多个赛季。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | SERIAL | PK | 自增主键 |
| country | VARCHAR(100) | NOT NULL | 国家 |
| league_id | INTEGER | NOT NULL | 联赛 ID（网站原始 ID） |
| league_name_zh | VARCHAR(200) | NOT NULL | 联赛名称（简体） |
| league_name_tw | VARCHAR(200) | NOT NULL | 联赛名称（繁体） |
| display_order | INTEGER | DEFAULT 0 | 显示顺序 |
| enabled | BOOLEAN | DEFAULT TRUE | 是否启用 |
| created_at | TIMESTAMP | DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMP | DEFAULT NOW() | 更新时间 |

**索引：**
- `idx_league_country` (country)
- `idx_league_enabled` (enabled)

---

### 2.2 seasons - 赛季表

存储联赛的赛季信息。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | SERIAL | PK | 自增主键 |
| league_id | INTEGER | FK → league_index.id | 关联联赛 |
| season_label | VARCHAR(50) | NOT NULL | 赛季标签（如 2024-2025） |
| season_start | DATE | | 赛季开始日期 |
| season_end | DATE | | 赛季结束日期 |
| status | VARCHAR(20) | DEFAULT 'active' | 状态：active/completed/archived |
| created_at | TIMESTAMP | DEFAULT NOW() | 创建时间 |

**索引：**
- `idx_season_league` (league_id)
- `idx_season_label` (season_label)

---

### 2.3 matches - 比赛日程表

存储比赛基本信息，同时作为爬虫任务队列。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| match_id | BIGINT | PK | 比赛 ID（网站原始 ID） |
| league_id | INTEGER | FK → league_index.id | 关联联赛 |
| season_id | INTEGER | FK → seasons.id | 关联赛季 |
| league_name | VARCHAR(200) | | 联赛名称 |
| season | VARCHAR(50) | | 赛季标签 |
| group_name | VARCHAR(100) | | 分组/分区 |
| round_name | VARCHAR(100) | | 轮次名称 |
| match_time | TIMESTAMP | | 开球时间 |
| home_team | VARCHAR(200) | | 主队名称（繁体） |
| away_team | VARCHAR(200) | | 客队名称（繁体） |
| score_ft | VARCHAR(20) | | 全场比分 |
| score_ht | VARCHAR(20) | | 半场比分 |
| crawl_status | VARCHAR(20) | DEFAULT 'pending' | 爬取状态 |
| retry_count | INTEGER | DEFAULT 0 | 重试次数 |
| error_message | TEXT | | 错误信息 |
| last_synced | TIMESTAMP | DEFAULT NOW() | 最后同步时间 |

**索引：**
- `idx_match_league` (league_id, season)
- `idx_match_status` (crawl_status)
- `idx_match_time` (match_time)

**crawl_status 状态说明：**
- `pending`: 待爬取
- `running`: 爬取中
- `completed`: 已完成
- `error`: 失败
- `nodata`: 无数据
- `live`: 直播中

---

### 2.4 odds_movements - 赔率变动表

存储比赛赔率的变动历史。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| movement_id | SERIAL | PK | 自增主键 |
| match_id | BIGINT | FK → matches.match_id | 关联比赛 |
| odds_type | VARCHAR(10) | NOT NULL | 赔率类型：AH/OU/1x2 |
| is_half_time | BOOLEAN | DEFAULT FALSE | 是否半场 |
| elapsed_time | VARCHAR(20) | | 比赛进行时间 |
| score_at_time | VARCHAR(20) | | 变动时比分 |
| update_time | TIMESTAMP | | 赔率变动时间 |
| status | VARCHAR(20) | | 状态：早/即/走 |
| home_rate | REAL | | 主队赔率/大球赔率/胜赔 |
| handicap_raw | VARCHAR(50) | | 原始盘口 |
| handicap_std | REAL | | 标准化盘口 |
| away_rate | REAL | | 客队赔率/小球赔率/负赔 |

**索引：**
- `idx_odds_match` (match_id, odds_type)
- `idx_odds_time` (update_time)
- `idx_odds_status` (status)

---

### 2.5 x_value_results - X值计算结果表

存储 X 值计算结果，供系统 B 读取使用。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | SERIAL | PK | 自增主键 |
| match_id | BIGINT | FK → matches.match_id | 关联比赛 |
| home_team | VARCHAR(200) | | 主队名称 |
| away_team | VARCHAR(200) | | 客队名称 |
| score | VARCHAR(20) | | 比赛比分 |
| target_team | VARCHAR(200) | | 计算依据队伍 |
| has_star_mark | BOOLEAN | | 是否有红色 * 标记 |
| x_value | REAL | | X 值 |
| status | VARCHAR(20) | | 状态：success/not_suitable/no_data |
| calculation_note | TEXT | | 计算备注 |
| movement_url | VARCHAR(500) | | 盘口历史页面链接 |
| created_at | TIMESTAMP | DEFAULT NOW() | 创建时间 |

**索引：**
- `idx_xvalue_match` (match_id)
- `idx_xvalue_status` (status)

---

### 2.6 crawl_jobs - 爬虫任务表

存储爬虫任务的执行记录。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | SERIAL | PK | 自增主键 |
| job_id | VARCHAR(100) | UNIQUE, NOT NULL | 任务 ID |
| league_id | INTEGER | | 联赛 ID |
| season_label | VARCHAR(50) | | 赛季标签 |
| status | VARCHAR(20) | DEFAULT 'pending' | 状态 |
| total_matches | INTEGER | DEFAULT 0 | 总场次 |
| completed_matches | INTEGER | DEFAULT 0 | 已完成 |
| failed_matches | INTEGER | DEFAULT 0 | 失败 |
| started_at | TIMESTAMP | | 开始时间 |
| completed_at | TIMESTAMP | | 完成时间 |
| error_message | TEXT | | 错误信息 |
| created_at | TIMESTAMP | DEFAULT NOW() | 创建时间 |

**索引：**
- `idx_job_status` (status)
- `idx_job_id` (job_id)

---

## 三、ER 关系图

```
┌─────────────┐       ┌─────────────┐
│ league_index│       │   seasons   │
├─────────────┤       ├─────────────┤
│ id (PK)     │◄──────│ league_id   │
│ league_id   │       │ id (PK)     │
└─────────────┘       └──────┬──────┘
                             │
                             ▼
                      ┌─────────────┐
                      │   matches   │
                      ├─────────────┤
                      │ match_id(PK)│
                      │ league_id   │
                      │ season_id   │
                      └──────┬──────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
       ┌────────────┐ ┌────────────┐ ┌────────────┐
       │ odds_      │ │ x_value_   │ │ crawl_     │
       │ movements  │ │ results    │ │ jobs       │
       ├────────────┤ ├────────────┤ ├────────────┤
       │ movement_id│ │ id (PK)    │ │ id (PK)    │
       │ match_id   │ │ match_id   │ │ job_id     │
       └────────────┘ └────────────┘ └────────────┘
```

---

## 四、初始化 SQL

```sql
-- 创建联赛索引表
CREATE TABLE league_index (
    id SERIAL PRIMARY KEY,
    country VARCHAR(100) NOT NULL,
    league_id INTEGER NOT NULL,
    league_name_zh VARCHAR(200) NOT NULL,
    league_name_tw VARCHAR(200) NOT NULL,
    display_order INTEGER DEFAULT 0,
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_league_country ON league_index(country);
CREATE INDEX idx_league_enabled ON league_index(enabled);

-- 创建赛季表
CREATE TABLE seasons (
    id SERIAL PRIMARY KEY,
    league_id INTEGER REFERENCES league_index(id),
    season_label VARCHAR(50) NOT NULL,
    season_start DATE,
    season_end DATE,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_season_league ON seasons(league_id);
CREATE INDEX idx_season_label ON seasons(season_label);

-- 创建比赛日程表
CREATE TABLE matches (
    match_id BIGINT PRIMARY KEY,
    league_id INTEGER REFERENCES league_index(id),
    season_id INTEGER REFERENCES seasons(id),
    league_name VARCHAR(200),
    season VARCHAR(50),
    group_name VARCHAR(100),
    round_name VARCHAR(100),
    match_time TIMESTAMP,
    home_team VARCHAR(200),
    away_team VARCHAR(200),
    score_ft VARCHAR(20),
    score_ht VARCHAR(20),
    crawl_status VARCHAR(20) DEFAULT 'pending',
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,
    last_synced TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_match_league ON matches(league_id, season);
CREATE INDEX idx_match_status ON matches(crawl_status);
CREATE INDEX idx_match_time ON matches(match_time);

-- 创建赔率变动表
CREATE TABLE odds_movements (
    movement_id SERIAL PRIMARY KEY,
    match_id BIGINT REFERENCES matches(match_id),
    odds_type VARCHAR(10) NOT NULL,
    is_half_time BOOLEAN DEFAULT FALSE,
    elapsed_time VARCHAR(20),
    score_at_time VARCHAR(20),
    update_time TIMESTAMP,
    status VARCHAR(20),
    home_rate REAL,
    handicap_raw VARCHAR(50),
    handicap_std REAL,
    away_rate REAL
);

CREATE INDEX idx_odds_match ON odds_movements(match_id, odds_type);
CREATE INDEX idx_odds_time ON odds_movements(update_time);
CREATE INDEX idx_odds_status ON odds_movements(status);

-- 创建 X 值结果表
CREATE TABLE x_value_results (
    id SERIAL PRIMARY KEY,
    match_id BIGINT REFERENCES matches(match_id),
    home_team VARCHAR(200),
    away_team VARCHAR(200),
    score VARCHAR(20),
    target_team VARCHAR(200),
    has_star_mark BOOLEAN,
    x_value REAL,
    status VARCHAR(20),
    calculation_note TEXT,
    movement_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_xvalue_match ON x_value_results(match_id);
CREATE INDEX idx_xvalue_status ON x_value_results(status);

-- 创建爬虫任务表
CREATE TABLE crawl_jobs (
    id SERIAL PRIMARY KEY,
    job_id VARCHAR(100) UNIQUE NOT NULL,
    league_id INTEGER,
    season_label VARCHAR(50),
    status VARCHAR(20) DEFAULT 'pending',
    total_matches INTEGER DEFAULT 0,
    completed_matches INTEGER DEFAULT 0,
    failed_matches INTEGER DEFAULT 0,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_job_status ON crawl_jobs(status);
CREATE INDEX idx_job_id ON crawl_jobs(job_id);
```