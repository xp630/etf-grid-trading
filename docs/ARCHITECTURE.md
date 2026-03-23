# 系统架构设计

> 本文档描述 ETF 网格交易系统的整体设计。开发人员必读。

---

## 1. 系统架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                        系统架构                                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐     多数据源工厂      ┌─────────────────────┐    │
│  │ AkShare      │ ──────────────────▶ │                     │    │
│  │ JoinQuant    │                      │   DataEngine        │    │
│  │ Tushare      │                      │   get_current_price │    │
│  │ Mock         │                      │   get_baseline_price│    │
│  └──────────────┘                      └──────────┬──────────┘    │
│                                                     │              │
│                                                     ▼              │
│  ┌──────────────────────────────────────────────────────────┐    │
│  │                    TrendGridStrategy                     │    │
│  │  ┌────────────┐  ┌────────────┐  ┌─────────────────┐  │    │
│  │  │ 趋势过滤   │  │ AI网格间距  │  │  自动单位计算   │  │    │
│  │  │ MA20判断   │  │ 牛/熊/震荡  │  │ position_ratio  │  │    │
│  │  └────────────┘  └────────────┘  └─────────────────┘  │    │
│  │         │                 │                 │          │    │
│  │         └─────────────────┼─────────────────┘          │    │
│  │                           ▼                              │    │
│  │                  check_signals()                         │    │
│  │                  每次最多 1 个信号                       │    │
│  └───────────────────────────┬──────────────────────────────┘    │
│                              │                                    │
│         ┌────────────────────┼────────────────────┐              │
│         ▼                    ▼                    ▼                │
│  ┌────────────┐      ┌─────────────┐      ┌──────────────┐       │
│  │RiskEngine │      │ExecutionEng. │      │PositionTrack │       │
│  │check_all()│ ───▶ │ place_order │ ────▶│record_buy/   │       │
│  │ 四重风控  │      │  聚宽API    │      │record_sell   │       │
│  └────────────┘      └─────────────┘      └──────┬───────┘       │
│                                                   │               │
│                              ┌────────────────────┼───────┐       │
│                              ▼                    ▼       ▼       │
│                       ┌────────────┐      ┌──────────┐ ┌───────┐  │
│                       │  SQLite    │      │Server酱  │ │ 日志  │  │
│                       │  持仓/交易 │      │微信通知  │ │       │  │
│                       └────────────┘      └──────────┘ └───────┘  │
└─────────────────────────────────────────────────────────────────────┘

Web 层：
  ┌────────────────────┐   ┌──────────────────────┐
  │ Streamlit 监控面板  │   │ Flask API 服务        │
  │ :8501  实时数据    │   │ :5001  交易控制      │
  └────────────────────┘   └──────────────────────┘
```

---

## 2. 核心组件

### 2.1 TrendGridStrategy（主策略）

**文件**：`strategies/trend_grid_live.py`

**三种交易模式**：
```
MODE_FULL_GRID  ─── 震荡市：正常网格，低买高卖
MODE_BUY_ONLY   ─── 下跌趋势：只买不卖，等待反弹
MODE_SELL_ONLY  ─── 上涨趋势：只卖不买，等待回调
```

**趋势判断**（MA20）：
- 上涨：`price > MA20 × (1 + threshold)` → `MODE_SELL_ONLY`
- 下跌：`price < MA20 × (1 - threshold)` → `MODE_BUY_ONLY`
- 震荡：其他情况 → `MODE_FULL_GRID`

**AI 网格间距调整**：
| 市场状态 | 间距 |
|---------|------|
| 牛市 | 6% |
| 熊市 | 4% |
| 震荡 | 5% |
| 高波动 | 3% |

**自动单位计算**：
```
每格单位 = (总资金 × 持仓比例) ÷ (买入档位数 × 当前价格)
→ 向下取整到 100 股
```

**卖出理由优先级**：
1. 止损（3%亏损）
2. 止盈（8%盈利）
3. 移动止损（从最高点回落2%）
4. 网格卖出（价格涨过档位）

---

### 2.2 DataEngine（数据引擎）

**文件**：`engines/data.py`

**职责**：封装多数据源，对上层屏蔽数据获取细节。

**数据源切换**（`config.yaml`）：
```yaml
data_source:
  index: akshare   # 默认 AkShare（免费）
  # index: joinquant  # 聚宽（需要账号）
  # index: tushare    # Tushare（需要 Token）
  # index: mock       # 模拟数据
```

**缓存策略**：价格缓存 10 秒，避免频繁调用 API。

**Mock 模式**：当所有数据源都失败时，使用固定模拟价格（约 3.80 元）。

---

### 2.3 ExecutionEngine（执行引擎）

**文件**：`engines/execution.py`

**订单流程**：
```
place_order(action, price, quantity)
    │
    ├─▶ RiskEngine.check_all()  ──拒绝──▶ 返回错误
    │
    ▼
ExecutionEngine._submit_order()
    │
    ├─▶ jq.paper_order()  ──成功──▶ 返回 order_id
    │
    ├─▶ jq.paper_order()  ──失败（重试3次）──▶ 返回 mock_order_*（模拟）
    │
    ▼
PositionTracker.record_buy/sell()
    │
    ▼
Notifier.send_trade()
```

---

### 2.4 RiskEngine（风控引擎）

**文件**：`engines/risk.py`

**四重风控**：

| 层级 | 检查 | 阈值 | 触发后行为 |
|------|------|------|-----------|
| 1 | 仓位上限 | 持仓 ≤ 5000 元 | 拒绝买入 |
| 2 | 日亏损熔断 | 当日亏损 ≥ 100 元 | 停止交易，等待下一日 |
| 3 | 总资产止损 | 总资产 ≤ 9000 元 | **永久**停止交易 |
| 4 | 买入验证 | new_position ≤ max_position | 拒绝超出部分 |

**注意**：日亏损熔断在每日开盘重置；总资产止损是永久性的，需重启系统。

---

### 2.5 PositionTracker（持仓追踪）

**文件**：`utils/position_tracker.py`

**数据库**：`trading.db`（SQLite）

```sql
positions: symbol TEXT PRIMARY KEY, quantity INTEGER, avg_price REAL,
           level_index INTEGER, buy_date TEXT

trades: id INTEGER PRIMARY KEY, symbol TEXT, action TEXT, price REAL,
        quantity INTEGER, level_index INTEGER, timestamp TEXT, profit REAL
```

**关键逻辑**：
- `record_buy`：加权平均计算持仓均价
- `record_sell`：计算单笔盈利 = `(卖出价 - 均价) × 数量`
- `get_daily_pnl`：当日所有卖出盈利之和（未实现盈亏不计入）

---

### 2.6 Notifier（微信通知）

**文件**：`notification/notifier.py`

**通知类型**：

| 方法 | 触发时机 |
|------|---------|
| `send_trade()` | 成交时推送：档位、价格、数量、盈利 |
| `send_risk_warning()` | 日亏损超限 / 仓位超限 |
| `send_stop_loss()` | 总资产触及止损线（紧急） |
| `send_error()` | 系统异常 |
| `send_daily_summary()` | 每日 14:55 推送：日盈亏、持仓、交易统计 |

---

## 3. 数据流

### 3.1 每日交易流程

```
09:25 ──────────────────────────────────────────────────────────────
       DataEngine.get_baseline_price()
             │
             ▼
       GridCalculator 初始化网格（10档，5%间距）
             │
             ▼
       TrendGridStrategy._get_trend_mode()  ── 确定今日交易模式

09:30 ──────────────────────────────────────────────────────────────
       每 10 秒循环：
       ┌─────────────────────────────────────────────────────────┐
       │  DataEngine.get_current_price()                        │
       │        │                                               │
       │        ▼                                               │
       │  TrendGridStrategy.check_signals()                     │
       │    ├─ MODE_BUY_ONLY  → 只检查买入                      │
       │    ├─ MODE_SELL_ONLY → 只检查卖出                      │
       │    └─ MODE_FULL_GRID → 买入 + 卖出                     │
       │        │                                               │
       │        ▼                                               │
       │  RiskEngine.check_all()  ── 任意一项失败 → 跳过        │
       │        │                                               │
       │        ▼                                               │
       │  ExecutionEngine.place_order()                         │
       │        │                                               │
       │        ▼                                               │
       │  PositionTracker.record_buy/sell()                     │
       │        │                                               │
       │        ▼                                               │
       │  Notifier.send_trade()                                 │
       └─────────────────────────────────────────────────────────┘

14:50 ──────────────────────────────────────────────────────────────
       取消所有未成委托
       Notifier.send_daily_summary()

14:55 ──────────────────────────────────────────────────────────────
       当日交易循环结束，进入休市状态
       每 60 秒检查一次是否开盘
```

### 3.2 信号检查流程（TrendGridStrategy）

```
价格变化 ──▶ 获取当前价格
                 │
                 ▼
         _get_trend_mode()  ──▶ 今日模式（BUY_ONLY/SELL_ONLY/FULL_GRID）
                 │
       ┌────────┴────────┐
       ▼                 ▼
  检查买入           检查卖出
       │                 │
       │  价格 < 档位价   │  价格 > 档位价
       │  AND            │  AND
       │  档位空仓       │  档位有持仓
       │  AND            │  AND
       │  未达止损/止盈  │  未达止损/止盈
       │  AND            │
       │  模式允许买入   │
       └────────┬────────┘
                 ▼
           生成 Signal
           立即 break
           （每次最多1个）
```

---

## 4. Web 服务架构

```
┌─────────────────────────────────────────────────────────────────┐
│                      Web 服务架构                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Streamlit 监控面板（:8501）                                    │
│   ├── 仪表盘：持仓、资金、日盈亏、网格状态                        │
│   ├── 市场分析：指数/个股走势 + AI 解读                          │
│   ├── 回测分析：历史回测 + 策略推荐                              │
│   └── 设置：通知配置、AI模型、数据源切换                          │
│                                                                 │
│   Flask API 服务（:5001）                                       │
│   ├── /api/strategy     GET/PUT  切换策略（grid/trend_grid）     │
│   ├── /api/order/manual POST 手动下单                            │
│   ├── /api/index/*     GET   指数数据（AkShare/Baostock）        │
│   ├── /api/stock/*     GET   个股数据（Baostock）                │
│   ├── /api/config/*    GET/PUT 配置管理                         │
│   ├── /api/shutdown    POST  关闭服务                           │
│   └── 后台运行 trading_loop()  ──▶ TrendGridStrategy.run_once() │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**注意**：`web/app.py`（Flask 监控面板）已废弃，功能迁移到 Streamlit。

---

## 5. 数据源架构

```
                    DataSourceFactory
                          │
         ┌────────────────┼────────────────┐
         ▼                ▼                ▼
  ┌──────────┐    ┌──────────┐    ┌──────────┐
  │ JoinQuant │    │  AkShare  │    │ Tushare  │
  │ DataSource│    │ DataSource│    │ DataSource│
  └────┬─────┘    └────┬─────┘    └────┬─────┘
       │               │               │
       └───────────────┼───────────────┘
                       ▼
              BaseDataSource（ABC）
              get_current_price()
              get_baseline_price()
              is_market_open()
              get_market_status()
              get_historical_prices()
```

**选择策略**（`data_sources/factory.py`）：
- `config.yaml` 指定 `index: akshare` → 使用 AkShare
- `index: joinquant` → 使用聚宽
- `index: tushare` → 使用 Tushare
- 所有数据源失败 → 回退到 Mock 模式（固定模拟价格）

---

## 6. 错误处理

| 场景 | 处理方式 |
|------|---------|
| 下单失败（网络） | 重试 3 次，间隔 2 秒，仍失败跳过并记录 |
| 聚宽认证失败 | 自动切换 Mock 模式，继续运行 |
| 日亏损超限 | 停止交易，等待下一日 |
| 总资产触及止损 | `running = False`，永久停止，发送紧急通知 |
| 14:50 后 | 取消所有未成委托，不再开新仓位 |
| 数据源 API 限流 | AkShare 偶有不稳定，多数据源自动切换 |

---

## 7. 安全机制总结

1. **无杠杆**：不使用融资融券
2. **仓位上限**：任何时候持仓不超过 5000 元
3. **日亏损熔断**：当日亏损达 100 元停止交易
4. **总资产止损**：亏损 10%（9000 元）永久停止
5. **只做模拟盘**：目前仅支持聚宽模拟交易，不支持实盘

---

*文档更新：2026-03-23*
