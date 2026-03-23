"""
回测运行器 - 使用历史数据回测策略
"""
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.position_tracker import PositionTracker
from utils.grid_calculator import GridCalculator


class BacktestRunner:
    """
    回测运行器

    使用历史价格数据回测网格策略
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.grid_config = config.get('grid', {})
        self.risk_config = config.get('risk', {})

        # 结果存储
        self.trades: List[Dict] = []
        self.daily_pnl: List[Dict] = []
        self.initial_capital = self.risk_config.get('initial_capital', 10000)

    def run(self, price_data: List[float], dates: List[str] = None) -> Dict[str, Any]:
        """
        运行回测

        Args:
            price_data: 历史价格列表
            dates: 对应日期列表

        Returns:
            回测结果
        """
        if dates is None:
            dates = [f"Day {i}" for i in range(len(price_data))]

        capital = self.initial_capital
        position = None  # 当前持仓
        grid = None

        for i, price in enumerate(price_data):
            date = dates[i] if i < len(dates) else f"Day {i}"

            # 每天开盘时重置网格
            if i == 0 or (i > 0 and price_data[i-1] != price):
                baseline = price_data[i-1] if i > 0 else price
                grid = GridCalculator(
                    base_price=baseline,
                    levels=self.grid_config.get('levels', 10),
                    spacing=self.grid_config.get('spacing', 0.05)
                )

            # 检查买入信号
            if position is None:
                # 应该在某档位买入
                level_index = grid.get_level_index(price)
                buy_price = grid.get_price_at_level(level_index)

                if price <= buy_price * 1.01:  # 5%范围内买入
                    quantity = 100  # 1手
                    cost = buy_price * quantity
                    if cost <= capital:
                        position = {
                            'buy_price': buy_price,
                            'quantity': quantity,
                            'level_index': level_index,
                            'date': date
                        }
                        capital -= cost
                        self.trades.append({
                            'date': date,
                            'action': 'buy',
                            'price': buy_price,
                            'quantity': quantity
                        })

            # 检查卖出信号
            elif position:
                level_index = grid.get_level_index(price)
                if level_index > position['level_index']:
                    # 价格涨到更高档，卖出
                    sell_price = grid.get_price_at_level(position['level_index'])

                    if price >= sell_price * 0.99:  # 5%范围内卖出
                        revenue = sell_price * position['quantity']
                        capital += revenue
                        pnl = revenue - position['buy_price'] * position['quantity']

                        self.trades.append({
                            'date': date,
                            'action': 'sell',
                            'price': sell_price,
                            'quantity': position['quantity'],
                            'pnl': pnl
                        })

                        position = None

            # 记录每日权益
            position_value = position['buy_price'] * position['quantity'] if position else 0
            self.daily_pnl.append({
                'date': date,
                'price': price,
                'capital': capital,
                'position_value': position_value,
                'total': capital + position_value
            })

        # 计算统计指标
        return self._calculate_stats()

    def _calculate_stats(self) -> Dict[str, Any]:
        """计算回测统计指标"""
        if not self.daily_pnl:
            return {}

        total_value = self.daily_pnl[-1]['total']
        total_return = (total_value - self.initial_capital) / self.initial_capital

        # 计算最大回撤
        peak = self.initial_capital
        max_drawdown = 0
        for day in self.daily_pnl:
            if day['total'] > peak:
                peak = day['total']
            drawdown = (peak - day['total']) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        # 计算胜率
        sell_trades = [t for t in self.trades if t['action'] == 'sell']
        winning_trades = [t for t in sell_trades if t.get('pnl', 0) > 0]
        win_rate = len(winning_trades) / len(sell_trades) if sell_trades else 0

        # 总盈亏
        total_pnl = sum(t.get('pnl', 0) for t in self.trades if t['action'] == 'sell')

        return {
            'initial_capital': self.initial_capital,
            'final_value': total_value,
            'total_return': total_return,
            'total_pnl': total_pnl,
            'max_drawdown': max_drawdown,
            'total_trades': len(self.trades),
            'sell_trades': len(sell_trades),
            'win_rate': win_rate,
            'daily_pnl': self.daily_pnl,
            'trades': self.trades
        }

    def generate_chart_html(self, title: str = "回测结果") -> str:
        """
        生成回测结果图表HTML

        Args:
            title: 图表标题

        Returns:
            HTML字符串，包含Chart.js图表
        """
        if not self.daily_pnl:
            return "<p>无回测数据</p>"

        # 提取数据
        dates = [d['date'] for d in self.daily_pnl]
        equity = [d['total'] for d in self.daily_pnl]

        # 计算回撤序列
        peak = self.initial_capital
        drawdown = []
        for day in self.daily_pnl:
            if day['total'] > peak:
                peak = day['total']
            dd = (peak - day['total']) / peak if peak > 0 else 0
            drawdown.append(dd * 100)

        # 价格数据
        prices = [d['price'] for d in self.daily_pnl]

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; padding: 20px; background: #1a1a2e; color: #eee; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        h1 {{ color: #00d4ff; text-align: center; }}
        .stats {{ display: flex; justify-content: center; gap: 30px; margin: 20px 0; flex-wrap: wrap; }}
        .stat {{ background: #16213e; padding: 15px 25px; border-radius: 10px; text-align: center; }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #00d4ff; }}
        .stat-label {{ color: #888; font-size: 14px; margin-top: 5px; }}
        .positive {{ color: #00ff88; }}
        .negative {{ color: #ff4444; }}
        .chart-container {{ background: #16213e; border-radius: 12px; padding: 20px; margin: 20px 0; }}
        .chart-title {{ font-size: 16px; color: #888; margin-bottom: 15px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{title}</h1>

        <div class="stats">
            <div class="stat">
                <div class="stat-value {'positive' if equity[-1] >= self.initial_capital else 'negative'}">{equity[-1]:.2f}</div>
                <div class="stat-label">最终价值</div>
            </div>
            <div class="stat">
                <div class="stat-value {'positive' if equity[-1] >= self.initial_capital else 'negative'}">{((equity[-1]-self.initial_capital)/self.initial_capital*100):.2f}%</div>
                <div class="stat-label">总收益率</div>
            </div>
            <div class="stat">
                <div class="stat-value negative">{max(drawdown):.2f}%</div>
                <div class="stat-label">最大回撤</div>
            </div>
            <div class="stat">
                <div class="stat-value">{(sum(1 for t in self.trades if t['action']=='sell') or 0)}</div>
                <div class="stat-label">总交易次数</div>
            </div>
        </div>

        <div class="chart-container">
            <div class="chart-title">权益曲线</div>
            <canvas id="equityChart"></canvas>
        </div>

        <div class="chart-container">
            <div class="chart-title">回撤曲线</div>
            <canvas id="drawdownChart"></canvas>
        </div>

        <div class="chart-container">
            <div class="chart-title">价格走势</div>
            <canvas id="priceChart"></canvas>
        </div>
    </div>

    <script>
        const labels = {dates};
        const equityData = {equity};
        const drawdownData = {drawdown};
        const priceData = {prices};

        // 权益曲线
        new Chart(document.getElementById('equityChart'), {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: [{{
                    label: '账户权益',
                    data: equityData,
                    borderColor: '#00d4ff',
                    backgroundColor: 'rgba(0, 212, 255, 0.1)',
                    fill: true,
                    tension: 0.1
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{
                    x: {{ display: false }},
                    y: {{ ticks: {{ color: '#888' }} }}
                }}
            }}
        }});

        // 回撤曲线
        new Chart(document.getElementById('drawdownChart'), {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: [{{
                    label: '回撤',
                    data: drawdownData,
                    borderColor: '#ff4444',
                    backgroundColor: 'rgba(255, 68, 68, 0.1)',
                    fill: true,
                    tension: 0.1
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{
                    x: {{ display: false }},
                    y: {{ ticks: {{ color: '#888' }}, max: 0 }}
                }}
            }}
        }});

        // 价格走势
        new Chart(document.getElementById('priceChart'), {{
            type: 'line',
            data: {{
                labels: labels,
                datasets: [{{
                    label: '价格',
                    data: priceData,
                    borderColor: '#00ff88',
                    backgroundColor: 'rgba(0, 255, 136, 0.1)',
                    fill: false,
                    tension: 0.1
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{
                    x: {{ display: false }},
                    y: {{ ticks: {{ color: '#888' }} }}
                }}
            }}
        }});
    </script>
</body>
</html>"""
        return html

    def save_chart(self, filepath: str, title: str = "回测结果"):
        """保存图表到HTML文件"""
        html = self.generate_chart_html(title)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)


def run_backtest_demo():
    """运行示例回测"""
    import random

    # 生成模拟价格数据（震荡市）
    prices = [4.0]
    for _ in range(100):
        change = random.uniform(-0.05, 0.05)
        new_price = prices[-1] * (1 + change)
        prices.append(round(new_price, 3))

    dates = [f"2024-01-{i+1:02d}" for i in range(len(prices))]

    config = {
        'grid': {
            'levels': 10,
            'spacing': 0.05
        },
        'risk': {}
    }

    runner = BacktestRunner(config)
    result = runner.run(prices, dates)

    print("=" * 50)
    print("回测结果")
    print("=" * 50)
    print(f"初始资金: {result['initial_capital']}")
    print(f"最终价值: {result['final_value']:.2f}")
    print(f"总收益率: {result['total_return']*100:.2f}%")
    print(f"最大回撤: {result['max_drawdown']*100:.2f}%")
    print(f"总交易次数: {result['total_trades']}")
    print(f"胜率: {result['win_rate']*100:.2f}%")
    print("=" * 50)


if __name__ == '__main__':
    run_backtest_demo()