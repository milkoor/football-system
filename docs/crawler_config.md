# 爬虫配置说明

**版本**: 1.2.0
**更新日期**: 2026-05-24

---

## 一、配置方式

### 1.1 通过管理界面配置（推荐）

访问系统 A 管理后台：http://localhost:8000/admin/settings

### 1.2 通过环境变量配置

```bash
# 系统 A 容器环境变量
DATABASE_URL=postgresql://football:password@postgres:5432/football_data
CRAWL_CONCURRENCY=3
REQUEST_DELAY_MIN=1.0
REQUEST_DELAY_MAX=3.0
PROXY_ENABLED=false
LOG_LEVEL=INFO
```

---

## 二、爬虫参数

### 2.1 并发控制（v1.2.0 新增 ThreadPoolExecutor 支持）

| 参数 | 说明 | 默认值 | 建议范围 |
|------|------|--------|----------|
| crawl_concurrency | 同时爬取的网页数 | 3 (可实现10+) | 1-10 |
| request_delay_min | 请求间隔下限（秒） | 1.0 | 1-3 |
| request_delay_max | 请求间隔上限（秒） | 3.0 | 2-5 |

**配置示例：**
```python
# 激进配置（可能被封）
crawl_concurrency = 5
request_delay_min = 0.5
request_delay_max = 1.5

# 保守配置（稳定但慢）
crawl_concurrency = 1
request_delay_min = 3.0
request_delay_max = 5.0
```

### 2.2 批次设置

| 参数 | 说明 | 默认值 |
|------|------|--------|
| batch_size | 每批处理的任务数 | 10 |

---

## 三、代理配置

### 3.1 支持的代理类型

- **SOCKS5**（推荐）
- **HTTP/HTTPS**
- **Oxylabs 实时 API**

### 3.2 SOCKS5 代理配置

```json
{
  "enabled": true,
  "type": "socks5",
  "host": "sg.nexip.cc",
  "port": 3010,
  "username": "your_username",
  "password": "your_password"
}
```

### 3.3 Oxylabs 配置

```json
{
  "enabled": true,
  "type": "oxylabs",
  "endpoint": "https://realtime.oxylabs.io/v1/queries",
  "username": "your_username",
  "password": "your_password"
}
```

### 3.4 代理服务商推荐

| 服务商 | 类型 | 特点 |
|--------|------|------|
| NexIP | SOCKS5 | 性价比高，亚洲节点好 |
| Oxylabs | 住宅代理 | 稳定但价格较高 |
| SmartProxy | 住宅代理 | 平衡之选 |

---

## 四、反爬策略

### 4.1 已内置的策略

1. **随机 User-Agent**
   - 自动轮换常见的浏览器 User-Agent

2. **请求间隔随机化**
   - 每次请求在 [delay_min, delay_max] 区间随机延时

3. **错误重试机制**
   - 自动重试 3 次（429, 500, 502, 503, 504 错误）

4. **代理自动切换**
   - 检测到被封时自动切换代理

### 4.2 最佳实践

1. **新联赛首次爬取**：使用保守配置
   ```python
   crawl_concurrency = 1
   request_delay_min = 3.0
   request_delay_max = 5.0
   ```

2. **日常增量更新**：使用默认配置
   ```python
   crawl_concurrency = 3
   request_delay_min = 1.0
   request_delay_max = 3.0
   ```

3. **大规模回填**：使用激进配置 + 代理
   ```python
   crawl_concurrency = 5
   request_delay_min = 0.5
   request_delay_max = 1.0
   # 必须使用代理
   proxy_enabled = true
   ```

---

## 五、目标网站

### 5.1 网站信息

| 网站 | URL | 用途 |
|------|-----|------|
| 赛程 | https://zq.titan007.com | 获取联赛赛程 |
| 赔率 | https://vip.titan007.com | 获取赔率变动 |

### 5.2 数据更新频率

- **赛程数据**：每场比赛开赛前 30 天开始采集
- **赔率数据**：
  - 早盘（Early）：赛前 24 小时开始更新
  - 即时盘（Live）：比赛中实时更新

---

## 六、监控与告警

### 6.1 关键指标

- 任务成功率（>95% 为正常）
- 错误类型分布
- 爬取速度（场/分钟）

### 6.2 常见错误处理

| 错误类型 | 可能原因 | 处理方式 |
|----------|----------|----------|
| 403 Forbidden | IP 被封 | 启用代理或降低并发 |
| 404 Not Found | 比赛 ID 不存在 | 忽略，标记为 nodata |
| Timeout | 网络问题 | 自动重试 |
| 500 Server Error | 目标网站问题 | 降低频率，等待恢复 |

---

## 七、性能调优

### 7.1 瓶颈分析

使用管理后台的"数据质量"页面监控：
- 爬取速度
- 失败率
- 各联赛完成度

### 7.2 优化建议

1. **网络优化**
   - 使用香港/新加坡代理
   - 避开高峰时段（晚上 8-11 点）

2. **并发优化**
   - 不要超过 5 个并发
   - 观察目标网站响应时间调整

3. **存储优化**
   - 定期清理超过 2 年的历史数据
   - 对大表进行分区（可选）