"""
回测性能指标计算器
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Optional
import os
import yaml


class MarketAnalyzer:
    """AI市场牛熊判断分析器"""

    @staticmethod
    def analyze_market_bear_bull(
        prices: List[float],
        dates: List[str],
        trades: List[Dict] = None
    ) -> Dict:
        """
        AI分析市场牛熊状态

        Args:
            prices: 价格序列
            dates: 日期序列
            trades: 交易记录（可选）

        Returns:
            dict with market analysis results
        """
        if len(prices) < 20:
            return {
                'status': 'unknown',
                'trend': 'unknown',
                'volatility': 'unknown',
                'signal': '数据不足，无法判断',
                'advice': '至少需要20天数据进行分析'
            }

        prices_series = pd.Series(prices)
        returns = prices_series.pct_change().dropna()

        # 1. 趋势判断（使用MA均线）
        ma5 = prices_series.rolling(5).mean()
        ma20 = prices_series.rolling(20).mean()
        ma60 = prices_series.rolling(60).mean() if len(prices) >= 60 else None

        current_price = prices[-1]
        current_ma5 = ma5.iloc[-1]
        current_ma20 = ma20.iloc[-1]
        current_ma60 = ma60.iloc[-1] if ma60 is not None else None

        # 2. 趋势判断
        if current_ma60 is not None:
            if current_price > current_ma60 > current_ma20 > current_ma5:
                trend = 'strong_bull'
                trend_text = '强势上涨'
            elif current_price > current_ma20 > current_ma5:
                trend = 'bull'
                trend_text = '震荡上涨'
            elif current_price < current_ma60 < current_ma20 < current_ma5:
                trend = 'strong_bear'
                trend_text = '弱势下跌'
            elif current_price < current_ma20 < current_ma5:
                trend = 'bear'
                trend_text = '震荡下跌'
            else:
                trend = 'sideways'
                trend_text = '横盘震荡'
        else:
            if current_price > current_ma20 > current_ma5:
                trend = 'bull'
                trend_text = '上涨趋势'
            elif current_price < current_ma20 < current_ma5:
                trend = 'bear'
                trend_text = '下跌趋势'
            else:
                trend = 'sideways'
                trend_text = '横盘震荡'

        # 3. 波动率分析
        volatility_20 = returns.rolling(20).std().iloc[-1] * np.sqrt(250) * 100 if len(returns) >= 20 else returns.std() * np.sqrt(250) * 100
        if volatility_20 > 30:
            volatility = 'high'
            volatility_text = '高波动'
        elif volatility_20 > 15:
            volatility = 'medium'
            volatility_text = '中等波动'
        else:
            volatility = 'low'
            volatility_text = '低波动'

        # 4. 动量分析
        momentum_20 = (current_price / prices[-20] - 1) * 100 if len(prices) >= 20 else 0
        momentum_60 = (current_price / prices[-60] - 1) * 100 if len(prices) >= 60 else 0

        # 5. 牛熊综合判断
        if trend in ['strong_bull', 'bull'] and volatility != 'high':
            status = 'bull'
            status_text = '牛市'
        elif trend in ['strong_bear', 'bear'] and volatility != 'high':
            status = 'bear'
            status_text = '熊市'
        elif volatility == 'high':
            status = 'volatile'
            status_text = '高波动市'
        else:
            status = 'sideways'
            status_text = '震荡市'

        # 6. 生成AI建议
        advice_parts = []

        # 网格策略适配建议
        if status == 'bull':
            advice_parts.append('当前牛市环境，建议：适当放大网格间距(6%-8%)，减少交易频率，让利润奔跑')
        elif status == 'bear':
            advice_parts.append('当前熊市环境，建议：缩小网格间距(3%-4%)，降低单格仓位，严格止损')
        elif status == 'sideways':
            advice_parts.append('当前震荡市，网格策略最佳适用场景，建议：保持现有参数(5%)')
        else:
            advice_parts.append('高波动市场，建议：密切关注仓位变化，准备临时调仓')

        # 风险提示
        if volatility == 'high':
            advice_parts.append('⚠️ 注意波动率较高，需做好极端行情应对准备')

        if abs(momentum_20) > 15:
            advice_parts.append(f'⚠️ 短期动量{momentum_20:.1f}%较大，趋势可能延续')

        # 交易信号
        signal = f"{status_text} | {trend_text} | {volatility_text}"
        advice = '\n'.join(advice_parts)

        return {
            'status': status,
            'trend': trend,
            'volatility': volatility,
            'signal': signal,
            'advice': advice,
            'details': {
                'momentum_20': round(momentum_20, 2),
                'momentum_60': round(momentum_60, 2) if momentum_60 else 0,
                'volatility_annual': round(volatility_20, 2),
                'ma5': round(current_ma5, 3) if not np.isnan(current_ma5) else None,
                'ma20': round(current_ma20, 3) if not np.isnan(current_ma20) else None,
                'ma60': round(current_ma60, 3) if current_ma60 is not None and not np.isnan(current_ma60) else None,
            }
        }


class MetricsCalculator:
    """计算回测性能指标"""

    @staticmethod
    def calculate(trades: List[Dict], equity_curve: List[float], initial_capital: float) -> Dict:
        """
        计算所有性能指标

        Args:
            trades: 交易记录列表 [{date, action, price, quantity, profit}]
            equity_curve: 每日权益列表 [float]
            initial_capital: 初始资金

        Returns:
            dict with all performance metrics
        """
        if not equity_curve or len(equity_curve) < 2:
            return MetricsCalculator._empty_metrics()

        equity_series = pd.Series(equity_curve)
        returns = equity_series.pct_change().dropna()

        # 基本指标
        final_capital = equity_curve[-1]
        total_return = (final_capital - initial_capital) / initial_capital * 100

        # 年化收益率
        trading_days = len(equity_curve)
        years = trading_days / 250  # 假设一年250个交易日
        annualized_return = ((final_capital / initial_capital) ** (1 / years) - 1) * 100 if years > 0 else 0

        # 最大回撤
        peak = equity_series.expanding(min_periods=1).max()
        drawdown = (equity_series - peak) / peak * 100
        max_drawdown = abs(drawdown.min())
        max_drawdown_capital = abs(drawdown.min() / 100 * initial_capital)

        # 夏普比率 (假设无风险利率3%)
        risk_free_rate = 3.0
        if len(returns) > 1 and returns.std() != 0:
            daily_sharpe = (returns.mean() * 100 - risk_free_rate / 250) / (returns.std() * 100)
            sharpe_ratio = daily_sharpe * np.sqrt(250)
        else:
            sharpe_ratio = 0

        # 交易统计
        buy_trades = [t for t in trades if t.get('action') == 'buy']
        sell_trades = [t for t in trades if t.get('action') == 'sell']
        total_trades = len(trades)

        # 胜率计算 (盈利的卖出次数 / 总卖出次数)
        winning_trades = [t for t in trades if t.get('profit', 0) > 0]
        win_rate = len(winning_trades) / total_trades * 100 if total_trades > 0 else 0

        # 盈利因子
        total_profit = sum(t.get('profit', 0) for t in trades if t.get('profit', 0) > 0)
        total_loss = abs(sum(t.get('profit', 0) for t in trades if t.get('profit', 0) < 0))
        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf') if total_profit > 0 else 0

        # 每笔平均盈利
        avg_profit = (total_profit - total_loss) / total_trades if total_trades > 0 else 0

        return {
            'total_return': round(total_return, 2),
            'annualized_return': round(annualized_return, 2),
            'max_drawdown': round(max_drawdown, 2),
            'max_drawdown_capital': round(max_drawdown_capital, 2),
            'sharpe_ratio': round(sharpe_ratio, 2),
            'win_rate': round(win_rate, 2),
            'total_trades': total_trades,
            'winning_trades': len(winning_trades),
            'losing_trades': total_trades - len(winning_trades),
            'profit_factor': round(profit_factor, 2) if profit_factor != float('inf') else float('inf'),
            'avg_profit_per_trade': round(avg_profit, 2),
            'final_capital': round(final_capital, 2),
            'total_profit': round(total_profit, 2),
            'total_loss': round(total_loss, 2),
            'trading_days': trading_days,
        }

    @staticmethod
    def calculate_monthly_returns(trades: List[Dict], equity_curve: List[float], dates: List[str]) -> Dict[str, float]:
        """
        计算月度收益

        Args:
            trades: 交易记录列表
            equity_curve: 每日权益列表
            dates: 日期列表

        Returns:
            dict: {YYYY-MM: return_pct}
        """
        if not equity_curve or len(equity_curve) < 2:
            return {}

        # 创建日期索引
        df = pd.DataFrame({'equity': equity_curve}, index=pd.to_datetime(dates))
        monthly = df['equity'].resample('ME').last()

        monthly_returns = {}
        for i in range(1, len(monthly)):
            prev = monthly.iloc[i - 1]
            curr = monthly.iloc[i]
            if prev > 0:
                month_key = monthly.index[i].strftime('%Y-%m')
                monthly_returns[month_key] = round((curr - prev) / prev * 100, 2)

        return monthly_returns

    @staticmethod
    def calculate_drawdown_series(equity_curve: List[float]) -> List[float]:
        """计算回撤序列"""
        if not equity_curve:
            return []

        equity_series = pd.Series(equity_curve)
        peak = equity_series.expanding(min_periods=1).max()
        drawdown = (equity_series - peak) / peak * 100
        return drawdown.tolist()

    @staticmethod
    def _empty_metrics() -> Dict:
        """返回空指标"""
        return {
            'total_return': 0,
            'annualized_return': 0,
            'max_drawdown': 0,
            'max_drawdown_capital': 0,
            'sharpe_ratio': 0,
            'win_rate': 0,
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'profit_factor': 0,
            'avg_profit_per_trade': 0,
            'final_capital': 0,
            'total_profit': 0,
            'total_loss': 0,
            'trading_days': 0,
        }

    @staticmethod
    def get_ai_market_analysis(prices: List[float], dates: List[str], trades: List[Dict] = None) -> Dict:
        """
        获取AI市场分析（使用MiniMax LLM）

        Args:
            prices: 价格序列
            dates: 日期序列
            trades: 交易记录

        Returns:
            dict with AI analysis results
        """
        try:
            # 动态导入避免循环依赖
            from utils.llm_service import get_llm_service

            # 加载配置获取API key
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                'config.yaml'
            )
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            llm = get_llm_service(config)

            if not llm.enabled:
                return {
                    'ai_enabled': False,
                    'signal': '未配置AI',
                    'advice': '请在设置中配置MiniMax API密钥'
                }

            # 计算技术指标
            prices_series = pd.Series(prices)
            indicators = {}

            if len(prices) >= 5:
                indicators['MA5'] = prices_series.rolling(5).mean().iloc[-1]
            if len(prices) >= 20:
                indicators['MA20'] = prices_series.rolling(20).mean().iloc[-1]
            if len(prices) >= 60:
                indicators['MA60'] = prices_series.rolling(60).mean().iloc[-1]

            # 波动率
            returns = prices_series.pct_change().dropna()
            if len(returns) >= 20:
                indicators['Volatility_20D'] = returns.rolling(20).std().iloc[-1] * np.sqrt(250) * 100

            # 动量
            if len(prices) >= 20:
                indicators['Momentum_20D'] = (prices[-1] / prices[-20] - 1) * 100

            result = llm.analyze_market(prices, dates, indicators)
            # 统一key名称
            if 'enabled' in result:
                result['ai_enabled'] = result.pop('enabled')
            return result

        except ImportError:
            return {
                'ai_enabled': False,
                'error': 'LLM模块未安装'
            }
        except Exception as e:
            return {
                'ai_enabled': False,
                'error': str(e)
            }
