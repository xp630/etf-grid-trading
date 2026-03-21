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

    def send_trade(self, action: str, symbol: str, price: float, quantity: int) -> bool:
        """
        发送交易通知

        Args:
            action: 'buy' 或 'sell'
            symbol: 标的代码
            price: 成交价格
            quantity: 成交数量
        """
        action_text = '买入' if action == 'buy' else '卖出'
        title = f'交易提醒：{action_text}'
        content = f"""
## 交易提醒

- 操作：{action_text}
- 标的：{symbol}
- 价格：{price:.3f}元
- 数量：{quantity}股
- 金额：{price * quantity:.2f}元
"""
        return self.send(title, content)

    def send_risk_warning(self, warning_type: str, value: float) -> bool:
        """
        发送风险警告

        Args:
            warning_type: 'daily_loss' 或 'position_limit'
            value: 警告值
        """
        if warning_type == 'daily_loss':
            title = '⚠️ 日亏损警告'
            content = f"今日亏损已达 **{value:.2f}元**，请关注"
        elif warning_type == 'position_limit':
            title = '⚠️ 仓位超限警告'
            content = f"当前仓位 **{value:.2f}元** 接近上限"
        else:
            title = '⚠️ 风险警告'
            content = f"风险指标：{warning_type} = {value}"

        return self.send(title, content, short=True)

    def send_stop_loss(self, total_assets: float) -> bool:
        """
        发送止损通知

        Args:
            total_assets: 当前总资产
        """
        title = '🚨 触及总止损线'
        content = f"""
## 紧急：触及总资产止损线

当前总资产：**{total_assets:.2f}元**

系统已停止所有交易。请人工检查后决定是否继续。
"""
        return self.send(title, content)

    def send_error(self, error_message: str) -> bool:
        """
        发送错误通知

        Args:
            error_message: 错误信息
        """
        title = '❌ 系统异常'
        content = f"""
## 系统异常

```
{error_message}
```

请检查系统运行状态。
"""
        return self.send(title, content)

    def send_daily_summary(self, daily_pnl: float, trades: list, positions: dict) -> bool:
        """
        发送每日总结

        Args:
            daily_pnl: 当日盈亏
            trades: 当日交易列表
            positions: 当前持仓
        """
        pnl_emoji = '📈' if daily_pnl >= 0 else '📉'
        title = f'{pnl_emoji} 每日总结'

        trades_text = '\n'.join([
            f"- {t['action']} {t['symbol']} {t['quantity']}股 @{t['price']}"
            for t in trades
        ]) or '无交易'

        positions_text = '\n'.join([
            f"- {symbol}: {info['quantity']}股 @ {info['avg_price']}"
            for symbol, info in positions.items()
        ]) or '无持仓'

        content = f"""
## 每日总结

### 当日盈亏
**{daily_pnl:.2f}元**

### 持仓
{positions_text}

### 交易记录
{trades_text}
"""
        return self.send(title, content)