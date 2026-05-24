# 交付前验证流程

> 版本: 1.2  
> 适用范围: 完整全流程人工 + 半自动化验证  
> 预估耗时: 30-45 分钟（含 Docker 启动）

---

## 目录

1. [前置检查（5 分钟）](#1-前置检查)
2. [System A 后端验证（10 分钟）](#2-system-a-后端验证)
3. [System B 前端完整操作流程（20 分钟）](#3-system-b-前端完整操作流程)
4. [ETL 管线验证](#4-etl-管线验证)
5. [异常场景与边界测试](#5-异常场景与边界测试)
6. [回归检查清单](#6-回归检查清单)
7. [交付签字标准](#7-交付签字标准)

---

## 1. 前置检查

### 1.1 环境启动

```bash
# 1. 构建并启动所有服务
./start.sh

# 2. 等待所有服务健康
./status.sh
# 期望输出:
# ✅ 系统 A API:   http://localhost:8000
# ✅ 系统 B 前端:  http://localhost:8501
# ✅ PostgreSQL:   localhost:5432
```

### 1.2 基础健康检查

| 检查项 | 命令 | 期望结果 |
|--------|------|----------|
| System A root | `curl http://localhost:8000/` | `{"status":"ok","service":"足球数据系统 A"}` |
| System A health | `curl http://localhost:8000/health` | `{"status":"healthy"}` |
| System B UI | 浏览器打开 `http://localhost:8501` | 首页正常渲染，显示系统介绍 |

### 1.3 数据库连接验证

```bash
# 检查 PostgreSQL 中是否有初始化表
docker exec football_system_db psql -U football -d football_data -c "\dt"
# 期望: 至少看到 league_index, seasons, matches, odds_movements,
#        x_value_results, crawl_jobs 等表
```

### 1.4 依赖检查

```bash
# 验证 pip 依赖无冲突
docker compose run --rm system_a pip check || echo "⚠️ pip check failed"
docker compose run --rm system_b pip check || echo "⚠️ pip check failed"
```

---

## 2. System A 后端验证

### 2.1 API 端点验证

按模块逐一验证每个 REST API 端点。

#### 2.1.1 联赛管理

```bash
# ----- GET /api/leagues -----
curl -s http://localhost:8000/api/leagues | python3 -m json.tool
# 期望: 返回联赛列表（或空数组 []），每个联赛有 id, league_id, country, league_name_zh 等字段

# ----- GET /api/leagues?enabled=true（带筛选）-----
curl -s "http://localhost:8000/api/leagues?enabled=true&limit=3" | python3 -m json.tool
# 期望: 最多返回 3 条 enabled=true 的联赛

# ----- POST /api/leagues （创建联赛）-----
curl -s -X POST http://localhost:8000/api/leagues \
  -H "Content-Type: application/json" \
  -d '{"country":"Test","league_id":99999,"league_name_zh":"测试联赛","league_name_tw":"測試聯賽"}' | python3 -m json.tool
# 期望: 返回创建后的对象，包含 id

# ----- GET /api/leagues/{id} （按 ID 查询）-----
# 将 {id} 替换为上一步返回的 id
curl -s http://localhost:8000/api/leagues/1 | python3 -m json.tool
# 期望: 返回指定联赛详情

# ----- PUT /api/leagues/{id} （更新联赛）-----
curl -s -X PUT http://localhost:8000/api/leagues/1 \
  -H "Content-Type: application/json" \
  -d '{"country":"Test","league_id":99999,"league_name_zh":"更新的联赛","league_name_tw":"更新的聯賽"}' | python3 -m json.tool
# 期望: league_name_zh 变为 "更新的联赛"

# ----- DELETE /api/leagues/{id} （删除联赛）-----
curl -s -X DELETE http://localhost:8000/api/leagues/1
# 期望: {"message":"联赛已删除"}
```

#### 2.1.2 赛季管理

```bash
# ----- GET /api/seasons/{league_id} -----
curl -s http://localhost:8000/api/seasons/1 | python3 -m json.tool
# 期望: 返回该联赛的赛季列表（或空数组）

# ----- POST /api/seasons （创建赛季）-----
curl -s -X POST http://localhost:8000/api/seasons \
  -H "Content-Type: application/json" \
  -d '{"league_id":1,"season_label":"2025-2026","status":"active"}' | python3 -m json.tool
```

#### 2.1.3 比赛管理

```bash
# ----- GET /api/matches -----
curl -s "http://localhost:8000/api/matches?page=1&page_size=5" | python3 -m json.tool
# 期望: 返回 {total: N, matches: [...]}，每条比赛包含 match_id, league_id, home_team, away_team, score_ft 等

# ----- GET /api/matches/{match_id} -----
curl -s http://localhost:8000/api/matches/1 | python3 -m json.tool

# ----- POST /api/matches/batch （批量创建）-----
curl -s -X POST http://localhost:8000/api/matches/batch \
  -H "Content-Type: application/json" \
  -d '[{"match_id":88888,"league_id":1,"home_team":"主队A","away_team":"客队B","season":"2025-2026"}]' | python3 -m json.tool
# 期望: {"message":"已处理 1 条记录","created":1}
```

#### 2.1.4 赔率查询

```bash
# ----- GET /api/matches/{match_id}/odds -----
curl -s http://localhost:8000/api/matches/88888/odds | python3 -m json.tool
# 期望: 返回赔率记录（或空 {total:0, movements:[]}）

# ----- GET /api/odds/latest?odds_type=AH -----
curl -s "http://localhost:8000/api/odds/latest?odds_type=AH&limit=5" | python3 -m json.tool
```

#### 2.1.5 X 值管理

```bash
# ----- GET /api/x-values -----
curl -s http://localhost:8000/api/x-values | python3 -m json.tool

# ----- POST /api/x-values （创建 X 值结果）-----
curl -s -X POST http://localhost:8000/api/x-values \
  -H "Content-Type: application/json" \
  -d '{"match_id":88888,"x_value":0.5,"status":"success"}' | python3 -m json.tool

# ----- PUT /api/x-values/{match_id} （更新 X 值）-----
curl -s -X PUT http://localhost:8000/api/x-values/88888 \
  -H "Content-Type: application/json" \
  -d '{"match_id":88888,"x_value":0.75,"status":"success"}' | python3 -m json.tool
```

#### 2.1.6 爬虫任务

```bash
# ----- GET /api/crawl/jobs -----
curl -s http://localhost:8000/api/crawl/jobs | python3 -m json.tool

# ----- GET /api/crawl/stats -----
curl -s http://localhost:8000/api/crawl/stats | python3 -m json.tool
# 期望: 返回 total_matches, pending, completed, error, active_jobs

# ----- POST /api/crawl/start（启动爬虫任务）-----
# 注意: 这会在后台启动异步爬虫
curl -s -X POST http://localhost:8000/api/crawl/start \
  -H "Content-Type: application/json" \
  -d '{"league_id":1}' | python3 -m json.tool
# 期望: 返回创建的 CrawlJob 对象，status="pending"
```

#### 2.1.7 结算功能

```bash
# ----- POST /api/matches/{match_id}/score（更新比分并自动结算）-----
curl -s -X POST "http://localhost:8000/api/matches/88888/score?score_ft=2-1" | python3 -m json.tool
# 期望: 比分更新成功，返回结算结果

# ----- GET /api/matches/{match_id}/settlement（查询结算结果）-----
curl -s http://localhost:8000/api/matches/88888/settlement | python3 -m json.tool
# 期望: 返回包含 settlement, settlement_value, home_away_direction 的结算信息

# ----- POST /api/matches/{match_id}/auto-settle（触发自动结算）-----
curl -s -X POST http://localhost:8000/api/matches/88888/auto-settle | python3 -m json.tool
```

#### 2.1.8 管理员界面

```bash
# HTML 页面 - 检查返回 200 且包含正确标题
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/admin/
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/admin/leagues
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/admin/tasks
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/admin/quality
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/admin/settings
# 期望: 全部返回 200
```

#### 2.1.9 联赛同步与赛季统计（v1.2.0 新增验证）

```bash
# ----- POST /api/leagues/sync-from-site（从网站同步联赛）-----
curl -s -X POST http://localhost:8000/api/leagues/sync-from-site | python3 -m json.tool
# 期望: {"message":"联赛同步任务已启动","status":"started","job_id":"..."}

# ----- POST /api/leagues/batch-sync-seasons（批量同步赛季）-----
curl -s -X POST http://localhost:8000/api/leagues/batch-sync-seasons | python3 -m json.tool
# 期望: {"message":"全联赛批量同步任务已启动","status":"started","job_id":"..."}

# ----- GET /api/season-stats（赛季统计）-----
curl -s http://localhost:8000/api/season-stats | python3 -m json.tool
# 期望: {"total_seasons": N, "synced_seasons": M}

# ----- POST /api/leagues/clear-all（清除所有同步数据）-----
curl -s -X POST http://localhost:8000/api/leagues/clear-all | python3 -m json.tool
# 期望: {"message":"所有同步数据已清除"}
```

### 2.2 错误路径测试

| 测试场景 | 请求 | 期望结果 |
|----------|------|----------|
| 不存在的联赛 | `GET /api/leagues/999999` | 404 `{"detail":"联赛不存在"}` |
| 不存在的比赛 | `GET /api/matches/999999` | 404 `{"detail":"比赛不存在"}` |
| 不存在的任务 | `GET /api/crawl/jobs/999999` | 404 `{"detail":"任务不存在"}` |
| 缺少必填参数 | `GET /api/odds/latest` | 422 参数验证错误 |
| 无效分页参数 | `GET /api/matches?page=-1` | 422 ge=1 验证失败 |

---

## 3. System B 前端完整操作流程

> 此部分需要人工在浏览器中操作 `http://localhost:8501`

### 3.1 首页加载

| 步骤 | 操作 | 期望结果 |
|------|------|----------|
| 1.1 | 访问 `http://localhost:8501` | 首页渲染：标题"欢迎使用足球数据分析系统" |
| 1.2 | 检查左侧导航 | 看到 5 个导航分组：首页、数据准备、数据分析、结果输出、运维 |
| 1.3 | 检查首页指标 | 显示"活跃联赛数量"和"总比赛数量"指标 |
| 1.4 | 验证导航可点击 | 点击各导航项，页面正确跳转 |

### 3.2 系统同步 → 联赛管理

| 步骤 | 操作 | 期望结果 |
|------|------|----------|
| 2.1 | 导航 → 数据准备 → 系统同步 | 页面加载无报错 |
| 2.2 | 点击"从网站同步联赛列表" | 提示同步任务已启动 |
| 2.3 | 导航 → 数据准备 → 联赛管理 | 页面加载，看到从网站同步的联赛列表 |
| 2.4 | 搜索/筛选联赛 | 筛选功能正常工作 |
| 2.5 | 选择一个联赛，同步赛季赛程 | 同步任务启动，后台执行 |
| 2.6 | 同步后检查该联赛是否有比赛数据 | 比赛列表中出现记录 |

### 3.3 数据导入

| 步骤 | 操作 | 期望结果 |
|------|------|----------|
| 3.1 | 导航 → 数据准备 → 数据导入 | 页面加载 |
| 3.2 | 选择联赛 | 下拉菜单显示可用联赛 |
| 3.3 | 选择赛季 | 显示该联赛可用赛季 |
| 3.4 | 点击同步/导入 | 数据开始同步 |

### 3.4 队伍分组设置

| 步骤 | 操作 | 期望结果 |
|------|------|----------|
| 4.1 | 导航 → 数据准备 → 队伍分组 | 页面加载 |
| 4.2 | 查看/管理分组配置 | 分组正常展示 |

### 3.5 参数设定 （ETL 前置）

| 步骤 | 操作 | 期望结果 |
|------|------|----------|
| 5.1 | 导航 → 数据分析 → 参数设定 | 页面加载 |
| 5.2 | 检查 X 值边界参数 | 显示默认值或已保存的值 |
| 5.3 | 检查轮次块大小等参数 | 字段展示正常 |
| 5.4 | 修改参数并保存 | 保存成功提示 |

### 3.6 ETL 执行

| 步骤 | 操作 | 期望结果 |
|------|------|----------|
| 6.1 | 导航 → 数据分析 → ETL执行 | 页面加载 |
| 6.2 | 选择联赛和赛季 | 下拉菜单正常 |
| 6.3 | 点击"执行ETL" | ETL 开始运行 |
| 6.4 | 观察进度条 | 进度逐步推进 |
| 6.5 | ETL 完成后查看日志 | 显示完成信息和质量报告 |

### 3.7 报表看板

| 步骤 | 操作 | 期望结果 |
|------|------|----------|
| 7.1 | 导航 → 结果输出 → 报表看板 | 页面加载 |
| 7.2 | 选择联赛、分组、玩法、时段 | 筛选器联动正常 |
| 7.3 | 检查决策信号是否显示 | 页面展示 Home/Away 信号列表 |
| 7.4 | 检查五大区间的图表 | 图表渲染正常 |
| 7.5 | 检查护级/强度等级 | 数据展示正常 |

### 3.8 历史记录

| 步骤 | 操作 | 期望结果 |
|------|------|----------|
| 8.1 | 导航 → 结果输出 → 历史纪录 | 页面加载 |
| 8.2 | 查看 ETL 运行历史 | 显示历史运行记录列表 |

### 3.9 数据验证与数据库管理

| 步骤 | 操作 | 期望结果 |
|------|------|----------|
| 9.1 | 导航 → 运维 → 数据验证 | 页面加载 |
| 9.2 | 运行验证 | 显示验证结果/质量报告 |
| 9.3 | 导航 → 运维 → 数据库管理 | 页面加载 |
| 9.4 | 查看数据库状态 | 状态信息显示正常 |

### 3.10 任务列表

| 步骤 | 操作 | 期望结果 |
|------|------|----------|
| 10.1 | 导航 → 运维 → 任务列表 | 页面加载 |
| 10.2 | 查看爬虫/同步任务状态 | 显示任务列表，状态正确 |

---

## 4. ETL 管线验证

### 4.1 管线步骤追踪

ETL 管线执行顺序（与 3.6 同步）：

```
Step 0: 读取 match_records 表
Step 1: 分类（XValueClassifier）
Step 2: 轮次汇总（RoundBlockAggregator）
Step 3: 跨赛季汇总（SeasonAggregator）
Step 4: 五大区间（FiveZoneGrouper）
Step 5: 护级（GuardLevelEvaluator）
Step 6: 强度（StrengthUpgrader）
Step 7: 信号生成（SignalGenerator）
Step 8: 质量检查（QualityChecker）
```

### 4.2 数据流验证

```bash
# ETL 执行后，检查 SQLite 数据库是否写入结果
docker compose exec system_b sqlite3 /app/system_b/db/quant.db ".tables"
# 期望: 看到 computation_results, decision_results, quality_issues 等表

# 检查是否有计算结果
docker compose exec system_b sqlite3 /app/system_b/db/quant.db "SELECT COUNT(*) FROM computation_results;"
# 期望: > 0

# 检查是否有决策结果
docker compose exec system_b sqlite3 /app/system_b/db/quant.db "SELECT COUNT(*) FROM decision_results;"
# 期望: > 0
```

### 4.3 数据一致性验证

```bash
# 检查 System A （PostgreSQL）中比赛数据与 System B 中 match_records 的对应关系
# 验证爬取状态为 completed 的比赛有对应的赔率数据
curl -s http://localhost:8000/api/crawl/stats | python3 -m json.tool
# completed > 0 indicates crawl success
```

---

## 5. 异常场景与边界测试

### 5.1 网络/连接异常

| 测试场景 | 操作 | 期望结果 |
|----------|------|----------|
| System A 未启动时访问 System B | 关闭 System A → 刷新 System B | System B 页面显示连接错误提示，不崩溃 |
| System A 恢复后 System B 自动重连 | 重启 System A → 刷新 System B | 恢复正常 |
| API 超时 | 制造网络延迟 | 请求有超时处理，不挂起整个页面 |

### 5.2 数据异常

| 测试场景 | 操作 | 期望结果 |
|----------|------|----------|
| 空数据库 | 清空数据后访问各页面 | 页面显示空状态而不是崩溃 |
| 无效比分格式 | POST 比分 "abc-def" | 返回 400 错误，说明解析失败 |
| 缺失盘口数据时结算 | 对无盘口的比赛结算 | 返回 error 描述"暂无盘口数据" |
| 超大分页参数 | `page_size=99999` | 被 le=10000 限制 |

### 5.3 并发/重复操作

| 测试场景 | 操作 | 期望结果 |
|----------|------|----------|
| 重复点击 ETL 执行 | ETL 运行时再次点击 | 应有防重复处理或无副作用 |
| 快速切换页面 | 在 ETL 运行时频繁导航 | 不触发异常 |

### 5.4 无效输入

| 测试场景 | 操作 | 期望结果 |
|----------|------|----------|
| 空搜索参数 | 提交不带参数的搜索 | 返回全部结果或提示 |
| 特殊字符 | 搜索包含 HTML/JS 的队名 | 正确转义，无 XSS 风险 |
| 负数 ID | `GET /api/leagues/-1` | 404 或参数验证失败 |

---

## 6. 回归检查清单

### 6.1 代码质量检查

```bash
# ----- Python 语法检查（所有修改过的文件）-----
cd /mnt/d/project/football_system

# system_a
python3 -m py_compile system_a/api/main.py
python3 -m py_compile system_a/api/routes/leagues.py
python3 -m py_compile system_a/api/routes/matches.py
python3 -m py_compile system_a/api/routes/odds.py
python3 -m py_compile system_a/api/routes/crawl.py
python3 -m py_compile system_a/api/routes/x_values.py
python3 -m py_compile system_a/api/routes/settlement.py
python3 -m py_compile system_a/admin/routes.py
python3 -m py_compile system_a/config/settings.py
python3 -m py_compile system_a/config/models.py
python3 -m py_compile system_a/config/database.py
python3 -m py_compile system_a/scraper/odds_crawler.py
python3 -m py_compile system_a/scraper/league_crawler.py
python3 -m py_compile system_a/scraper/handicap_normalizer.py
python3 -m py_compile system_a/scraper/team_normalizer.py
python3 -m py_compile system_a/modules/settlement_calculator.py

# system_b
python3 -m py_compile system_b/app.py
python3 -m py_compile system_b/modules/settlement_calculator.py
python3 -m py_compile system_b/modules/data_connector.py
python3 -m py_compile system_b/modules/x_calculator.py
python3 -m py_compile system_b/core/pipeline.py

echo "✅ All Python files compile clean"
```

### 6.2 测试套件运行

```bash
# ----- System A 测试 -----
cd /mnt/d/project/football_system/system_a && python3 -m pytest tests/ -v --tb=line 2>&1 | tail -30

# ----- System B 测试 -----
cd /mnt/d/project/football_system/system_b && python3 -m pytest tests/ --ignore=tests/tests -v --tb=line 2>&1 | tail -50
```

### 6.3 Docker 构建检查

```bash
# 构建镜像（无缓存）
cd /mnt/d/project/football_system
sudo docker compose build --no-cache 2>&1 | tail -20
# 期望: 构建成功，无错误
```

### 6.4 硬编码路径检查

```bash
# 确保没有残留硬编码路径
grep -rn "/mnt/d/project/" system_a/ system_b/ --include="*.py" || echo "✅ No hardcoded paths found"
# 期望: 输出 "✅ No hardcoded paths found"
```

### 6.5 导入一致性检查

```bash
# 检查 system_b 中是否还有 from etl import （应当使用 from core import）
grep -rn "from etl import" system_b/ --include="*.py" || echo "✅ No stale 'from etl import' found"

# 检查 system_b 中是否有相对导入
grep -rn "from \.core\|from \.modules\|from \.config\|from \.utils" system_b/ --include="*.py" || echo "✅ No relative imports found"
```

### 6.6 重复模块检查

```bash
# 检查 system_b 中是否还有遗留的 HANDICAP_MAP
grep -rn "HANDICAP_MAP" system_b/modules/settlement_calculator.py && echo "⚠️ Duplicate logic still present!" || echo "✅ No duplicate HANDICAP_MAP in system_b settlement_calculator"

# 检查 system_b 中是否还有本地结算计算逻辑
grep -rn "def calculate_hdp_settlement\|def calculate_ou_settlement\|def normalize_handicap" system_b/modules/settlement_calculator.py && echo "⚠️ Duplicate business logic still present!" || echo "✅ No duplicate business logic"
```

### 6.7 API 参数一致性检查

```bash
# 验证 System B 调用 System A API 时使用 params= 而非 json=
grep -n "client\.post.*json=" system_b/modules/settlement_calculator.py && echo "⚠️ Still using json= instead of params=!" || echo "✅ All API calls use params="
```

---

## 7. 交付签字标准

### ✅ 必须全部通过（Critical Path）

| # | 检查项 | 验证方式 | 通过标准 |
|---|--------|----------|----------|
| 1 | System A 启动 | `./status.sh` | 3 个服务都 healthy |
| 2 | API 健康检查 | `curl /health` | 返回 `{"status":"healthy"}` |
| 3 | 核心 CRUD 端点 | 第 2.1 节 | 全部返回 200/404 （合理） |
| 4 | 错误路径测试 | 第 2.2 节 | 返回正确 HTTP 状态码 |
| 5 | Python 编译 | `py_compile` | 所有文件无语法错误 |
| 6 | System A 测试 | `pytest` | 全部通过或已知预期失败 |
| 7 | System B 测试 | `pytest` | 全部通过或已知预期失败 |
| 8 | Docker 构建 | `docker compose build` | 构建成功无错误 |
| 9 | 无硬编码路径 | `grep /mnt/d/` | 无命中 |

### 🔶 强烈建议通过（High Priority）

| # | 检查项 | 验证方式 |
|---|--------|----------|
| 10 | System B 首页加载 | 浏览器浏览 |
| 11 | 页面导航完整 | 所有导航项可点击跳转 |
| 12 | 系统同步操作 | 点击同步按钮，任务下发 |
| 13 | 参数设定页面 | 参数读取与保存 |
| 14 | ETL 执行 | 运行完成，无抛错 |
| 15 | 报表看板渲染 | 图表/信号正常展示 |

### 🔵 可选（Medium）

| # | 检查项 |
|---|--------|
| 16 | 数据导入操作 |
| 17 | 联赛管理操作 |
| 18 | 队伍分组操作 |
| 19 | 历史记录查看 |
| 20 | 管理员界面访问 |

---

## 附录 A：故障排查快速参考

### System A 502 / 无法连接

```bash
# 检查日志
docker compose logs system_a

# 检查数据库连接
docker compose exec system_a python3 -c "
from config.database import engine
engine.connect()
print('✅ DB connected')
"

# 手动启动（调试）
cd system_a && uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### System B 页面报错

```bash
# 检查日志
docker compose logs system_b

# 检查是否连接到 System A
docker compose exec system_b python3 -c "
from modules.data_connector import get_connector
c = get_connector()
print(c.get_leagues())
"
```

### ETL 执行失败

```bash
# 检查 SQLite 数据库
docker compose exec system_b sqlite3 /app/system_b/db/quant.db ".tables"

# 检查 ETL 运行记录
docker compose exec system_b sqlite3 /app/system_b/db/quant.db "SELECT * FROM etl_runs ORDER BY id DESC LIMIT 5;"

# 检查质量报告
docker compose exec system_b sqlite3 /app/system_b/db/quant.db "SELECT * FROM quality_issues ORDER BY id DESC LIMIT 10;"
```

### 数据库重置

```bash
# 完全重启（保留数据）
./stop.sh && ./start.sh

# 完全重置（删除数据）
docker compose down -v && ./start.sh
```

---

## 附录 B：一键验证脚本

将以下内容保存为 `verify.sh`：

```bash
#!/bin/bash
# 交付前验证脚本
set -e

echo "========================================="
echo "🔍 交付前验证脚本"
echo "========================================="

# 1. 环境就绪检查
echo ""
echo "【1/6】环境就绪检查..."
./status.sh

# 2. 语法检查
echo ""
echo "【2/6】Python 语法检查..."
cd system_a
for f in api/main.py api/routes/*.py admin/routes.py config/*.py scraper/*.py modules/*.py; do
    python3 -m py_compile "$f" 2>/dev/null && echo "  ✅ $f" || echo "  ❌ $f"
done
cd ../system_b
for f in app.py core/*.py modules/*.py utils/*.py; do
    python3 -m py_compile "$f" 2>/dev/null && echo "  ✅ $f" || echo "  ❌ $f"
done
cd ..

# 3. API 健康检查
echo ""
echo "【3/6】API 端点检查..."
for endpoint in "/" "/health" "/api/leagues" "/api/matches?page=1&page_size=1" "/api/crawl/stats"; do
    status=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000$endpoint")
    if [ "$status" = "200" ]; then
        echo "  ✅ GET $endpoint → $status"
    else
        echo "  ❌ GET $endpoint → $status"
    fi
done

# 4. 硬编码路径检查
echo ""
echo "【4/6】硬编码路径检查..."
if grep -rn "/mnt/d/project/" system_a/ system_b/ --include="*.py" > /dev/null 2>&1; then
    echo "  ❌ 发现硬编码路径:"
    grep -rn "/mnt/d/project/" system_a/ system_b/ --include="*.py"
else
    echo "  ✅ 无硬编码路径"
fi

# 5. API 参数一致性
echo ""
echo "【5/6】API 参数一致性检查..."
if grep -n "client\.post.*json=" system_b/modules/settlement_calculator.py > /dev/null 2>&1; then
    echo "  ❌ settlement_calculator.py 仍使用 json= 而非 params="
else
    echo "  ✅ settlement_calculator.py API 调用参数正确"
fi

# 6. 重复逻辑检查
echo ""
echo "【6/6】重复逻辑检查..."
if grep -q "HANDICAP_MAP" system_b/modules/settlement_calculator.py 2>/dev/null; then
    echo "  ❌ 仍存在重复 HANDICAP_MAP"
else
    echo "  ✅ 无重复结算逻辑"
fi

echo ""
echo "========================================="
echo "✅ 验证完成"
echo "========================================="
```