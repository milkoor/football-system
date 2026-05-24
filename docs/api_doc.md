# 足球数据系统 A - REST API 接口文档

**版本**: 1.2.0
**更新日期**: 2026-05-24

---

## 一、基础信息

### 1.1 基础 URL

```
http://<server>:8000
```

### 1.2 响应格式

所有 API 返回 JSON 格式，结构如下：

```json
{
  "status": "success",
  "data": { ... },
  "message": "操作成功"
}
```

错误响应：

```json
{
  "status": "error",
  "detail": "错误详情"
}
```

### 1.3 通用参数

| 参数 | 类型 | 说明 |
|------|------|------|
| page | int | 页码（默认 1） |
| page_size | int | 每页数量（默认 50） |

### 1.4 健康检查

**GET** `/health`

**响应示例：**

```json
{
  "status": "healthy"
}
```

---

## 二、联赛接口

### 2.1 获取联赛列表

**GET** `/api/leagues`

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| country | string | 否 | 国家筛选 |
| enabled | boolean | 否 | 是否启用 |
| limit | int | 否 | 限制数量（默认 10000） |
| offset | int | 否 | 偏移量（默认 0） |

**响应示例：**

```json
[
  {
    "id": 1,
    "country": "英格兰",
    "league_id": 36,
    "league_name_zh": "英超",
    "league_name_tw": "英超",
    "display_order": 0,
    "enabled": true,
    "created_at": "2026-04-12T10:00:00",
    "updated_at": "2026-04-12T10:00:00"
  }
]
```

### 2.2 获取单个联赛

**GET** `/api/leagues/{league_id}`

**路径参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| league_id | int | 联赛 ID |

### 2.3 创建联赛

**POST** `/api/leagues`

**请求体：**

```json
{
  "country": "英格兰",
  "league_id": 36,
  "league_name_zh": "英超",
  "league_name_tw": "英超",
  "display_order": 0,
  "enabled": true
}
```

### 2.4 更新联赛

**PUT** `/api/leagues/{league_id}`

### 2.5 删除联赛

**DELETE** `/api/leagues/{league_id}`

### 2.6 从网站同步联赛列表

**POST** `/api/leagues/sync-from-site`

从 titan007 网站同步最新的联赛列表（后台任务）。

**响应示例：**

```json
{
  "message": "联赛同步任务已启动",
  "status": "started",
  "job_id": "uuid-string"
}
```

### 2.7 同步指定联赛赛季赛程

**POST** `/api/leagues/{league_id}/sync-seasons`

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| season_label | string | 否 | 指定赛季标签（如 "2025-2026"），不填则同步全部 |

**响应示例：**

```json
{
  "message": "联赛 1 赛季同步任务已启动",
  "status": "started",
  "job_id": "uuid-string"
}
```

### 2.8 批量同步所有联赛赛季赛程

**POST** `/api/leagues/batch-sync-seasons`

单后台任务批量同步全部联赛的赛季赛程数据（约 14 秒完成 10,950+ 条）。

**响应示例：**

```json
{
  "message": "全联赛批量同步任务已启动",
  "status": "started",
  "job_id": "uuid-string"
}
```

### 2.9 清除所有同步数据

**POST** `/api/leagues/clear-all`

清除所有通过同步导入的数据（比赛、赔率、X 值等）。

**响应示例：**

```json
{
  "message": "所有同步数据已清除"
}
```

---

## 三、赛季接口

### 3.1 获取赛季列表

**GET** `/api/seasons/{league_id}`

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| status | string | 否 | 状态筛选（active/completed） |

**响应示例：**

```json
[
  {
    "id": 1,
    "league_id": 1,
    "season_label": "2024-2025",
    "season_start": "2024-08-01",
    "season_end": "2025-05-31",
    "status": "active"
  }
]
```

### 3.2 创建赛季

**POST** `/api/seasons`

**请求体：**

```json
{
  "league_id": 1,
  "season_label": "2025-2026",
  "season_start": "2025-08-01",
  "season_end": "2026-05-31",
  "status": "active"
}
```

### 3.3 获取赛季维度统计

**GET** `/api/season-stats`

获取所有联赛的总赛季数和已同步赛季数。

**响应示例：**

```json
{
  "total_seasons": 2180,
  "synced_seasons": 1950
}
```

---

## 四、比赛接口

### 4.1 获取比赛列表

**GET** `/api/matches`

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| league_id | int | 否 | 联赛 ID |
| season | string | 否 | 赛季 |
| crawl_status | string | 否 | 爬取状态（pending/completed/nodata/error） |
| home_team | string | 否 | 主队名称（模糊匹配） |
| away_team | string | 否 | 客队名称（模糊匹配） |
| page | int | 否 | 页码（默认 1） |
| page_size | int | 否 | 每页数量（默认 50） |

**响应示例：**

```json
{
  "total": 100,
  "matches": [
    {
      "match_id": 2789381,
      "league_id": 1,
      "league_name": "英超",
      "group_name": null,
      "round_name": "第1轮",
      "season": "2024-2025",
      "match_time": "2024-08-16T20:00:00",
      "home_team": "曼聯",
      "away_team": "富咸",
      "score_ft": "1-0",
      "score_ht": null,
      "settlement": null,
      "settlement_value": null,
      "settlement_direction": null,
      "home_away_direction": null,
      "target_team": null,
      "crawl_status": "completed",
      "retry_count": 0
    }
  ]
}
```

### 4.2 获取单个比赛

**GET** `/api/matches/{match_id}`

### 4.3 批量创建比赛

**POST** `/api/matches/batch`

**请求体：**

```json
[
  {
    "match_id": 2789381,
    "league_id": 1,
    "league_name": "英超",
    "home_team": "曼聯",
    "away_team": "富咸"
  }
]
```

**响应示例：**

```json
{
  "message": "已处理 50 条记录",
  "created": 50
}
```

### 4.4 更新比赛结算信息

**PATCH** `/api/matches/{match_id}/settlement`

手动更新比赛的结算字段。

**请求体：**

```json
{
  "score_ft": "2-1",
  "settlement": "赢",
  "settlement_value": 0.5,
  "settlement_direction": "上",
  "home_away_direction": "home",
  "target_team": "曼聯"
}
```

---

## 五、赔率接口

### 5.1 获取比赛赔率变动

**GET** `/api/matches/{match_id}/odds`

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| odds_type | string | 否 | 赔率类型（AH/OU/1x2） |
| status | string | 否 | 状态（早/即/走） |

**响应示例：**

```json
{
  "total": 50,
  "movements": [
    {
      "movement_id": 1,
      "match_id": 2789381,
      "odds_type": "AH",
      "is_half_time": false,
      "elapsed_time": "",
      "score_at_time": null,
      "update_time": "2024-08-16T18:00:00",
      "status": "早",
      "home_rate": 0.85,
      "handicap_raw": "半球",
      "handicap_std": 0.5,
      "away_rate": 0.97
    }
  ]
}
```

### 5.2 获取最新赔率

**GET** `/api/odds/latest`

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| odds_type | string | 是 | 赔率类型 |
| limit | int | 否 | 数量限制（默认 50） |

**响应示例：**

```json
[
  { "movement_id": 1, "match_id": 2789381, ... }
]
```

---

## 六、结算接口

### 6.1 自动结算单场比赛

**POST** `/api/matches/{match_id}/auto-settle`

根据比赛比分和盘口数据自动计算结算结果。

**响应示例：**

```json
{
  "match_id": 2789381,
  "home_team": "曼聯",
  "away_team": "富咸",
  "score": "2-1",
  "handicap": "0.5",
  "settlement": "赢",
  "settlement_value": 0.5,
  "settlement_direction": "上",
  "home_away_direction": "home",
  "target_team": "曼聯",
  "error": null
}
```

### 6.2 批量自动结算

**POST** `/api/matches/auto-settle`

批量结算指定联赛赛季的所有比赛。

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| league_id | int | 否 | 联赛 ID（不填则结算全部） |
| season | string | 否 | 赛季标签（不填则结算全部） |

**响应示例：**

```json
{
  "total": 380,
  "success": 376,
  "failed": 4,
  "results": [
    { "match_id": 2789381, "settlement": "赢", "settlement_value": 0.5 }
  ]
}
```

### 6.3 获取比赛结算结果

**GET** `/api/matches/{match_id}/settlement`

### 6.4 更新比分并自动结算

**POST** `/api/matches/{match_id}/score`

更新比赛比分后自动触发结算计算。

**请求体：**

```json
{
  "score_ft": "2-1",
  "score_ht": "1-0"
}
```

**响应示例：**

```json
{
  "message": "比分已更新并自动结算",
  "match_id": 2789381,
  "score": "2-1",
  "settlement": "赢"
}
```

---

## 七、爬虫任务接口

### 7.1 获取任务列表

**GET** `/api/crawl/jobs`

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| status | string | 否 | 任务状态（pending/running/completed/failed） |
| limit | int | 否 | 数量限制（默认 20） |

**响应示例：**

```json
[
  {
    "id": 1,
    "job_id": "abc123",
    "job_type": "crawl_odds",
    "league_id": 1,
    "season_label": "2024-2025",
    "match_ids": null,
    "status": "completed",
    "total_matches": 380,
    "completed_matches": 380,
    "failed_matches": 0,
    "started_at": "2026-05-24T10:00:00",
    "completed_at": "2026-05-24T10:05:00",
    "error_message": null
  }
]
```

### 7.2 获取单个任务

**GET** `/api/crawl/jobs/{job_id}`

`job_id` 支持数据库 ID（int）或任务 UUID（string）。

### 7.3 触发爬虫任务

**POST** `/api/crawl/start`

**请求体：**

```json
{
  "league_id": 1,
  "season_label": "2024-2025",
  "match_ids": null
}
```

`match_ids` 可选，指定后只爬取指定比赛而非全部赛季比赛。

**响应示例：**

```json
{
  "id": 1,
  "job_id": "abc123",
  "league_id": 1,
  "season_label": "2024-2025",
  "status": "pending",
  "total_matches": 380,
  "completed_matches": 0,
  "failed_matches": 0
}
```

### 7.4 停止任务

**POST** `/api/crawl/stop/{job_id}`

停止正在运行中的爬虫任务。

```json
{
  "message": "任务已停止"
}
```

### 7.5 获取爬虫统计

**GET** `/api/crawl/stats`

**响应示例：**

```json
{
  "total_matches": 5000,
  "pending": 1000,
  "completed": 3800,
  "error": 200,
  "active_jobs": 2
}
```

---

## 八、X 值接口

### 8.1 获取 X 值列表

**GET** `/api/x-values`

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| match_id | int | 否 | 比赛 ID |
| status | string | 否 | 状态（success/not_suitable/no_data/error） |
| limit | int | 否 | 数量限制（默认 100） |

**响应示例：**

```json
[
  {
    "id": 1,
    "match_id": 2789381,
    "home_team": "曼聯",
    "away_team": "富咸",
    "score": "1-0",
    "target_team": "主队",
    "has_star_mark": true,
    "x_value": 0.35,
    "status": "success",
    "calculation_note": null,
    "movement_url": "https://vip.titan007.com/changeDetail/handicap.aspx?id=2789381",
    "created_at": "2026-04-12T10:00:00"
  }
]
```

### 8.2 获取单场比赛 X 值

**GET** `/api/x-values/{match_id}`

### 8.3 保存 X 值计算结果

**POST** `/api/x-values`

**请求体：**

```json
{
  "match_id": 2789381,
  "home_team": "曼聯",
  "away_team": "富咸",
  "score": "1-0",
  "target_team": "主队",
  "has_star_mark": true,
  "x_value": 0.35,
  "status": "success",
  "calculation_note": null,
  "movement_url": "https://vip.titan007.com/changeDetail/handicap.aspx?id=2789381"
}
```

---

## 九、错误码

| HTTP 状态码 | 说明 |
|-------------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |
| 503 | 服务不可用 |

---

## 十、示例请求

### cURL 示例

```bash
# 健康检查
curl -X GET "http://localhost:8000/health"

# 获取联赛列表
curl -X GET "http://localhost:8000/api/leagues"

# 获取比赛列表
curl -X GET "http://localhost:8000/api/matches?league_id=1&page=1&page_size=50"

# 获取比赛赔率
curl -X GET "http://localhost:8000/api/matches/2789381/odds"

# 触发爬虫任务
curl -X POST "http://localhost:8000/api/crawl/start" \
  -H "Content-Type: application/json" \
  -d '{"league_id": 1, "season_label": "2024-2025"}'

# 批量同步所有赛季
curl -X POST "http://localhost:8000/api/leagues/batch-sync-seasons"

# 批量自动结算
curl -X POST "http://localhost:8000/api/matches/auto-settle?league_id=1&season=2025-2026"

# 获取赛季统计
curl -X GET "http://localhost:8000/api/season-stats"

# 获取爬虫统计
curl -X GET "http://localhost:8000/api/crawl/stats"
```

### Python 示例

```python
import requests

base_url = "http://localhost:8000"

# 健康检查
response = requests.get(f"{base_url}/health")
print(response.json())

# 获取联赛列表
response = requests.get(f"{base_url}/api/leagues")
leagues = response.json()

# 触发爬虫任务
response = requests.post(
    f"{base_url}/api/crawl/start",
    json={"league_id": 1, "season_label": "2024-2025"}
)
job = response.json()

# 批量结算
response = requests.post(
    f"{base_url}/api/matches/auto-settle",
    params={"league_id": 1, "season": "2025-2026"}
)
result = response.json()
```