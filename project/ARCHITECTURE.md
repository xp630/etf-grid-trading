# ETF网格交易系统 - 架构设计

## 系统架构图

```
┌─────────────────────────────────────────────────────────┐
│                    系统架构                               │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────┐   ┌──────────┐   ┌──────────────┐      │
│  │ 行情数据  │ → │ 网格策略  │ → │  模拟/实盘   │      │
│  │ (聚宽API) │   │ (低买高卖)│   │  执行层     │      │
│  └──────────┘   └──────────┘   └──────────────┘      │
│       ↑              ↑              ↓                   │
│       ↓              ↓              ↓                   │
│  ┌──────────┐   ┌──────────┐   ┌──────────────┐      │
│  │ 数据存储  │   │ 风控引擎  │   │  持仓/资金   │      │
│  │ (历史K线) │   │ (绝不亏光)│   │  (实时跟踪)  │      │
│  └──────────┘   └──────────┘   └──────────────┘      │
│                                                         │
│  ┌──────────────────────────────────────────┐          │
│  │          Web监控面板 + 微信通知           │          │
│  └──────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────┘
```

## 核心模块

### 1. utils/grid_calculator.py - 网格计算器

**职责**: 根据基准价和网格参数计算各档位价格

**主要类**: `GridCalculator`

| 方法 | 说明 |
|------|------|
| `get_levels()` | 获取所有档位价格列表 |
| `get_level_index(price)` | 获取价格所属档位索引 |
| `get_price_at_level(idx)` | 获取指定档位价格 |

**网格计算逻辑**:
- 基准价在中间位置
- `levels=10, spacing=5%` 时，共11档（5档向下 + 基准 + 5档向上）
- 档位0 = 最低价，档位10 = 最高价

### 2. utils/position_tracker.py - 持仓追踪器

**职责**: 管理持仓和交易记录（SQLite持久化）

**主要类**: `Position`, `PositionTracker`

| 方法 | 说明 |
|------|------|
| `record_buy()` | 记录买入 |
| `record_sell()` | 记录卖出（含盈利计算） |
| `get_all_positions()` | 获取所有持仓 |
| `get_total_value(price)` | 计算持仓总市值 |
| `get_daily_pnl()` | 计算当日盈亏 |
| `is_level_holding(idx)` | 检查档位是否有持仓 |
| `get_trades()` | 获取交易记录 |

**数据库表**:
- `positions`: symbol, quantity, avg_price, level_index, buy_date
- `trades`: symbol, action, price, quantity, level_index, timestamp, profit

### 3. engines/risk.py - 风控引擎

**职责**: 下单前的风控检查

**主要方法**:

| 方法 | 检查内容 |
|------|----------|
| `check_order()` | 仓位是否超限（仅买入检查） |
| `check_daily_loss()` | 日亏损是否超限 |
| `check_total_assets()` | 总资产是否触及止损线 |
| `check_all()` | 执行所有检查 |
| `get_status()` | 获取风控状态摘要 |

**风控规则**:
- 买入时检查：当前持仓 + 订单金额 <= 5000元
- 日亏损 < -100元时拒绝新买入
- 总资产 < 9000元时永久停止交易

### 4. engines/data.py - 数据引擎

**职责**: 从多数据源获取行情数据

**数据源支持**:
- 聚宽（优先，需要账号）
- AkShare（免费，偶有不稳定）
- Baostock（免费，稳定）
- Mock（仅测试用）

**主要方法**:

| 方法 | 说明 |
|------|------|
| `get_current_price()` | 获取当前价格（含重试机制） |
| `get_baseline_price()` | 获取基准价（前一日收盘） |
| `get_price_with_cache()` | 带缓存的价格获取 |
| `is_market_open()` | 检查是否在交易时间 |
| `get_market_status()` | 获取市场状态 |

**重试机制**: 默认3次重试，间隔2秒

**数据源配置**: 通过 `config.yaml` 中的 `data_source.index` 设置，可选值：`auto`（自动）/ `joinquant` / `akshare` / `baostock` / `mock`

### 5. engines/execution.py - 执行引擎

**职责**: 订单管理和执行

**主要方法**:

| 方法 | 说明 |
|------|------|
| `place_order()` | 下单（含风控检查） |
| `cancel_order()` | 取消订单 |
| `get_order_status()` | 查询订单状态 |

**订单流程**:
1. 风控检查
2. 提交订单到聚宽
3. 成交后记录持仓

### 6. strategies/grid.py - 网格策略

**职责**: 核心交易策略逻辑

**主要方法**:

| 方法 | 说明 |
|------|------|
| `_init_grid()` | 初始化网格 |
| `check_signals()` | 检查买卖信号 |
| `execute_signals()` | 执行信号 |
| `run_once()` | 运行一次策略 |
| `get_status()` | 获取策略状态 |

**信号逻辑**:
- 买入: `price < 基准价 && price < level_price && 档位空仓`
- 卖出: `price > level_price && 档位有持仓`
- 每次最多处理1个信号

### 7. notification/notifier.py - 通知器

**职责**: 通过Server酱发送微信通知

**通知类型**:

| 方法 | 触发条件 |
|------|----------|
| `send_trade()` | 成交时 |
| `send_risk_warning()` | 日亏损/仓位超限时 |
| `send_stop_loss()` | 触及总止损线时 |
| `send_error()` | 系统异常时 |
| `send_daily_summary()` | 每日总结 |

### 8. web/streamlit_app.py - Web监控面板

**功能**: Streamlit单页应用，集成监控面板、市场分析、回测分析

**主要区域**:
- 📊 监控面板：持仓、资金、昨日收益、网格状态
- 📊 市场分析：预设指数 + 手动输入股票，支持个股走势分析和AI解读
- 📈 回测分析：历史回测 + AI策略推荐
- ⚙️ 设置：微信通知、AI模型、数据源配置

**市场分析功能**:
- 预设指数：上证指数、深证成指、创业板指、科创50、沪深300、上证50、中证500
- 手动输入：支持任意A股股票代码（使用Baostock数据）
- 走势分析：区间涨跌、近5日涨跌、年化波动率、均线多空判断
- 网格建议：自动判断是否适合做网格
- AI解读：点击按钮调用大模型，用通俗语言解释数据并给出建议

**数据源切换**: 设置页面可选择指数数据来源（自动/聚宽/AkShare/Baostock/模拟）

### 9. backtest/runner.py - 回测运行器

**主要方法**:

| 方法 | 说明 |
|------|------|
| `run(price_data, dates)` | 运行回测 |
| `_calculate_stats()` | 计算统计指标 |

**输出指标**:
- 总收益率
- 最大回撤
- 胜率
- 总交易次数
- 日盈亏曲线

### 10. utils/llm_service.py - AI服务

**职责**: 调用大语言模型分析个股走势，给出网格交易建议

**支持的提供商**: MiniMax / OpenAI / DeepSeek

**主要方法**:

| 方法 | 说明 |
|------|------|
| `analyze_market()` | 同步分析市场（不含账户信息） |
| `analyze_market_stream()` | 流式分析（用于Streamlit） |
| `recommend_strategy()` | 基于大盘分析推荐策略 |
| `_build_market_prompt()` | 构建大盘分析提示词 |
| `_build_strategy_prompt()` | 构建策略推荐提示词 |
| `_parse_market_analysis()` | 解析AI返回结果 |

**AI解读功能**（市场分析页面）:
- 用户输入股票代码，获取历史数据
- 系统自动计算涨跌、波动率、均线多空
- AI根据数据判断是否适合做网格，给出策略建议

## 数据流

```
1. 每日09:25
   DataEngine.get_baseline_price() → GridCalculator初始化

2. 交易时间内（每10秒）
   DataEngine.get_current_price()
         ↓
   GridStrategy.check_signals()
         ↓
   RiskEngine.check_all() → ExecutionEngine.place_order()
         ↓
   PositionTracker.record_buy/sell()
         ↓
   Notifier.send_trade()

3. 14:50后
   取消所有未成委托
```

## 配置文件

所有配置集中在 `config.yaml`:

```yaml
grid:          # 网格参数
risk:          # 风控参数
broker:        # 券商设置
market:        # 市场设置
notification:  # 通知设置
database:      # 数据库设置
```

## 错误处理

| 场景 | 处理方式 |
|------|----------|
| 下单失败 | 重试3次，失败记录错误并跳过 |
| 网络断线 | 自动重连，重连后检查持仓一致性 |
| 部分成交 | 按实际成交数量更新持仓，剩余撤销 |
| 超仓风险 | 若成交后超5000元，撤销剩余单 |
| 14:50后 | 取消所有未成委托 |

## 安全机制

1. **硬性止损线**: 总资产亏损10%永久停止交易
2. **日亏损熔断**: 当日亏损100元停止等待下一日
3. **仓位上限**: 任何时候总持仓不超过5000元
4. **无杠杆**: 不使用融资融券
5. **只做模拟盘（初期）**: 至少模拟3个月再考虑实盘
