# 运维手册

> 面向操作人员。本文档描述如何启动、监控和排查故障。

---

## 1. 快速开始

### 1.1 环境要求

- Python 3.8+
- pip 依赖已安装：`pip install -r project/requirements.txt`

### 1.2 环境变量

| 变量 | 必填 | 说明 |
|------|------|------|
| `JQCLOUD_USERNAME` | 聚宽实盘时 | 聚宽账号 |
| `JQCLOUD_PASSWORD` | 聚宽实盘时 | 聚宽密码 |
| `AI_API_KEY` | AI 功能时 | MiniMax/OpenAI/DeepSeek API Key |
| `TUSHARE_TOKEN` | Tushare 数据源时 | Tushare Pro Token |
| `SERVERCHAN_KEY` | 微信通知时 | Server酱 SCKEY |

**设置方式（永久）**：
- Windows：`setx JQCLOUD_USERNAME "xxx"`（需重启终端）
- Linux/macOS：`export JQCLOUD_USERNAME=xxx`（写入 `~/.bashrc` 或 `~/.zshrc`）

### 1.3 启动方式

**方式一：命令行启动交易系统**
```bash
# 进入项目目录
cd /path/to/etf-grid-trading

# 设置环境变量（可选，取决于配置）
export JQCLOUD_USERNAME=xxx
export JQCLOUD_PASSWORD=xxx

# 运行
python project/main.py
```

**方式二：启动 Web 监控面板**
```bash
streamlit run project/web/streamlit_app.py --server.port 8501
```
访问 http://localhost:8501

**方式三：启动 Flask API 服务（含交易循环）**
```bash
python project/web/api_server.py
```
API 服务运行于 http://localhost:5001，后台同时运行交易循环。

**方式四：一键脚本（推荐）**
```bash
# Linux/macOS
./run.sh start

# Windows
run.bat start
```

---

## 2. 配置文件

所有配置集中在 `project/config.yaml`。**不要直接修改 `config.yaml`**，通过 Web 界面（:8501 设置页）或以下方式修改：

```bash
# 修改 config.yaml 后，重启系统使配置生效
```

### 2.1 首次配置清单

- [ ] 确认 `market.etf_code` 为 `510300`（沪深300ETF）
- [ ] 设置 `risk.initial_capital`（初始本金）
- [ ] 配置 `notification.server酱_key`（否则收不到微信通知）
- [ ] 配置数据源：`data_source.index`（默认 `akshare`，无需 API Key）
- [ ] 如使用聚宽：设置 `JQCLOUD_USERNAME` 和 `JQCLOUD_PASSWORD` 环境变量

---

## 3. 监控面板使用

### 3.1 仪表盘（默认页）

显示内容：
- **持仓状态**：各档位持仓数量、均价
- **资金状况**：总资产、现金、持仓市值
- **日盈亏**：当日已实现盈亏
- **网格状态**：基准价、当前价、各档位状态

**正常状态指示**：
- 每日 14:55 收到微信总结通知
- 日志无 ERROR 级别记录
- `running` 状态为 `True`

### 3.2 市场分析页

- 预设指数：上证指数、深证成指、创业板指等
- 手动输入股票代码查看走势
- **AI 解读**：点击按钮获取 AI 策略建议

### 3.3 回测分析页

- 选择回测时间段
- 查看历史收益曲线、最大回撤
- 不同配置对比

### 3.4 设置页

- 通知测试（点击"测试"按钮）
- AI 模型切换（MiniMax/OpenAI/DeepSeek）
- 数据源切换（AkShare/聚宽/Tushore/Mock）
- **配置修改后点击"保存"**

---

## 4. 每日操作流程

```
09:25 ─ 系统自动获取基准价，初始化网格
           ↓
09:30 ─ 交易循环启动（每10秒检查一次）
           ↓
09:30-14:50 ─ 被动运行，无需人工干预
           ↓
14:50 ─ 自动取消未成委托
           ↓
14:55 ─ 收到微信日总结通知
           ↓
14:55-15:00 ─ 检查通知，确认当日无异常
```

**需要人工干预的情况**：
- 收到风控警告微信（仓位/日亏损超限）
- 收到总资产止损通知（需评估是否重启）
- 系统异常无法自动恢复

---

## 5. 故障排查

### 5.1 症状自查表

| 症状 | 可能原因 | 解决方案 |
|------|---------|---------|
| 启动报错 `ModuleNotFoundError` | 依赖未安装 | `pip install -r project/requirements.txt` |
| 一直报 `market_closed` | 非交易时间，或日期错误 | 确认系统时间正确 |
| 无法获取价格 | AkShare/聚宽 API 不稳定 | 等待自动恢复，或切换数据源 |
| 微信通知收不到 | Server酱 Key 错误 | 检查 `notification.server酱_key` 配置 |
| 模拟交易不成交 | 聚宽账号权限问题 | 检查聚宽账号状态 |
| 回测图表不显示 | HTML 文件被拦截 | 浏览器允许弹窗，或手动打开 HTML 文件 |

### 5.2 查看日志

```bash
# 查看最近日志
tail -n 50 logs/trading.log

# 实时跟踪日志
tail -f logs/trading.log

# 搜索错误
grep "ERROR" logs/trading.log
```

### 5.3 数据源切换（紧急恢复）

如果 AkShare 持续失败，可手动切换到 Mock 模式继续测试：

```yaml
# project/config.yaml
data_source:
  index: mock  # 临时使用模拟数据
```

### 5.4 重置系统

如需清空持仓记录重新开始：

```bash
# 删除数据库文件
rm trading.db

# 重启系统
python project/main.py
```

**注意**：清空数据库后历史交易记录无法恢复。

---

## 6. 交易限制与注意事项

### 6.1 当前系统限制

- **仅支持模拟交易**：不支持实盘下单
- **价格延迟**：AkShare/聚宽数据可能有 15 分钟延迟
- **聚宽免费账号**：数据范围仅支持 15 个月内

### 6.2 风险警示

- 网格策略在单边行情中可能持续亏损
- 日亏损熔断触发后，系统会停止当日交易（下一日自动恢复）
- 总资产止损触发后需手动重启系统
- 建议至少观察 1 个月再决定是否长期运行

### 6.3 紧急联系人

- 系统问题：查看日志文件 `logs/trading.log`
- 聚宽问题：https://www.joinquant.com/help
- Server酱问题：https://sct.ftqq.com

---

## 7. 目录结构

```
project/
├── main.py              # CLI 入口
├── config.yaml          # 配置文件
├── trading.db           # SQLite 数据库（持仓、交易记录）
└── logs/
    └── trading.log      # 交易日志
```

---

*文档更新时间：2026-03-23*
