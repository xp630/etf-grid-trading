"""
微信通知器 - 通过Server酱发送微信通知
"""
import requests
from typing import Optional


class Notifier:
    """
    微信通知器

    使用Server酱（sct.ftqq.com）推送微信消息
    申请地址：https://sct.ftqq.com
    """

    def __init__(self, server酱_key: str = None):
        """
        初始化通知器

        Args:
            server酱_key: Server酱的SCKEY，留空则禁用通知
        """
        self.key = server酱_key
        self.enabled = bool(server酱_key)
        self.api_url = f'https://sct.ftqq.com/{server酱_key}.send' if server酱_key else None
        # 注意：api_url在send()时才验证enabled状态

    def send(self, title: str, content: str, short: bool = False) -> bool:
        """
        发送通知

        Args:
            title: 标题
            content: 内容
            short: 是否使用短消息（True时不保留历史记录）

        Returns:
            是否发送成功
        """
        if not self.enabled:
            return False

        try:
            data = {
                'text': title,
                'desp': content
            }

            if short:
                data['short'] = 'true'

            response = requests.post(self.api_url, data=data, timeout=10)

            return response.status_code == 200

        except Exception as e:
            # 通知失败不影响主流程
            print(f"Failed to send notification: {e}")
            return False

    def send_trade(self, action: str, symbol: str, price: float, quantity: int, **kwargs) -> bool:
        """
        发送交易通知

        Args:
            action: 'buy' 或 'sell'
            symbol: 标的代码
            price: 成交价格
            quantity: 成交数量
            level_index: 档位索引（可选）
            profit: 盈利金额（可选）
        """
        from datetime import datetime
        action_text = '买入' if action == 'buy' else '卖出'
        action_emoji = '📈' if action == 'buy' else '📉'
        level_idx = kwargs.get('level_index', 0)
        profit = kwargs.get('profit')

        title = f'{action_emoji} 交易提醒：{action_text}'

        profit_line = f"**盈利：{profit:.2f}元**" if profit is not None else ""
        content = f"""
## {action_text}交易

| 项目 | 值 |
|------|-----|
| 标的 | **{symbol}** |
| 操作 | {action_text} |
| 价格 | **{price:.3f}元** |
| 数量 | {quantity}股 |
| 金额 | **{price * quantity:.2f}元** |
| 档位 | 第{level_idx + 1}档 |
| 时间 | {datetime.now().strftime('%H:%M:%S')} |

{profit_line}
"""
        return self.send(title, content)

    def send_risk_warning(self, warning_type: str, value: float, **kwargs) -> bool:
        """
        发送风险警告

        Args:
            warning_type: 'daily_loss' / 'position_limit' / 'total_assets'
            value: 警告值
            limit: 限额（可选）
        """
        limit = kwargs.get('limit', 0)

        if warning_type == 'daily_loss':
            title = '⚠️ 日亏损警告'
            content = f"""
## 日亏损警告

> 当前日亏损已达 **{value:.2f}元**

建议：暂停交易，关注市场走势。

---
*收到此通知表示系统已触发日亏损熔断机制*
"""
        elif warning_type == 'position_limit':
            title = '⚠️ 仓位超限警告'
            content = f"""
## 仓位超限

> 当前仓位 **{value:.2f}元**

建议：适当减仓，控制风险。

---
*仓位接近或超过上限*
"""
        elif warning_type == 'total_assets':
            title = '🚨 总资产警告'
            content = f"""
## 总资产接近止损线

> 当前总资产 **{value:.2f}元**（止损线：{limit:.2f}元）

建议：密切关注，必要时手动止损。

---
*资产持续下降*
"""
        else:
            title = '⚠️ 风险警告'
            content = f"风险指标：{warning_type} = {value}"

        return self.send(title, content, short=True)

    def send_stop_loss(self, total_assets: float, **kwargs) -> bool:
        """
        发送止损通知

        Args:
            total_assets: 当前总资产
            initial_capital: 初始本金（可选）
            loss_ratio: 亏损比例（可选）
        """
        initial = kwargs.get('initial_capital', 10000)
        loss_ratio = kwargs.get('loss_ratio', 0)
        stop_loss_line = kwargs.get('stop_loss_line', 9000)

        title = '🚨 触及总止损线 - 系统已停止'

        content = f"""
## 紧急：触及总资产止损线

| 项目 | 值 |
|------|-----|
| 当前总资产 | **{total_assets:.2f}元** |
| 初始本金 | {initial:.2f}元 |
| 亏损金额 | **{(initial - total_assets):.2f}元** |
| 亏损比例 | **{loss_ratio:.2%}** |
| 止损线 | {stop_loss_line:.2f}元 |

### 系统状态
**所有交易已停止**

请人工检查后决定是否：
1. 调整止损线后重启
2. 清算所有持仓
3. 分析亏损原因

---
*此为系统最终保护机制*
"""
        return self.send(title, content)

    def send_error(self, error_message: str, **kwargs) -> bool:
        """
        发送错误通知

        Args:
            error_message: 错误信息
            error_type: 错误类型（可选）
        """
        error_type = kwargs.get('error_type', 'Unknown')
        timestamp = kwargs.get('timestamp')

        title = '❌ 系统异常'
        time_str = timestamp or '未知时间'

        content = f"""
## 系统异常

> **{error_type}**

```
{error_message}
```

| 项目 | 值 |
|------|-----|
| 发生时间 | {time_str} |
| 错误类型 | {error_type} |

### 建议
1. 检查系统日志
2. 确认网络连接
3. 验证API配置

---
*系统将继续运行，但建议尽快检查*
"""
        return self.send(title, content)

    def send_daily_summary(self, daily_pnl: float, trades: list, positions: dict, **kwargs) -> bool:
        """
        发送每日总结

        Args:
            daily_pnl: 当日盈亏
            trades: 当日交易列表
            positions: 当前持仓
            total_assets: 总资产（可选）
            initial_capital: 初始本金（可选）
        """
        from datetime import datetime
        total_assets = kwargs.get('total_assets', 0)
        initial_capital = kwargs.get('initial_capital', 10000)
        win_count = sum(1 for t in trades if t.get('profit', 0) > 0)
        loss_count = len(trades) - win_count
        win_rate = f"{win_count / len(trades) * 100:.0f}%" if trades else "0%"

        pnl_emoji = '📈' if daily_pnl >= 0 else '📉'
        pnl_class = 'profit' if daily_pnl >= 0 else 'loss'
        title = f'{pnl_emoji} 每日总结 {datetime.now().strftime("%m/%d")}'

        # 格式化交易
        trades_text = ""
        for t in trades:
            action = '买入' if t['action'] == 'buy' else '卖出'
            profit = t.get('profit')
            profit_str = f"(盈利{profit:.2f}元)" if profit is not None else ""
            trades_text += f"| {action} | {t['quantity']}股 @{t['price']:.3f} {profit_str} |\n"

        if not trades_text:
            trades_text = "| - | 今日无交易 |"

        # 格式化持仓
        positions_text = ""
        total_position_value = 0
        for symbol, info in positions.items():
            value = info['quantity'] * (kwargs.get('current_price', info['avg_price']))
            total_position_value += value
            positions_text += f"| {symbol} | {info['quantity']}股 @ {info['avg_price']:.3f} | 市值 {value:.2f}元 |\n"

        if not positions_text:
            positions_text = "| - | 空仓 | - |"

        content = f"""
## {pnl_class.upper()} {datetime.now().strftime("%Y-%m-%d")} 交易总结

### 账户概览

| 项目 | 数值 |
|------|------|
| 当日盈亏 | **{daily_pnl:+.2f}元** |
| 总资产 | **{total_assets:.2f}元** |
| 初始本金 | {initial_capital:.2f}元 |
| 累计收益率 | **{((total_assets - initial_capital) / initial_capital * 100):+.2f}%** |

### 持仓状态

| 标的 | 数量 | 成本价 | 市值 |
|------|------|--------|------|
{positions_text}

> 总持仓市值：{total_position_value:.2f}元
> 可用资金：{total_assets - total_position_value:.2f}元

### 交易统计

| 指标 | 数值 |
|------|------|
| 交易次数 | {len(trades)} |
| 盈利交易 | {win_count} |
| 亏损交易 | {loss_count} |
| 胜率 | {win_rate} |

### 交易明细

| 操作 | 数量 | 价格 |
|------|------|------|
{trades_text}

---
*📊 ETF网格交易系统 自动推送*
"""
        return self.send(title, content)