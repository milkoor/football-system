# 代码审查报告

> 审查日期: 2026-05-10
> 审查范围: `system_a/`（数据层）和 `system_b/`（分析层）
> 文件数: 40+ 文件，约 5000+ 行代码
> **v1.2.0 更新说明**: 以下问题已于 2026-05-24 版本修复：结算逻辑三副本通过 System A 自动结算 API 整合 (#1.1, #1.2, #2.2, #3.1)、爬虫并发实现 ThreadPoolExecutor (#1.11, #6.1)、API 参数传递修正 `json=`→`params=` (#2.4, #2.5, #3.2)、`requirements.txt` 换行修复 (#2.1)、`crawl.py` 重复导入清理 (#1.10)、历史纪录页面 bug 修复、赛季 year_start 动态化。硬编码路径及 CORS 配置等问题暂未处理。详见 CHANGELOG。

---

## 目录

1. [System A — 关键问题](#1-system-a--关键问题)
2. [System B — 关键问题](#2-system-b--关键问题)
3. [跨系统问题](#3-跨系统问题)
4. [测试覆盖](#4-测试覆盖)
5. [安全评估](#5-安全评估)
6. [性能评估](#6-性能评估)
7. [总结与优先级排序](#7-总结与优先级排序)

---

## 1. System A — 关键问题

### 1.1 代码重复：两套几乎相同的 HandicapNormalizer

**严重性: HIGH**
**文件**: `system_a/scraper/handicap_normalizer.py` vs `system_a/modules/settlement_calculator.py`

`system_a/scraper/handicap_normalizer.py` 是专门独立的 Handicap normalization 类。而 `system_a/modules/settlement_calculator.py` 内部的 `AutoSettlementCalculator` 定义了**几乎完全相同**的 `HANDICAP_MAP`（第 37-48 行）和 `normalize_handicap()` 方法（第 50-79 行），但:

- `settlement_calculator.py` 的映射表只有 17 条，而 `handicap_normalizer.py` 有 50+ 条（简体+繁体、1.75~6.0）
- 两个 `normalize_handicap` 逻辑几乎一致，但 `settlement` 版本会先处理 `*` 号，并且缺少对 `handicap_normalizer.py` 中数字型盘口的完整解析

**建议**: 将 HandicapNormalizer 提升为共享模块，`AutoSettlementCalculator` 直接引用。

### 1.2 跨系统结算计算器重复（System A × System B）

**严重性: HIGH**
**文件**: `system_a/modules/settlement_calculator.py` vs `system_b/modules/settlement_calculator.py`

| 要素 | System A 版本 | System B 版本 |
|------|---------------|---------------|
| `HANDICAP_MAP` | 17 条 | 17 条（相同） |
| `normalize_handicap()` | 有，处理 `*` | 有，处理 `*`（略有不同—多了 `受让` 判断） |
| `calculate_hdp_settlement()` | 相同算法 | 相同算法 |
| `calculate_ou_settlement()` | 相同算法 | 相同算法 |
| 数据库访问 | 直接 `SessionLocal` | 通过 HTTP API |
| `auto_settle_match()` | 直接查 DB 写 DB | POST 到 System A API |
| `batch_auto_settle()` | 直接查 DB 写 DB | POST 到 System A API |

**问题**: 业务逻辑（比分解析、结算计算）在两个系统中是完全重复的。理论上 System B 应该**只通过 API 调用** System A 的结算，不需要自己实现 `calculate_*_settlement`。但 System B 的版本保留了这些方法。如果算法更新，两处必须同步修改。

另外，还有 **第三个** SettlementCalculator（`system_b/core/settlement.py`），但它是一个完全不同的实现——它解析**已存在的结算文字**而不是从比分计算结算。这是合理的（解析 vs 计算），但命名令人困惑。

**建议**: 从 `system_b/modules/settlement_calculator.py` 中移除 `calculate_hdp_settlement`、`calculate_ou_settlement`、`normalize_handicap`、`parse_score`（它们是 System A 逻辑的重复），只保留 API 调用包装器。

### 1.3 后台任务中传递 db Session 的风险

**严重性: HIGH**
**文件**: `system_a/api/routes/crawl.py` 第 251 行、`system_a/api/routes/leagues.py` 第 243/392 行

```python
# crawl.py:251
background_tasks.add_task(run_crawl_task, job.id, db)
```

SQLAlchemy Session 对象被传递到后台 `BackgroundTasks`。FastAPI 的 `get_db` 依赖在请求结束后会关闭 session。后台任务稍后运行时，该 session 可能已被关闭/释放。

`run_crawl_task` 内部确实重新创建了 `SessionLocal()`（第 58 行），所以传入的 `db` 实际上没有被使用。但传入的参数是未使用的，容易造成混淆。此外，`leagues.py` 的 `do_sync` 也正确创建了自己的 session，但父函数里的 `db` 在请求完成后也可能已无效。

**建议**: 删除后台函数签名中未使用的 `db` 参数，统一在函数内部创建 session。

### 1.4 CORS 宽松配置

**严重性: MEDIUM**
**文件**: `system_a/api/main.py` 第 52-57 行

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 所有来源
    allow_credentials=True, # 允许携带凭证
    ...
)
```

`allow_origins=["*"]` 配合 `allow_credentials=True` 是不安全的组合。根据 CORS 规范，当 `allow_credentials=True` 时，浏览器会忽略 `Access-Control-Allow-Origin: *`。虽然这实际上是安全的（浏览器会阻止），但它表明配置不够精确。

**建议**: 显式列出允许的来源，如 `["http://localhost:8501", "http://localhost:8000"]`。

### 1.5 .env 写入硬编码路径

**严重性: HIGH**
**文件**: `system_a/admin/routes.py` 第 383 行

```python
env_path = "/mnt/d/project/football_system/system_a/.env"
```

硬编码的绝对路径 `/mnt/d/project/football_system/system_a/.env`。这:

- 在 Docker 容器中会是错误的（容器内路径不同）
- 在 Windows 上会直接出错
- 在其他用户机器上会出错

**建议**: 使用 `os.path.dirname(__file__)` 或 `pathlib.Path(__file__).parent` 构建相对路径。

### 1.6 赛季列表硬编码默认值

**严重性: LOW**
**文件**: `system_a/scraper/league_crawler.py` 第 420 行

```python
return seasons if seasons else ["2024-2025", "2023-2024"]
```

硬编码的赛季字符串。到 2026 年，这些值就过时了。

**建议**: 根据当前年份动态生成，或者从配置中读取。

### 1.7 `clear-all` 端点未鉴权

**严重性: MEDIUM**
**文件**: `system_a/api/routes/leagues.py` 第 427-447 行

```python
@router.post("/leagues/clear-all")
async def clear_all_sync_data(db: Session = Depends(get_db)):
    """清除所有同步的数据"""
    db.query(OddsMovement).delete()
    db.query(XValueResult).delete()
    db.query(Match).delete()
    db.query(Season).delete()
    db.query(LeagueIndex).delete()
```

没有任何认证/鉴权，任何知道此端点的人可以一键清空整个数据库。DELETE 的顺序也有级联问题风险（但 SQLAlchemy 似乎处理了）。

**建议**: 添加简单的鉴权机制（如 API Key），或仅在生产环境移除该端点。

### 1.8 模拟数据（Mock Data）在生产代码中

**严重性: MEDIUM**
**文件**: `system_a/scraper/league_crawler.py` 第 18, 98-101, 211-212 行

```python
from scraper.mock_data import MOCK_LEAGUES, MOCK_MATCHES
...
if not leagues:
    logger.warning("无法获取真实联赛数据，使用模拟数据")
    leagues = MOCK_LEAGUES
```

当爬虫无法获取真实数据时静默回退到模拟数据。这意味着:

- 生产环境中如果爬虫出问题，用户可能看到的是假数据而不自知
- mock 数据不会标记为"模拟"

**建议**: 返回空列表或报错，让调用者决定是否用模拟数据。或者至少给数据打上标记。

### 1.9 联赛同步中 league_name_zh 和 league_name_tw 设置相同的值

**严重性: LOW**
**文件**: `system_a/api/routes/leagues.py` 第 203-204 行

```python
existing.league_name_tw = league_data.get("name", "")
existing.league_name_zh = league_data.get("name", "")
```

简体中文和繁体中文被设置为相同的值 `league_data.get("name")`。但实际上源数据中 `name2` 和 `name3` 分别是繁体和简体名。

**建议**: 从爬虫返回数据中区分 `name_zh` 和 `name_tw`。

### 1.10 `crawl.py` 不必要的重复导入

**严重性: LOW**
**文件**: `system_a/api/routes/crawl.py` 第 124-125 行

```python
from scraper.odds_crawler import OddsCrawler
temp_crawler = OddsCrawler()
```

在 `run_crawl_task` 函数内部，已经在上方第 56 行导入了 `OddsCrawler`，而且已经创建了 `crawler` 实例。这里为了调用 `is_match_completed` 又创建了一个新的实例，这是不必要的。更好的做法是直接让 `crawler.crawl_and_save` 返回更明确的结果，或者复用已有的实例。

**建议**: 删除多余导入和实例创建。

### 1.11 爬虫并发参数未被实际使用

**严重性: LOW**
**文件**: `system_a/scraper/odds_crawler.py` 第 28-29 行

```python
def __init__(self, concurrency: int = 3, ...):
    self.concurrency = concurrency
```

`concurrency` 参数被存储但**从未在类内部使用**。所有爬取都是在一个循环中顺序进行的（`crawl_and_save` 第 349 行的 for 循环）。

**建议**: 要么实现真正的并发（`ThreadPoolExecutor`），要么移除参数。

### 1.12 API 路由 `__init__.py` 未导出所有路由模块

**严重性: LOW**
**文件**: `system_a/api/routes/__init__.py`

```python
from api.routes import leagues, matches, odds, crawl
```

`x_values` 和 `settlement` 没有在 `__init__.py` 中导出。虽然 `main.py` 直接 `from api.routes import x_values, settlement` 所以不影响运行，但不一致。

**建议**: 同步更新 `__init__.py` 或干脆移除它（main.py 直接引用具体模块）。

### 1.13 `test_app.py` 中使用硬编码绝对路径

**严重性: MEDIUM**
**文件**: `system_a/test_app.py` 第 6 行

```python
sys.path.insert(0, '/mnt/d/project/football_system/system_a')
```

**建议**: 使用 `os.path.dirname(os.path.abspath(__file__))`。

### 1.14 管理后台 HTML 内联且不可维护

**严重性: MEDIUM**
**文件**: `system_a/admin/routes.py`

`settings_page()` 方法（第 194-371 行）和 `save_settings()` 方法（第 452-480 行）都包含内联的完整 HTML 页面。CSS 和 JS 混合在 Python 字符串中，导致约 300 行不可维护的代码。

但系统有 `admin/templates/` 目录（Jinja2 模板已配置），其他页面（dashboard、leagues、tasks、quality）都使用了模板。只有 settings 页面是特例。

**建议**: 将 settings 页面也迁移到 Jinja2 模板。

### 1.15 时间处理: 未使用时区感知的 `datetime`

**严重性: LOW**
**文件**: 多处

```python
from datetime import datetime
...
job.started_at = datetime.utcnow()
```

使用 naive `datetime.utcnow()`（不带时区信息）。当与带时区的数据交互时可能导致混淆。SQLAlchemy 的 `DateTime` 默认也是 naive。

**建议**: 如果使用 PostgreSQL，考虑使用 `DateTime(timezone=True)` 搭配 `datetime.now(timezone.utc)`。

---

## 2. System B — 关键问题

### 2.1 `requirements.txt` 中 opencc 依赖拼写错误

**严重性: HIGH**
**文件**: `system_b/requirements.txt` 第 27 行

```
python-json-logger==2.0.7opencc-python-reimplemented
```

这一行将 `python-json-logger==2.0.7` 与 `opencc-python-reimplemented` 拼在了一起没有换行。这会导致:

- `pip install` 会尝试安装 `python-json-logger==2.0.7opencc-python-reimplemented`（一个不存在的版本）
- `opencc-python-reimplemented` 不会被安装

**建议**: 拆分为两行:
```
python-json-logger==2.0.7
opencc-python-reimplemented
```

### 2.2 System B `AutoSettlementCalculator` 包含重复的业务逻辑

**严重性: HIGH**
**文件**: `system_b/modules/settlement_calculator.py` 第 42-271 行

整个 `HANDICAP_MAP`、`normalize_handicap`、`parse_score`、`calculate_hdp_settlement`、`calculate_ou_settlement` 都是 System A `system_a/modules/settlement_calculator.py` 中相同逻辑的直接拷贝。

System B 本意是通过 API 调用 System A 来结算，但它仍然保留了完整的本地结算能力。这导致:

- 两处必须同步修改
- 维护成本翻倍
- 在 System B 中可能绕过 System A 的结算逻辑

**建议**: 移除这些方法，只保留 API 调用包装器。如果出于离线需求需要保留，应提取为共享库。

### 2.3 `core/settlement.py` 和 `modules/settlement_calculator.py` 命名冲突

**严重性: MEDIUM**
**文件**: `system_b/core/settlement.py` vs `system_b/modules/settlement_calculator.py`

两个文件都包含"settlement"相关的类:

| 文件 | 类名 | 功能 |
|------|------|------|
| `core/settlement.py` | `SettlementCalculator` | 解析已存在的结算文字 |
| `modules/settlement_calculator.py` | `AutoSettlementCalculator` | 通过 API 调用 System A 自动结算 |

两个类名相似、功能相关但不同。开发人员容易混淆，特别是在搜索"settlement"相关代码时。

**建议**: 将 `core/settlement.py` 重命名为 `core/settlement_parser.py`，类名改为 `SettlementParser`。

### 2.4 API 调用中传递 params 的方式（POST 请求）

**严重性: MEDIUM**
**文件**: `system_b/modules/settlement_calculator.py` 第 329 行、第 453 行

```python
response = client.post(url, json=params)  # 发送 JSON body
```

但 System A 的端点 `POST /api/matches/auto-settle` 期望的是 `Query` 参数:

```python
# system_a/api/routes/settlement.py:68
async def batch_auto_settle(
    league_id: Optional[int] = Query(None),
    season: Optional[str] = Query(None),
```

`league_id` 和 `season` 是 Query 参数，而非 JSON body 参数。所以:
```python
client.post(url, params=params)  # ✅ 应该用 params=
client.post(url, json=params)   # ❌ 用了 json=，服务器不会解析
```

这是一个实际会影响功能的 bug。批量结算功能在跨系统调用时实际上不会正确传递参数。

**建议**: 将 `json=params` 改为 `params=params`。

### 2.5 `update_score_and_settle` 传递参数格式错误

**严重性: HIGH**
**文件**: `system_b/modules/settlement_calculator.py` 第 391 行

```python
response = client.post(url, json={"score": score})
```

System A 的端点期望的是:

```python
# system_a/api/routes/settlement.py:109
async def update_match_score(
    match_id: int,
    score_ft: str = ...,
    score_ht: Optional[str] = None,
```

`score_ft` 是 query 参数（`=...` 表示必需），而非 JSON body 参数。所以 `json={"score": score}` 不会被正确解析。参数名也不匹配（`score` vs `score_ft`）。

**建议**: 使用 `params={"score_ft": score}`。

### 2.6 自动同步在非 Docker 环境下行为

**严重性: INFO**
**文件**: `system_b/app.py` 第 21 行

```python
if os.getenv("IS_DOCKER") is None:
    ...
    scheduler = SyncScheduler(...)
```

当 `IS_DOCKER` 未设置时启动调度器，即本地开发环境启动。但 Streamlit 的开发方式是多进程/多线程的，每次页面重载都可能初始化多个调度器实例。

**建议**: 添加全局锁或文件锁来防止重复初始化。

### 2.7 核心模块 `__init__.py` 仅导出部分类

**严重性: LOW**
**文件**: `system_b/core/__init__.py`

```python
from core.classifier import XValueClassifier
from core.config_store import ConfigStore, get_store
from core.five_zone import FiveZoneGrouper
...
```

缺少几个关键类的导出: `TeamMatcher`、`RecordSplitter`、`QualityChecker`、`SeasonAggregator`、`Preprocessor`、`Reader` 等。虽然可以通过 `from core.matcher import TeamMatcher` 直接导入，但 `__init__.py` 的"便利导出"角色不完整。

**建议**: 审查 `core/` 下的所有模块，确保公共 API 类都通过 `__init__.py` 导出。

### 2.8 test_path 硬编码

**严重性: LOW**
**文件**: `system_a/tests/test_admin_settings.py` 第 11 行

```python
sys.path.insert(0, '/mnt/d/project/football_system/system_a')
```

多个测试文件依赖硬编码的绝对路径，在另一台机器上就会失效。

**建议**: 用 `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` 动态计算。

### 2.9 测试中使用 `.env` 文件，可能污染实际环境

**严重性: MEDIUM**
**文件**: `system_a/tests/test_admin_settings.py`

测试会读取、修改、恢复 `/mnt/d/project/football_system/system_a/.env` 文件。如果测试异常退出（如 `KeyboardInterrupt`），`.env` 可能处于被修改的状态。

**建议**: 使用 `tmp_path` pytest fixture 或 `tempfile` 创建临时 `.env`，修改 `Settings` 的 `env_file` 路径或使用环境变量覆盖。

---

## 3. 跨系统问题

### 3.1 结算逻辑三副本

| 位置 | 功能 | 备注 |
|------|------|------|
| `system_a/modules/settlement_calculator.py` | 从比分+盘口计算结算 | 直接访问 DB |
| `system_b/modules/settlement_calculator.py` | **复制了**相同计算逻辑 + API 包装 | 应只做 API 包装 |
| `system_b/core/settlement.py` | 解析已存在的结算文字 | 不同功能，但命名冲突 |

**严重性: HIGH**

### 3.2 API 参数传递不匹配

System B 的 `settlement_calculator.py` 在调用 System A API 时使用 `json=` 传递本应是 `params=` 的参数。导致批量结算和比分更新功能在跨系统调用时实际不可用。

**严重性: HIGH**

### 3.3 数据一致性保证

没有显式的机制保证 System B 的 SQLite 数据库 (`db/quant.db`) 与 System A 的 PostgreSQL 数据保持一致。ETL 管道运行在 `match_records` 表上，但没有数据版本或同步检查点机制。

**严重性: MEDIUM**

### 3.4 无统一配置管理

两个系统各自有独立的 `config/settings.py`，使用 `pydantic-settings`，但 `.env` 文件的读取路径不同。Docker 环境下使用相同的 `.env`，但在本地开发时可能使用不同的 `.env` 文件。

**严重性: LOW**

---

## 4. 测试覆盖

### 4.1 System A 测试

| 文件 | 类型 | 覆盖内容 |
|------|------|----------|
| `tests/test_admin_settings.py` | 单元测试 | 管理后台设置页面（3 个测试） |
| `tests/test_admin_settings_integration.py` | 集成测试 | 设置页面 GET/POST（1 个测试） |
| `tests/test_settings_simple.py` | 简单测试 | 配置模块基本功能 |
| `test_app.py` | 冒烟测试 | 应用启动、健康检查 |

**未测试的模块:**
- 所有 API 路由（leagues, matches, odds, crawl, x_values, settlement）
- 爬虫模块（odds_crawler, league_crawler）
- 标准化模块（handicap_normalizer, team_normalizer）
- 结算计算器（settlement_calculator）
- 管理后台核心逻辑（dashboard, quality, tasks）

System A 只有 3 个 pytest 文件 + 1 个冒烟测试，覆盖率极低。

### 4.2 System B 测试

| 类别 | 数量 | 覆盖内容 |
|------|------|----------|
| Property-based (`_properties`) | 14+ | classifier, config_store, five_zone, guard, matcher, mismatch_detector, pipeline, quality, round_aggregator, signal, strength 等 |
| 传统单元测试 | 10+ | settlement, preprocessor, round_aggregator, mismatch_detector, migration, reader |
| 集成/UI 测试 | 5+ | etl_integration, ui_workflow, sync_settings, data_consistency, system_b_settlement |

**特点:**
- 大量使用 `hypothesis` property-based testing
- `core/` 模块覆盖较好（10+ 个模块有对应测试）
- `modules/` 覆盖较差（data_connector, follow_list, auto_sync 无测试）
- `views/` 完全无直接测试
- `system_b/modules/settlement_calculator.py` 无测试

---

## 5. 安全评估

### 5.1 发现的 Issues

| Issue | 严重性 | 位置 |
|-------|--------|------|
| CORS 全通 + 允许凭证 | Medium | `system_a/api/main.py:52-54` |
| 数据清空端点无鉴权 | Medium | `system_a/api/routes/leagues.py:427` |
| .env 含明文密码 | Low | `.env` 中 PostgreSQL 密码明文 |
| 硬编码路径暴露目录结构 | Low | `admin/routes.py:383` |
| 模拟数据未标记 | Low | `scraper/league_crawler.py` |
| SQLAlchemy 潜在 SQL 注入可能 | Low | 所有动态 filter/order_by 使用 ORM，总体安全 |

### 5.2 正面

- 所有数据库操作都使用 SQLAlchemy ORM，避免了直接的 SQL 注入风险
- 爬虫使用了 retry 和延迟，行为合理
- 没有在生产代码中发现硬编码的 API key 或 secret
- System B 的 API 调用有适当的错误处理

---

## 6. 性能评估

### 6.1 已知问题

| Issue | 严重性 | 描述 |
|-------|--------|------|
| 爬虫无并发 | Medium | `concurrency` 参数存在但不使用 |
| N+1 查询 | Low | admin 页面为每个联赛查询赛季数（`leagues_page` 中的循环查询） |
| 后台任务使用独立 Session | OK | 后台任务正确创建自己的 Session，避免线程安全问题 |
| 数据库连接池配置 | OK | `pool_size=10, max_overflow=20` 配置合理 |

---

## 7. 总结与优先级排序

### 立刻修复（影响功能）

| # | Issue | 文件 | 影响 |
|---|-------|------|------|
| 1 | `requirements.txt` 依赖拼写错误 | `system_b/requirements.txt:27` | `opencc-python-reimplemented` 无法安装 |
| 2 | System B API 调用使用 `json=` 而非 `params=` | `system_b/modules/settlement_calculator.py:329,453` | 批量结算和比分更新功能跨系统不可用 |
| 3 | System B `update_score_and_settle` 参数名不匹配 | `system_b/modules/settlement_calculator.py:391` | 跨系统比分更新功能不可用 |

### 一周内修复

| # | Issue | 文件 |
|---|-------|------|
| 4 | `admin/routes.py` .env 路径硬编码 | `system_a/admin/routes.py:383` |
| 5 | 后台任务传入未使用的 db session | `system_a/api/routes/crawl.py:251`, `leagues.py:243,392` |
| 6 | 结算逻辑三副本 | `system_a/modules/` + `system_b/modules/` + `system_b/core/` |
| 7 | 测试文件路径硬编码 | `system_a/test_app.py:6`, `tests/test_admin_settings.py:11` |

### 建议改善

| # | Issue | 优先度 |
|---|-------|--------|
| 8 | 移除 System B 中重复的计算逻辑 | High |
| 9 | 管理后台内联 HTML → Jinja2 模板 | Medium |
| 10 | CORS 精确来源配置 | Medium |
| 11 | 数据清空端点添加鉴权 | Medium |
| 12 | 模拟数据回退逻辑标记 | Medium |
| 13 | 爬虫实现真正的并发 | Low |
| 14 | N+1 查询优化 | Low |
| 15 | 硬编码赛季字符串 | Low |
| 16 | `core/settlement.py` 重命名 | Low |
| 17 | 联赛同步区分繁简中文 | Low |

---

## 附录 A: 文件清单

**审查的 `system_a/` 文件（17 个）:**

| 文件 | 行数 | 审查结果 |
|------|------|----------|
| `api/main.py` | 92 | CORS 配置松散 |
| `api/routes/leagues.py` | 447 | Session 传递问题, clear-all 无鉴权 |
| `api/routes/matches.py` | 175 | 良好 |
| `api/routes/odds.py` | 78 | 良好 |
| `api/routes/crawl.py` | 297 | 重复导入, Session 传递 |
| `api/routes/x_values.py` | 136 | 良好 |
| `api/routes/settlement.py` | 138 | 良好 |
| `config/models.py` | 139 | 良好 |
| `config/database.py` | 39 | 良好 |
| `config/settings.py` | 52 | 良好 |
| `scraper/odds_crawler.py` | 384 | concurrency 未使用 |
| `scraper/league_crawler.py` | 451 | 模拟数据静默回退 |
| `scraper/handicap_normalizer.py` | 100 | 良好 |
| `scraper/team_normalizer.py` | 198 | 良好 |
| `admin/routes.py` | 481 | 硬编码路径, 内联 HTML |
| `modules/settlement_calculator.py` | 405 | 与 scraper 模块重复 |
| `tests/test_admin_settings.py` | 196 | 绝对路径, .env 污染 |

**审查的 `system_b/` 文件（6 个）:**

| 文件 | 行数 | 审查结果 |
|------|------|----------|
| `requirements.txt` | 29 | **拼写错误** |
| `app.py` | 85 | 调度器可能重复初始化 |
| `core/settlement.py` | 144 | 好, 但命名冲突 |
| `modules/settlement_calculator.py` | 530 | **API 参数错误**, 重复逻辑 |
| `config/settings.py` | 45 | 良好 |
| `core/__init__.py` | 29 | 导出不完整 |

---

*审查完成: 40+ 文件, 发现 20+ issues (3 Critical, 5 High, 7 Medium, 6 Low)*