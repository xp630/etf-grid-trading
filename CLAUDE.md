# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

ETF网格交易系统 - 基于网格策略的量化交易系统，监控沪深300ETF(510300)价格波动，低买高卖赚取确定性利润。目标用户：1万以下个人投资者，极致安全，不碰杠杆。

## 常用命令

```bash
# 安装依赖
pip install -r project/requirements.txt

# 运行交易系统（需要设置环境变量）
JQCLOUD_USERNAME=xxx JQCLOUD_PASSWORD=xxx python project/main.py

# 运行Web监控面板
python project/web/app.py

# 运行所有测试
pytest project/ -v

# 运行特定模块测试
pytest project/tests/utils/ -v
pytest project/engines/ -v
```

环境变量：Windows用`setx JQCLOUD_USERNAME "xxx"`永久设置，Linux用`export`。

## 系统架构

```
DataEngine (聚宽API)
    ↓ get_current_price(), get_baseline_price()
GridStrategy (网格策略) ← 需要 DataEngine, ExecutionEngine, RiskEngine, PositionTracker
    ↓ check_signals() → signals
ExecutionEngine (执行引擎)
    ↓ place_order() → 风控检查 → 订单提交
RiskEngine (风控) + PositionTracker (SQLite)
    ↑ check_all(), record_buy/sell
```

**初始化顺序**：`TradingSystem.__init__()` 按此顺序创建组件：
DataEngine → RiskEngine → ExecutionEngine → GridStrategy

**每日流程**：09:25获取基准价 → 09:30初始化10档网格 → 每10秒run_once() → 14:50取消未成委托

## 核心参数 (config.yaml)

| 参数 | 默认值 | 说明 |
|------|--------|------|
| grid.levels | 10 | 网格格数（单边） |
| grid.spacing | 0.05 | 网格间距（5%） |
| grid.unit_size | 500 | 每格交易金额（元） |
| risk.max_position | 5000 | 最大持仓 |
| risk.max_daily_loss | 100 | 日最大亏损熔断 |
| risk.total_stop_loss | 9000 | 总资产止损线 |

## 风控机制

1. **买入前检查**：`RiskEngine.check_all()` 验证仓位和资金
2. **日亏损熔断**：当日亏损达100元停止交易，等待下一日
3. **总资产止损**：亏损10%（9000元）永久停止
4. **仓位上限**：任何时候持仓不超过5000元

## 开发注意事项

1. **聚宽认证**：`DataEngine.__init__()` 自动从环境变量读取并认证
2. **Mock模式**：聚宽不可用时(ImportError)自动使用模拟价格3.70~3.90
3. **14:50后**：非交易时间每60秒检查一次，开盘后每10秒执行
4. **订单处理**：`ExecutionEngine._submit_order()` 调用聚宽API，失败返回mock订单ID

## 关键实现模式

- **信号逻辑**：`GridStrategy.check_signals()` 每次最多处理1个信号
  - 买入：price < 基准价 AND price < level_price AND 档位空仓
  - 卖出：price > level_price AND 档位有持仓
- **持仓追踪**：`PositionTracker` 持有SQLite连接，positions表和trades表
- **回测**：`BacktestRunner.run(price_data, dates)` 返回总收益率/最大回撤/胜率

## 入口文件

- `project/main.py` - TradingSystem主类，run()方法
- `project/web/app.py` - Flask Web服务，路由：/api/status, /api/risk/status
- `project/config.yaml` - 所有配置集中在此

## 参考

- 聚宽: https://www.joinquant.com/help
- Server酱: https://sct.ftqq.com
