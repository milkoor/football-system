# 代码审查报告 — 2026-05-11

> **v1.2.0 更新说明**: 本报告所列问题已于 2026-05-24 版本处理：`ConfigStore.get_global_group()` 公共方法已添加（问题2）、验证增强（问题3）、Excel 导出加载状态（问题4）均已完成。详见 CHANGELOG。

## 审查范围

本次审查覆盖 `system_b` 与 `mftitan` 参考仓库的代码对比，以及最近一次提交中对 `dashboard.py`、`settings.py`、`default_params.json`、`views/dashboard.py` 的改动。

## 总体审查结论

| 审查维度 | 结论 | 置信度 |
|----------|------|--------|
| 目标完整性 | ✅ 通过 | 高 |
| 约束合规性 | ✅ 通过 | 高 |
| 代码质量 | ⚠️ 有条件通过 | 高 |
| 安全性 | ✅ 通过 | 高 |
| 上下文覆盖 | ✅ 通过 | 高 |
| **综合** | **✅ 通过** | **高** |

---

## 1. 目标完整性

### 1.1 用户6点要求逐项核对

| # | 要求 | 状态 | 证据 |
|---|------|------|------|
| 1 | 数据源接入调用系统A | ✅ 原本如此 | `modules/data_connector.py` 通过 httpx 调用 System A REST API，无需改动 |
| 2 | 页面层与 mftitan 保持一致 | ✅ 完成 | `dashboard.py` 和 `settings.py` 已从 mftitan 移植，其余页面无逻辑退化 |
| 3 | 双系统 Docker + 自动同步 | ✅ 原本如此 | `app.py` 保留 APScheduler 调度器、IS_DOCKER 环境检查、views/ 包装层 |
| 4 | settings 参数与 mftitan 一致 | ✅ 完成 | `settings.py` 重写为使用 `config_store.set_param()` 存储，含完整验证和"恢复默认"按钮 |
| 5 | X值计算在系统B | ✅ 原本如此 | `modules/x_calculator.py` 在系统B中，从System A原始赔率数据计算X值 |
| 6 | dashboard 使用真实数据 | ✅ 完成 | 从 mftitan 移植，读取 `decision_results` 表，支持 ETL 版本切换、筛选、导出 |

### 1.2 核心模块一致性验证

所有核心数据处理模块与 mftitan **100% 相同**：

| 模块 | 状态 | 行数 |
|------|------|------|
| `core/classifier.py` | ✅ 完全一致 | 73 |
| `core/five_zone.py` | ✅ 完全一致 | 58 |
| `core/guard.py` | ✅ 完全一致 | 62 |
| `core/strength.py` | ✅ 完全一致 | 47 |
| `core/signal.py` | ✅ 完全一致 | 80 |
| `core/splitter.py` | ✅ 完全一致 | 82 |
| `core/round_aggregator.py` | ✅ 完全一致 | 122 |
| `core/season_aggregator.py` | ✅ 完全一致 | 44 |
| `core/matcher.py` | ✅ 完全一致 | — |
| `core/models.py` | ✅ 完全一致 | — |
| `core/quality.py` | ✅ 完全一致 | — |
| `core/mismatch_detector.py` | ✅ 完全一致 | — |
| `core/preprocessor.py` | ✅ 完全一致 | — |
| `core/settlement.py` | ✅ 完全一致 | — |
| `core/legacy_report.py` | ✅ 完全一致 | — |
| `core/pipeline.py` | ✅ 完全一致 | 451 |
| `utils/excel_io.py` | ✅ 完全一致 | — |
| `utils/migration.py` | ✅ 完全一致 | — |
| `utils/default_params.py` | ✅ 完全一致 | — |

---

## 2. 约束合规性

### 2.1 非功能性约束

| 约束 | 状态 | 说明 |
|------|------|------|
| 核心处理逻辑与 mftitan 完全一致 | ✅ | 19个核心模块全部 diff 为空 |
| app.py 保留 Docker 同步 | ✅ | auto_sync、data_connector、follow_list 保持完整 |
| views/ 包装层保留 | ✅ | 14个 views/*.py 包装器保持不变 |
| `get_store()` 单例工厂保留 | ✅ | `config_store.py` 底部1422-1437行保持不变 |
| 不破坏双系统架构 | ✅ | Docker compose、System A API 路由、crawl routes 全部不变 |

### 2.2 发现的问题

#### 问题1：`dashboard.py` 的 `render()` 是空函数 (WARN)

```python
def render():
    pass
```

**文件**: `system_b/original_pages/dashboard.py:390-391`

**说明**: dashboard.py 采用 mftitan 风格的模块级执行模式（所有 `st.*` 在 import 时执行），`render()` 只是一个空函数供 `views/dashboard.py` 调用。这在 Streamlit 中工作正常，因为：
- `from original_pages.dashboard import render` 会触发模块级代码执行
- 所有 `st.title()`、`st.selectbox()` 等在 import 时已经注册到 Streamlit
- `render()` 只是语法上的入口点

**建议**: 不是 bug，但容易误导。后续可以考虑将全部逻辑移入 `render()` 函数，与 `settings.py` 风格统一。

---

## 3. 代码质量

### 3.1 优点

| 类别 | 说明 |
|------|------|
| 架构一致性 | dashboard.py 完全沿用了 mftitan 的架构和逻辑，与参考仓库保持同步 |
| 参数验证完整 | settings.py 有完整的边界验证（升序检查、mapping 覆盖检查、类型检查） |
| 错误处理恰当 | 使用 `try/except json.JSONDecodeError` 捕获 JSON 解析错误 |
| 空安全 | 多处使用 `get()` 和 `if x in range` 检查避免 IndexError |
| 性能 | `_group_cache` 字典缓存、`zone_labels` 常量，避免重复查询 |

### 3.2 发现的问题

#### 问题2：`_get_group_info()` 访问私有成员 `_conn` (MINOR)

```python
def _get_group_info(group_id: int) -> tuple[str, str]:
    row = store._conn.execute(
        "SELECT name, display_name FROM global_groups WHERE id = ?", (group_id,)
    ).fetchone()
```

**文件**: `system_b/original_pages/dashboard.py:79-81`

**说明**: 直接访问 `store._conn`（命名约定为私有成员）。mftitan 原始代码也这样做，因为 `ConfigStore` 没有暴露按 ID 查询 global group 的公共方法。

**建议**: 在 `ConfigStore` 中添加 `get_global_group(id)` 公共方法，替代直接访问私有成员。

```python
def get_global_group(self, group_id: int) -> GlobalGroup | None:
    row = self._conn.execute(
        "SELECT id, name, display_name, display_order FROM global_groups WHERE id = ?", (group_id,)
    ).fetchone()
    if row:
        return GlobalGroup(id=row["id"], name=row["name"], display_name=row["display_name"])
    return None
```

#### 问题3：`settings.py` 缺少部分参数类型的验证 (MINOR)

**文件**: `system_b/original_pages/settings.py`

**说明**: `_validate_param()` 覆盖了 `x_value_boundaries`、`five_zone_mapping`、数值类参数和 `settlement_values`。但对 `five_zone_mapping` 缺少对 `zone_id` 值域范围（1-9）的验证——如果用户错误传入 `[10]` 会通过验证但后续处理时越界。

#### 问题4：Excel 导出按钮缺少加载状态反馈 (MINOR)

**文件**: `system_b/original_pages/dashboard.py:245-277`

**说明**: 点击"匯出 Excel"按钮后直接生成数据，没有 loading 状态。在大量联赛数据时可能让用户感觉无响应。

---

## 4. 安全性

| 类别 | 结论 |
|------|------|
| SQL 注入 | ✅ 安全 — 所有查询使用参数化查询（`?` 占位符） |
| XSS | ✅ 安全 — Streamlit 自动转义输出 |
| 路径遍历 | ✅ 安全 — 模板路径使用硬编码的相对路径 |
| 文件包含 | ✅ 安全 — 文件读取使用 `_os.path.exists()` 检查后再打开 |
| 序列化 | ✅ 安全 — JSON 解析仅在可控的配置数据上操作 |
| 凭据泄露 | ✅ 无硬编码凭据 |

**无安全相关问题。**

---

## 5. 上下文覆盖

### 5.1 Git 历史分析

最近5次提交记录表明持续在进行重构和功能对齐：
- `f1aad6a` — docs:更新CLAUDE.md
- `356510a` — refactor:整合core/模块
- `108b2d5` — docs: add CLAUDE.md
- `642abf7` — fix: 修复UI文案一致性
- `71eaefd` — feat: 前端参数设定页添加自动同步设置界面

### 5.2 跨系统影响

| 影响范围 | 分析 |
|----------|------|
| System A | 无影响 — 未修改 System A 代码 |
| DB Schema | 无影响 — `default_params.json` 添加 `settlement_values` 字段不会影响已有数据 |
| ETL Pipeline | 无影响 — pipeline 不读取 `settlement_values` 参数，结算值由 `settlement.py` 硬编码计算 |
| 已有页面 | 无影响 — 其他 12 个页面保持不变 |

---

## 6. 建议改进 (非阻塞)

### 优先级：高

1. **在 `ConfigStore` 中添加公共 `get_global_group()` 方法**（见问题2）
   - 消除对 `_conn` 私有成员的直接访问
   - 约 15 行代码

### 优先级：中

2. **增强 `_validate_five_zone_mapping()` 的 zone_id 值域验证**
   ```python
   def _validate_five_zone_mapping(mapping, num_zones=9):
       # 现有逻辑...
       expected = list(range(1, num_zones + 1))
       for zid in all_ids:
           if zid < 1 or zid > num_zones:
               return f"zone_id 必須在 1~{num_zones} 範圍內，發現：{zid}"
   ```

3. **为 Excel 导出按钮添加 `st.spinner`**
   ```python
   if st.button("📥 匯出 Excel"):
       with st.spinner("正在生成報表..."):
           # 现有导出逻辑
   ```

### 优先级：低

4. **统一 `settings.py` 和 `dashboard.py` 的入口模式**
   - 目前 `settings.py` 使用 `def render()` 包装全部逻辑
   - `dashboard.py` 使用模块级执行 + `def render(): pass`
   - 建议统一为 `render()` 函数包装，更清晰

---

## 7. 与 mftitan 的偏离记录

以下差异是 **有意为之** 且 **合理的**：

| 差异项 | system_b | mftitan | 理由 |
|--------|----------|---------|------|
| 数据源 | System A REST API (data_connector) | RPA Excel文件 | 架构要求 |
| 页面加载 | views/ 包装层 + try/except | 直接 st.Page() | 错误隔离 |
| 自动同步 | APScheduler | 无 | Docker部署要求 |
| X值计算 | modules/x_calculator.py | 无（外部计算） | 用户要求X值在系统B |
| 结算计算 | modules/settlement_calculator.py (API包装) | core/settlement.py | 双系统架构 |
| config_store | get_store() 单例工厂 | 每次创建新实例 | 防止SQLite多连接 |
| team_grouping | 添加队名不一致检测+修复 | 无此功能 | 增强UX |
| settings UI | 参数验证+恢复默认+JSON编辑 | 相同功能 | 保持一致 |
| 导航 | st.navigation() 分组导航 | 无分组 | 更好的UX |
| dashboard | 真实数据 + ETL版本切换 | 真实数据 + ETL版本切换 | **已修复** |

---

## 8. 附录

### 8.1 文件变更统计

| 文件 | 操作 | 行数（旧→新） |
|------|------|---------------|
| `original_pages/dashboard.py` | 重写 | 100 → 395 |
| `original_pages/settings.py` | 重写 | 201 → 165 |
| `config/default_params.json` | 修改 | 12 → 13 |
| `views/dashboard.py` | 修改 | 18 → 14 |

### 8.2 审查方法

- 手动代码审查
- `diff` 对比 system_b 与 mftitan 对应文件
- Playwright 浏览器验证（dashboard 和 settings 页面在实际浏览器中渲染并交互）
- `py_compile` 语法检查
- Docker 容器内运行导入验证