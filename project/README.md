# ETF网格交易系统

基于网格交易策略的量化交易系统，监控ETF价格波动，在价格下跌时分档买入，在价格上涨时分档卖出，赚取确定性的小额利润。

**目标用户**: 资金在1万以下的个人投资者，追求极致安全，不碰杠杆和期货。
**交易品种**: 沪深300ETF (510300) - 稳定、低费率、无T+1

> 详细技术文档见 [docs/GRID_TRADING.md](../docs/GRID_TRADING.md)

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
└── tests/                  # 单元测试
    ├── conftest.py
    └── ...
```

---

## 安装指南

### 环境要求

- Python 3.10+
- Windows/Linux/macOS

### 步骤

```bash
# 1. 克隆项目
git clone <repository_url>
cd project

# 2. 创建虚拟环境（推荐）
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/macOS: source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 设置聚宽环境变量
# Windows:
setx JQCLOUD_USERNAME "你的账号"
setx JQCLOUD_PASSWORD "你的密码"
# Linux/macOS:
export JQCLOUD_USERNAME=你的账号
export JQCLOUD_PASSWORD=你的密码

# 5. 配置微信通知（可选）
# 在 config.yaml 中填入 Server酱 SCKEY
```

### 依赖列表

```
jqdatasdk==1.9.8   # 聚宽数据API
flask>=2.0.0       # Web框架
pyyaml>=5.4.0      # 配置文件解析
requests>=2.25.0   # HTTP请求
pytest>=7.0.0      # 单元测试
```

---

## 快速入门

```bash
# 启动交易系统
python main.py

# 启动Web监控面板（另一个终端）
python web/app.py
# 访问 http://localhost:5000
```

**每日流程**:
1. 09:25 - 获取前一交易日收盘价作为基准价
2. 09:30 - 初始化10档网格
3. 每10秒 - 检查价格，触发信号时自动交易
4. 14:50 - 取消所有未成委托
5. 15:00 - 收盘结算

---

## 风控机制

| 规则 | 设定值 | 说明 |
|------|--------|------|
| 总仓位上限 | 5000元 | 任何时候总持仓不超过5000元 |
| 日最大亏损 | 100元 | 当日亏损达100元停止交易 |
| 总资产止损线 | 9000元 | 亏损10%永久停止交易 |
| 杠杆使用 | 零杠杆 | 不使用融资融券 |

> 详细风控逻辑见 [docs/GRID_TRADING.md](../docs/GRID_TRADING.md#6-风控机制)

---

## 预期收益与风险

### 预期收益（保守估算）

| 市场环境 | 月收益 | 年化收益 |
|----------|--------|----------|
| 震荡市 | 1-3% | 12-36% |
| 单边上涨 | 较高 | 较高（但有限） |
| 单边下跌 | 亏损 | 亏损 |

**注意**: 网格策略不适合单边行情。1万资金预期年化10-20%已算不错。

### 风险提示

1. **单边下跌风险**: 价格持续下跌会套牢
2. **流动性风险**: ETF流动性好，基本无此问题
3. **系统性风险**: 大盘崩盘时无法避免亏损

---

## 使用说明

### 运行回测

```bash
python -m backtest.runner
```

### 查看监控面板

访问 http://localhost:5000 查看:
- 当前价格和行情
- 账户概览（总资产、持仓、市值）
- 风控状态
- 持仓明细
- 交易记录

---

## 开发指南

### 运行测试

```bash
# 所有测试
pytest -v

# 带覆盖率
pytest --cov=. --cov-report=html

# 特定文件
pytest tests/utils/test_grid_calculator.py -v
```

### 代码规范

- 使用类型注解（typing）
- 遵循PEP 8
- 所有公共方法需有docstring

---

## 技术参考

- [聚宽文档](https://www.joinquant.com/help#help-name-9)
- [Server酱（微信推送）](https://sct.ftqq.com)

---

*详细技术文档: [docs/GRID_TRADING.md](../docs/GRID_TRADING.md)*
