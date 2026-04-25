# 足球博彩数据处理系统 - 技术方案总结

## 一、项目概述

### 1.1 目标

整合两个现有项目（TitanProject 爬虫 + mftitan 数据处理），并新增 X 值计算模块，构建完整的足球博彩数据分析系统。

### 1.2 数据流

```
数据采集 (TitanProject) → X值计算 (新增) → 数据处理 (mftitan) → 用户界面
```

---

## 二、现有条件分析

### 2.1 TitanProject（数据采集层）

| 项目 | 详情 |
|------|------|
| **技术栈** | Python + requests + BeautifulSoup + SQLite |
| **核心文件** | `titan_crawler.py`, `league_scraper.py`, `db_utils.py` |
| **数据源** | vip.titan007.com（赔率）, zq.titan007.com（赛程） |
| **输出** | SQLite 数据库 (`data/football_data.db`) |
| **代码规模** | 10个Python文件 |

**核心功能:**
- 赛程爬虫：从 `info.titan007.com/jsData/matchResult/` 获取联赛赛程
- 赔率爬虫：从 `vip.titan007.com/changeDetail/` 获取盘口变动历史
- 盘口标准化：支持繁简盘口转换（平手、半球、一球等）
- 代理支持：集成 Oxylabs / NexIP 代理

**关键表结构:**
```sql
League_Schedules:  -- 比赛基本信息
  - Match_ID, League_ID, League_Name, Season
  - Match_Time, Home_Team, Away_Team
  - Score_FT, Score_HT
  - Crown_Initial_AH, Crown_Initial_OU, Crown_Initial_1x2  -- 初盘

Odds_Movements:    -- 赔率变动历史
  - Match_ID, Odds_Type, Is_Half_Time
  - Elapsed_Time, Score_At_Time
  - Update_Time, Status
  - Home_Rate, Handicap_Raw, Handicap_Std, Away_Rate
```

### 2.2 mftitan（数据处理层）

| 项目 | 详情 |
|------|------|
| **技术栈** | Python + pandas + SQLite + Streamlit |
| **核心文件** | `core/pipeline.py`, `core/classifier.py`, `core/models.py` |
| **输入** | Excel文件（手动导入） |
| **输出** | 分析报告、信号生成 |
| **代码规模** | 68个Python文件 |

**核心功能:**
- 数据读取器：从Excel读取比赛记录（`reader.py`）
- X值分类器：将X值分到9个区间（`classifier.py`）
- 轮次聚合：将数据按10轮为单位聚合（`round_aggregator.py`）
- 五大区间：将9个X值区间合并为5个大区间（`five_zone.py`）
- 护级评估：评估保级形势（`guard.py`）
- 强度升级：计算强度等级（`strength.py`）
- 信号生成：生成交易信号（`signal.py`）

**X值分类边界（默认）:**
```
zone 1: X ≤ -0.24
zone 2: -0.24 < X ≤ -0.22
zone 3: -0.22 < X ≤ -0.15
zone 4: -0.15 < X ≤ -0.08
zone 5: -0.08 < X ≤ -0.03
zone 6: -0.03 < X ≤ +0.07
zone 7: +0.07 < X ≤ +0.15
zone 8: +0.15 < X ≤ +0.23
zone 9: X > +0.23
```

### 2.3 现有数据流断裂点

```
TitanProject (爬虫)     [断层]        mftitan (数据处理)
      ↓                                ↓
 赔率变化数据                      需要Excel文件输入
 (SQLite)                             ↓
                               读取X值 → 分类 → 分析
                               (但X值从哪来？)
```

**问题:**
- TitanProject 只抓取赔率数据，不计算 X 值
- mftitan 假设 X 值已由外部计算好，直接从 Excel 读取
- 两个系统之间缺乏数据桥梁

---

## 三、技术难点分析

### 难点1: 动态菜单交互（第一阶段）

**问题:** 目标网站（zq.titan007.com）的联赛/赛季选择菜单是 JavaScript 动态渲染的，普通的 HTTP 请求无法获取完整数据。

**现有代码:** `league_scraper.py` 通过分析 JS 文件 URL 获取数据，但无法获取完整的菜单结构。

**解决方案:** 使用 Playwright 或 Selenium 模拟浏览器操作：
- 遍历国家菜单项
- 悬停等待联赛子菜单加载
- 悬停等待赛季子菜单展开
- 提取完整的联赛-赛季-URL 映射关系

**预估工作量:** 2-3 天

---

### 难点2: X值计算逻辑缺失（核心难点）

**问题:** 这是整个系统的核心，目前没有现成实现。

**需求分析:**

1. **数据来源:** 盘口变动历史页面
   - URL: `https://vip.titan007.com/changeDetail/handicap.aspx?id={match_id}&companyID=3`

2. **筛选条件:** 只使用「早」(Early) 区间数据

3. **判断逻辑:**
   - 红色 `*` 标记存在：比较客队 vs 主队赔率（客低有利）
   - 无红色 `*` 标记：比较主队 vs 客队赔率（主低有利）
   - 不符合条件：标记为「不适合」(not suitable)

**预估工作量:** **5-7 天

---

### 难点3: 数据组智能识别

**问题:** 比赛详细数据页面可能包含多个数据组（不同玩法、不同时段），需要智能选择正确的数据组。

**识别优先级:**
1. 优先选择 `class="techlist"` 中包含「联赛」名称的数据组
2. 或选择 `class="lsm2"` 中比赛轮次最多的数据组
3. 或选择排列第一的数据组

**预估工作量:** 1-2 天

---

### 难点4: 数据模型统一

**问题:** TitanProject 和 mftitan 使用不同的数据存储格式。

**现状:**
- TitanProject: SQLite 数据库
- mftitan: Excel 文件（手动导入）

**解决方案:** 统一到 SQLite 数据库 + 中间表

**预估工作量:** 1-2 天

---

### 难点5: 用户界面改造

**问题:** mftitan 现有界面是数据导入式的，需要改造为用户交互式。

**需求:**
- 联赛/赛季选择器
- 年份区间选择
- 实时爬取进度展示
- 结果展示（主队 | 比分 | 客队 | X值 | 历史链接）
- Excel 导出功能

**预估工作量:** 3-5 天

---

## 四、技术架构设计

### 4.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户交互层                               │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐ │
│  │  联赛/赛季选择  │  │  结果展示表格   │  │  Excel导出    │ │
│  │  (年份区间)     │  │  (分页/筛选)    │  │  (openpyxl)   │ │
│  └────────┬────────┘  └────────┬────────┘  └───────┬────────┘ │
└───────────┼────────────────────┼───────────────────┼──────────┘
            │                    │                   │
            ▼                    ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                        API服务层 (Flask/FastAPI)                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐ │
│  │  /crawl         │  │  /results       │  │  /export       │ │
│  │  触发爬取任务    │  │  获取结果数据   │  │  导出Excel    │ │
│  └────────┬────────┘  └────────┬────────┘  └───────┬────────┘ │
└───────────┼────────────────────┼───────────────────┼──────────┘
            │                    │                   │
            ▼                    ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                      核心计算层                                  │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐ │
│  │  menu_scraper   │  │  x_calculator   │  │  pipeline      │ │
│  │  (Playwright)   │  │  (X值计算)      │  │  (数据处理)    │ │
│  └────────┬────────┘  └────────┬────────┘  └───────┬────────┘ │
└───────────┼────────────────────┼───────────────────┼──────────┘
            │                    │                   │
            ▼                    ▼                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                      数据存储层 (SQLite)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │ League_      │  │ Odds_         │  │ Match_       │        │
│  │ Season_Index │  │ Movements     │  │ X_Values     │        │
│  └──────────────┘  └──────────────┘  └──────────────┘        │
└─────────────────────────────────────────────────────────────────┘
```

---

### 4.2 模块详细设计

#### 4.2.1 菜单抓取模块

```python
# modules/menu_scraper.py

class TitanMenuScraper:
    """使用 Playwright 抓取动态菜单结构"""
    
    def fetch_league_structure(self) -> dict:
        """
        输出格式:
        {
            "英格兰": {
                "英超": [
                    {"label": "2024-2025", "url": "..."},
                    {"label": "2023-2024", "url": "..."}
                ],
                "英冠": [...]
            },
            "西班牙": {...},
            ...
        }
        """
        pass
```

#### 4.2.2 X值计算模块

```python
# modules/x_calculator.py

class XValueCalculator:
    """X值计算核心逻辑"""
    
    def calculate_from_match(self, match_id: int) -> dict:
        """
        1. 获取盘口变动历史
        2. 筛选「早」区间数据
        3. 检测红色*标记
        4. 判断是否符合条件
        5. 计算X值
        """
        pass
    
    def _detect_star_mark(self, page_content: str) -> bool:
        """检测红色*标记"""
        pass
    
    def _compute_x(self, home_odds: float, away_odds: float, has_star: bool) -> float:
        """计算X值（公式待确认）"""
        pass
```

#### 4.2.3 数据组识别模块

```python
# modules/match_page_parser.py

class MatchPageParser:
    """智能识别正确的数据组"""
    
    def identify_correct_group(self, html: str) -> dict:
        """
        识别优先级:
        1. techlist 中包含「联赛」名称
        2. lsm2 中轮次最多
        3. 默认第一个
        """
        pass
```

#### 4.2.4 数据存储结构

```sql
-- 新增表: 联赛-赛季-URL索引
CREATE TABLE League_Season_Index (
    id INTEGER PRIMARY KEY,
    country TEXT,
    league_id INTEGER,
    league_name TEXT,
    season_label TEXT,
    season_url TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 新增表: X值计算结果
CREATE TABLE Match_X_Values (
    id INTEGER PRIMARY KEY,
    match_id INTEGER,
    home_team TEXT,
    away_team TEXT,
    score TEXT,
    target_team TEXT,           -- 计算依据队伍（主队/客队）
    has_star_mark BOOLEAN,      -- 是否有红色*标记
    x_value REAL,
    status TEXT,                -- 'success', 'not_suitable', 'no_data'
    calculation_note TEXT,
    movement_url TEXT,          -- 盘口历史页面链接
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (match_id) REFERENCES League_Schedules(Match_ID)
);
```

---

### 4.3 技术选型

| 功能模块 | 技术选型 | 理由 |
|----------|----------|------|
| 动态菜单抓取 | **Playwright** | 需要模拟悬停、等待JS加载 |
| Web框架 | **Flask** | 轻量快速，与现有Python项目兼容 |
| 数据存储 | **SQLite** | 现有项目已用，可无缝扩展 |
| 任务调度 | **Celery + Redis** | 支持异步任务、定时调度 |
| Excel处理 | **openpyxl** | 现有mftitan已使用 |
| 数据处理 | **pandas + numpy** | 高性能数值计算 |

---

## 五、后续任务规划

### 5.1 第一阶段：数据源整合（预计 3-5 天）

- [ ] 1.1 搭建 Playwright 环境
- [ ] 1.2 编写菜单抓取脚本
- [ ] 1.3 建立 League_Season_Index 表
- [ ] 1.4 定时更新联赛列表（可选）

### 5.2 第二阶段：X值计算模块（预计 5-7 天）

- [ ] 2.1 从现有 RPA 脚本迁移 X 值计算逻辑
- [ ] 2.2 编写盘口变动抓取模块
- [ ] 2.3 实现红色*标记检测
- [ ] 2.4 实现 X 值计算逻辑
- [ ] 2.5 建立 Match_X_Values 表

### 5.3 第三阶段：数据组智能识别（预计 2-3 天）

- [ ] 3.1 分析比赛详情页面结构
- [ ] 3.2 实现 techlist 识别逻辑
- [ ] 3.3 实现 lsm2 轮次比较逻辑
- [ ] 3.4 测试各种联赛页面

### 5.4 第四阶段：用户界面改造（预计 5-7 天）

- [ ] 4.1 搭建 Flask 项目结构
- [ ] 4.2 实现联赛/赛季选择器
- [ ] 4.3 实现爬取任务触发与进度展示
- [ ] 4.4 实现结果展示表格
- [ ] 4.5 实现 Excel 导出功能

### 5.5 第五阶段：测试与优化（预计 3-5 天）

- [ ] 5.1 单元测试覆盖
- [ ] 5.2 集成测试
- [ ] 5.3 性能优化
- [ ] 5.4 Bug 修复
- [ ] 5.5 部署上线

---

## 六、文件结构建议

```
/home/mk/project/football_system/
├── config/
│   ├── settings.py          # 配置文件
│   └── database.py          # 数据库配置
├── modules/
│   ├── menu_scraper.py      # 动态菜单抓取
│   ├── league_crawler.py    # 联赛赛程爬虫（复用TitanProject）
│   ├── odds_crawler.py      # 赔率变动爬虫（复用TitanProject）
│   ├── match_parser.py      # 比赛详情解析
│   ├── x_calculator.py      # X值计算核心
│   └── data_connector.py    # 数据桥梁
├── storage/
│   ├── database.py          # 数据库操作
│   └── models.py            # 数据模型
├── web/
│   ├── app.py               # Flask应用
│   ├── routes/
│   │   ├── index.py         # 主页路由
│   │   ├── crawl.py         # 爬取任务路由
│   │   └── results.py       # 结果展示路由
│   └── templates/
│       ├── base.html
│       ├── index.html
│       └── results.html
├── tasks/
│   ├── celery_app.py        # Celery配置
│   └── crawlers.py          # 爬取任务
├── tests/
│   ├── test_menu_scraper.py
│   ├── test_x_calculator.py
│   └── test_integration.py
├── requirements.txt
├── .env.example
└── README.md
```

---

## 七、总结

本项目需要整合两个现有项目并新增核心 X 值计算模块，主要技术难点在于：

1. **动态菜单抓取** - 需要使用 Playwright 模拟浏览器操作
2. **X值计算逻辑** - 从现有 RPA 脚本迁移核心算法
3. **数据流贯通** - 需要建立 SQLite 数据库作为数据桥梁
4. **用户界面改造** - 从文件导入式改为用户交互式

建议按阶段推进开发，先完成数据源整合和 X 值计算模块（5-7天），再进行用户界面改造。

---

*文档版本: v1.1*
*更新日期: 2026-04-09*