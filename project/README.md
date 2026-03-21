# ETF网格交易系统

基于网格交易策略的量化交易系统，监控ETF价格波动，在价格下跌时分档买入，在价格上涨时分档卖出，赚取确定性的小额利润。

**目标用户**: 资金在1万以下的个人投资者，追求极致安全，不碰杠杆和期货。

---

## 功能特性

- **网格策略**: 10档网格，5%间距，低买高卖
- **极致风控**: 仓位上限5000元，日亏损熔断100元，总资产止损线9000元
- **实时监控**: Flask Web监控面板，微信Server酱推送通知
- **回测验证**: 历史数据回测，支持多种市场环境测试
- **模拟/实盘**: 支持聚宽纸盘模拟和实盘交易

---

## 项目结构

```
project/
├── config.yaml              # 配置文件
├── requirements.txt         # Python依赖
├── main.py                 # 主程序入口
│
├── utils/
│   ├── grid_calculator.py  # 网格计算工具
│   └── position_tracker.py  # 持仓追踪（SQLite）
│
├── engines/
│   ├── data.py             # 数据引擎（聚宽API）
│   ├── execution.py        # 执行引擎（订单管理）
│   └── risk.py             # 风控引擎
│
├── strategies/
│   └── grid.py             # 网格交易策略
│
├── notification/
│   └── notifier.py         # 微信通知（Server酱）
│
├── web/
│   ├── app.py              # Flask Web服务
│   └── templates/
│       └── index.html      # 监控面板页面
│
├── backtest/
│   └── runner.py           # 回测运行器
│
├── data/                   # 数据存储目录
│   └── .gitkeep
│
└── tests/                  # 单元测试
    ├── conftest.py
    └── utils/
```

---

## 安装指南

### 环境要求

- Python 3.10+
- Windows/Linux/macOS

### 步骤

#### 1. 克隆项目

```bash
git clone <repository_url>
cd project
```

#### 2. 创建虚拟环境（推荐）

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

#### 3. 安装依赖

```bash
pip install -r requirements.txt
```

依赖列表:
```
jqdatasdk==1.8.47   # 聚宽数据API
flask>=2.0.0         # Web框架
pyyaml>=5.4.0        # 配置文件解析
requests>=2.25.0     # HTTP请求（用于微信通知）
pytest>=7.0.0        # 单元测试
```

#### 4. 配置聚宽账号

在 `config.yaml` 中配置聚宽账号:

```yaml
broker:
  name: joinquant
  account_type: simulated  # simulated=纸盘, live=实盘
```

**注意**: 聚宽API需要注册账号并获取API Key。注册地址: https://www.joinquant.com

#### 5. 配置微信通知（可选）

1. 前往 https://sct.ftqq.com 注册Server酱账号
2. 获取SCKEY
3. 在 `config.yaml` 中填入:

```yaml
notification:
  server酱_key: "your_sckey_here"
```

留空则禁用微信通知。

#### 6. 运行测试

```bash
# 运行所有测试
pytest -v

# 运行特定模块测试
pytest tests/utils/ -v
pytest engines/ -v
```

#### 7. 启动系统

```bash
# 启动交易系统
python main.py

# 启动Web监控面板
python -m web.app
# 访问 http://localhost:5000
```

---

## 配置说明

### config.yaml 完整配置

```yaml
# 网格设置
grid:
  levels: 10           # 网格格数（单边）
  spacing: 0.05        # 网格间距（5%）
  unit_size: 500       # 每格交易金额（元）

# 风控设置
risk:
  initial_capital: 10000  # 初始本金（元）
  max_position: 5000   # 最大持仓（元）
  max_daily_loss: 100  # 日最大亏损（元）
  total_stop_loss: 9000  # 总资产止损线（元）

# 券商设置
broker:
  name: joinquant      # 聚宽
  account_type: simulated  # simulated=纸盘, live=实盘

# 市场设置
market:
  etf_code: 510300     # 沪深300ETF
  trading_hours:
    open: "09:30"      # 开盘时间
    close: "15:00"     # 收盘时间
    cancel_before: "14:50"  # 停止下单时间

# 通知设置
notification:
  server酱_key: ""      # Server酱SCKEY，留空则禁用

# 数据库设置
database:
  path: "data/trading.db"
```

---

## 使用说明

### 启动交易

```bash
python main.py
```

系统将:
1. 每日09:25获取前一交易日收盘价作为基准价
2. 09:30开盘时初始化10档网格
3. 每10秒检查价格，触发网格信号时自动交易
4. 14:50后停止新下单，收盘后结算

### 查看监控面板

```bash
python -m web.app
```

访问 http://localhost:5000 查看:
- 当前价格和行情
- 账户概览（总资产、持仓、市值）
- 风控状态
- 持仓明细
- 交易记录

### 运行回测

```bash
python -m backtest.runner
```

或导入使用:

```python
from backtest.runner import BacktestRunner
import random

# 生成模拟数据
prices = [4.0]
for _ in range(100):
    change = random.uniform(-0.05, 0.05)
    prices.append(round(prices[-1] * (1 + change), 3))

# 运行回测
config = {'grid': {'levels': 10, 'spacing': 0.05}, 'risk': {}}
runner = BacktestRunner(config)
result = runner.run(prices)

print(f"收益率: {result['total_return']*100:.2f}%")
print(f"胜率: {result['win_rate']*100:.2f}%")
```

---

## 风控机制

| 规则 | 设定值 | 说明 |
|------|--------|------|
| 总仓位上限 | 5000元 | 任何时候总持仓不超过5000元 |
| 单笔交易上限 | 500元 | 每格交易金额限制 |
| 日最大亏损 | 100元 | 当日亏损达100元停止交易 |
| 总资产止损线 | 9000元 | 亏损10%永久停止交易 |
| 杠杆使用 | 零杠杆 | 不使用融资融券 |

---

## 网格交易原理

### 网格状态机

```
档位状态机（每个档位独立运作）:

空仓 ──价格触及──> 持仓中
  ^                    │
  │    价格触及        │
  └────────────────────┘

规则: 每个档位只能持仓1个单元，不可重复加仓
```

### 每日流程

```
09:25  获取前一交易日收盘价 → 计算10档网格
09:30  开盘
        ↓
每10秒轮询价格，检查触发条件
        ├── 价格跌破档位 + 该档位空仓 → 买入
        ├── 价格涨破档位 + 该档位有持仓 → 卖出
        └── 价格跳空超过1档 → 每tick最多处理1格
        ↓
14:50  取消所有未成委托
15:00  收盘结算
```

---

## 预期收益与风险

### 预期收益（保守估算）

| 市场环境 | 月收益 | 年化收益 |
|----------|--------|----------|
| 震荡市 | 1-3% | 12-36% |
| 单边上涨 | 较高 | 较高（但有限） |
| 单边下跌 | 亏损 | 亏损 |
| 横盘整理 | 稳定 | 稳定 |

**注意**: 网格策略不适合单边行情，只适合震荡市。1万资金预期年化10-20%已算不错。

### 风险提示

1. **单边下跌风险**: 价格持续下跌会套牢，网格下限可缓解
2. **流动性风险**: ETF流动性好，基本无此问题
3. **系统性风险**: 大盘崩盘时无法避免亏损

---

## 开发指南

### 添加新模块

1. 在对应目录创建模块文件
2. 编写单元测试（放在 `tests/` 目录）
3. 运行 `pytest` 确保测试通过
4. 更新本README

### 代码规范

- 使用类型注解（typing）
- 遵循PEP 8
- 所有公共方法需有docstring
- 测试覆盖率尽量100%

### 运行测试

```bash
# 所有测试
pytest -v

# 带覆盖率
pytest --cov=. --cov-report=html

# 特定文件
pytest tests/utils/test_grid_calculator.py -v
```

---

## 技术参考

- [聚宽文档](https://www.joinquant.com/help#help-name-9)
- [Server酱（微信推送）](https://sct.ftqq.com)
- [网格交易原理](https://www.joinquant.com/help#help-name-9)

---

## License

MIT License
