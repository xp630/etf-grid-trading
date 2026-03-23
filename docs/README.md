# ETF 网格交易系统文档

> 快速入门请参考 [project/README.md](../project/README.md)

## 文档索引

| 文档 | 受众 | 内容 |
|------|------|------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | 开发者 | 系统设计、组件关系、数据流、错误处理 |
| [GRID_TRADING.md](GRID_TRADING.md) | 用户/开发者 | 网格原理、信号逻辑、配置参数、风控机制 |
| [API.md](API.md) | 开发者 | 所有模块的类、方法、参数说明 |
| [BACKTEST_REPORT.md](BACKTEST_REPORT.md) | 用户 | 回测方法论、结果分析、配置建议 |
| [OPERATION.md](OPERATION.md) | 运维 | 启动方式、监控面板使用、故障排查 |

## 系统概览

```
交易引擎（project/main.py）
    ↓
DataEngine → 多数据源（AkShare/JoinQuant/Tushare/Mock）
    ↓
TrendGridStrategy（趋势过滤 + AI网格间距 + 自动单位）
    ↓ check_signals()
ExecutionEngine → RiskEngine.check_all() → 聚宽模拟账户
    ↓
PositionTracker（SQLite）+ Notifier（Server酱微信通知）
```

## 目录结构

```
project/
├── main.py              # CLI 入口，TradingSystem 主类
├── config.yaml          # 所有配置集中在此
├── strategies/
│   ├── grid.py          # 基础网格策略（GridStrategy）
│   ├── trend_grid_live.py # 增强版：趋势过滤+AI间距+自动单位
│   └── variants/        # 策略变体：无限网格、追踪止损
├── engines/
│   ├── data.py          # 数据引擎
│   ├── execution.py     # 执行引擎
│   ├── risk.py          # 风控引擎
│   └── metrics.py       # 指标计算 + AI市场分析
├── utils/
│   ├── grid_calculator.py # 网格档位计算
│   ├── position_tracker.py # SQLite 持仓追踪
│   ├── llm_service.py    # AI（MiniMax/OpenAI/DeepSeek）
│   └── market_calendar.py # A股日历
├── backtest/
│   └── runner.py         # 回测运行器
├── notification/
│   └── notifier.py      # Server酱微信通知
└── web/
    ├── streamlit_app.py  # Streamlit 监控面板（:8501）
    ├── app.py           # Flask 监控面板（废弃）
    └── api_server.py    # Flask API 服务（:5001）
```

## 版本信息

- 系统版本：见 `project/config.yaml` 的 `version` 字段
- 文档更新：2026-03-23
