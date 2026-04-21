# 足球数据系统 A - REST API 接口文档

**版本**: 1.0.0
**更新日期**: 2026-04-12

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

---

## 二、联赛接口

### 2.1 获取联赛列表

**GET** `/api/leagues`

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| country | string | 否 | 国家筛选 |
| enabled | boolean | 否 | 是否启用 |
| limit | int | 否 | 限制数量（默认 100） |
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

**响应示例：**

```json
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
```

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

---

## 四、比赛接口

### 4.1 获取比赛列表

**GET** `/api/matches`

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| league_id | int | 否 | 联赛 ID |
| season | string | 否 | 赛季 |
| crawl_status | string | 否 | 爬取状态 |
| home_team | string | 否 | 主队名称（模糊匹配） |
| away_team | string | 否 | 客队名称（模糊匹配） |
| page | int | 否 | 页码 |
| page_size | int | 否 | 每页数量 |

**响应示例：**

```json
{
  "total": 100,
  "matches": [
    {
      "match_id": 2789381,
      "league_id": 1,
      "league_name": "英超",
      "season": "2024-2025",
      "round_name": "第1轮",
      "match_time": "2024-08-16T20:00:00",
      "home_team": "曼聯",
      "away_team": "富咸",
      "score_ft": "1-0",
      "crawl_status": "completed"
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

---

## 五、赔率接口

### 5.1 获取比赛赔率

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
| limit | int | 否 | 数量限制 |

---

## 六、爬虫任务接口

### 6.1 获取任务列表

**GET** `/api/crawl/jobs`

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| status | string | 否 | 任务状态 |
| limit | int | 否 | 数量限制 |

### 6.2 获取单个任务

**GET** `/api/crawl/jobs/{job_id}`

### 6.3 触发爬虫任务

**POST** `/api/crawl/start`

**请求体：**

```json
{
  "league_id": 1,
  "season_label": "2024-2025"
}
```

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

### 6.4 停止任务

**POST** `/api/crawl/stop/{job_id}`

### 6.5 获取爬虫统计

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

## 七、错误码

| 错误码 | 说明 |
|--------|------|
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |
| 503 | 服务不可用 |

---

## 八、示例请求

### cURL 示例

```bash
# 获取联赛列表
curl -X GET "http://localhost:8000/api/leagues"

# 触发爬虫任务
curl -X POST "http://localhost:8000/api/crawl/start" \
  -H "Content-Type: application/json" \
  -d '{"league_id": 1, "season_label": "2024-2025"}'

# 获取比赛列表
curl -X GET "http://localhost:8000/api/matches?league_id=1&page=1&page_size=50"
```

### Python 示例

```python
import requests

base_url = "http://localhost:8000"

# 获取联赛列表
response = requests.get(f"{base_url}/api/leagues")
leagues = response.json()

# 触发爬虫任务
response = requests.post(
    f"{base_url}/api/crawl/start",
    json={"league_id": 1, "season_label": "2024-2025"}
)
job = response.json()
```