"""
AI 服务 - LLM 市场分析与策略建议
支持 MiniMax / OpenAI / DeepSeek
"""
import os
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class LLMService:
    """LLM 服务封装，支持 MiniMax / OpenAI / DeepSeek"""

    def __init__(
        self,
        api_key: str = None,
        provider: str = None,
        model: str = None,
        config: Dict[str, Any] = None
    ):
        """
        初始化 LLM 服务。

        Args:
            api_key: API 密钥
            provider: 提供商 ("minimax" / "openai" / "deepseek")
            model: 模型名称
            config: 可选，完整配置字典（会从中提取 ai_model 配置）
        """
        self.enabled = False
        self.provider = None
        self.model = None
        self.api_key = None

        # 如果传入完整 config，优先从中提取
        if config and not api_key:
            ai_cfg = config.get('ai_model', {}) if isinstance(config, dict) else config
            self.api_key = ai_cfg.get('api_key') or ai_cfg.get('api_key')
            self.provider = ai_cfg.get('provider') or ai_cfg.get('provider_name')
            self.model = ai_cfg.get('model')
        else:
            self.api_key = api_key
            self.provider = provider
            self.model = model

        # 从环境变量兜底
        if not self.api_key:
            self.api_key = os.environ.get('AI_API_KEY')

        if not self.provider:
            self.provider = os.environ.get('AI_PROVIDER', 'minimax')

        if not self.model:
            self.model = self._default_model()

        self.enabled = bool(self.api_key)

    def _default_model(self) -> str:
        """各提供商的默认模型"""
        defaults = {
            'minimax': 'MiniMax-M2.7-highspeed',
            'openai': 'gpt-4o-mini',
            'deepseek': 'deepseek-chat',
        }
        return defaults.get(self.provider, 'MiniMax-M2.7-highspeed')

    def _build_headers(self) -> Dict[str, str]:
        """构建请求头"""
        if self.provider == 'minimax':
            return {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            }
        elif self.provider == 'openai':
            return {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            }
        elif self.provider == 'deepseek':
            return {
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            }
        return {'Content-Type': 'application/json'}

    def _build_endpoint(self) -> str:
        """构建 API 端点"""
        if self.provider == 'minimax':
            return 'https://api.minimax.chat/v1/text/chatcompletion_v2'
        elif self.provider == 'openai':
            return 'https://api.openai.com/v1/chat/completions'
        elif self.provider == 'deepseek':
            return 'https://api.deepseek.com/v1/chat/completions'
        return ''

    def _build_messages(self, prompt: str) -> List[Dict[str, str]]:
        """构建消息列表"""
        return [
            {'role': 'system', 'content': '你是一位专业的量化交易策略分析师，擅长网格交易、趋势分析和风险管理。'},
            {'role': 'user', 'content': prompt},
        ]

    def _call_api(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """调用 LLM API"""
        import json
        import urllib.request

        endpoint = self._build_endpoint()
        headers = self._build_headers()

        body = {
            'model': self.model,
            'messages': self._build_messages(prompt),
            'temperature': kwargs.get('temperature', 0.3),
        }

        data = json.dumps(body).encode('utf-8')
        req = urllib.request.Request(endpoint, data=data, headers=headers, method='POST')

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                if self.provider == 'minimax':
                    choices = result.get('choices', [])
                    if choices:
                        return {'content': choices[0].get('messages', [{}])[0].get('content', '')}
                    return {'content': ''}
                elif self.provider == 'openai' or self.provider == 'deepseek':
                    choices = result.get('choices', [])
                    if choices:
                        return {'content': choices[0].get('message', {}).get('content', '')}
                    return {'content': ''}
                return {'content': ''}
        except Exception as e:
            logger.warning(f'LLM API 调用失败: {e}')
            return {'error': str(e)}

    def analyze_market(
        self,
        prices: List[float],
        dates: List[str] = None,
        indicators: Dict[str, float] = None
    ) -> Dict[str, Any]:
        """
        分析市场数据，判断是否适合做网格交易。

        Args:
            prices: 价格序列
            dates: 日期序列
            indicators: 技术指标字典（如 MA5、MA20、波动率等）

        Returns:
            {
                'enabled': True,
                'signal': 'bull'/'bear'/'sideways'/'volatile',
                'advice': str,  # 建议文本
                'grid_spacing': float,  # 建议网格间距
            }
        """
        if not self.enabled:
            return {'enabled': False, 'error': 'AI 未启用'}

        indicators = indicators or {}
        dates = dates or []

        # 构建提示词
        prompt = self._build_market_prompt(prices, dates, indicators)

        try:
            result = self._call_api(prompt)
            if 'error' in result:
                return {'enabled': False, 'error': result['error']}

            content = result.get('content', '')
            return self._parse_market_analysis(content, indicators)
        except Exception as e:
            logger.warning(f'AI 市场分析失败: {e}')
            return {'enabled': False, 'error': str(e)}

    def _build_market_prompt(
        self,
        prices: List[float],
        dates: List[str],
        indicators: Dict[str, float]
    ) -> str:
        """构建市场分析提示词"""
        current_price = prices[-1] if prices else 0
        latest_date = dates[-1] if dates else 'N/A'

        # 计算涨跌
        if len(prices) >= 5:
            change_5d = (prices[-1] / prices[-5] - 1) * 100
        else:
            change_5d = 0

        if len(prices) >= 20:
            change_20d = (prices[-1] / prices[-20] - 1) * 100
        else:
            change_20d = 0

        # 计算波动率
        if len(prices) >= 20:
            import statistics
            returns = [prices[i] / prices[i - 1] - 1 for i in range(1, len(prices))]
            volatility = statistics.stdev(returns) * 16 if len(returns) > 1 else 0
        else:
            volatility = 0

        indicator_text = '\n'.join([
            f'- {k}: {v:.2f}' for k, v in indicators.items()
        ]) or '无'

        prompt = f"""请分析以下市场数据，判断是否适合做网格交易：

【当前数据】
- 最新价格: {current_price:.4f}（日期: {latest_date}）
- 近5日涨跌: {change_5d:+.2f}%
- 近20日涨跌: {change_20d:+.2f}%
- 年化波动率: {volatility:.2f}%

【技术指标】
{indicator_text}

请分析并返回：
1. 市场判断（牛市/熊市/震荡/高波动）
2. 是否适合做网格（适合/不适合）
3. 建议的网格间距（3%/4%/5%/6%等）
4. 简要理由

请用 JSON 格式返回，包含字段：signal, suitable, grid_spacing, advice"""

        return prompt

    def _parse_market_analysis(
        self,
        content: str,
        indicators: Dict[str, float]
    ) -> Dict[str, Any]:
        """解析 AI 返回内容"""
        import json
        import re

        # 尝试提取 JSON
        json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group())
                return {
                    'enabled': True,
                    'signal': data.get('signal', 'unknown'),
                    'suitable': data.get('suitable', True),
                    'grid_spacing': float(data.get('grid_spacing', 0.05)),
                    'advice': data.get('advice', content[:200]),
                }
            except (json.JSONDecodeError, ValueError):
                pass

        # 回退：基于指标推断
        ma5 = indicators.get('MA5', 0)
        ma20 = indicators.get('MA20', 0)
        volatility = indicators.get('Volatility', indicators.get('Volatility_20D', 0))

        if ma5 > ma20 * 1.02:
            signal = 'bull'
            spacing = 0.06
        elif ma5 < ma20 * 0.98:
            signal = 'bear'
            spacing = 0.04
        else:
            signal = 'sideways'
            spacing = 0.05

        if volatility > 25:
            signal = 'volatile'
            spacing = 0.03

        return {
            'enabled': True,
            'signal': signal,
            'suitable': signal != 'volatile',
            'grid_spacing': spacing,
            'advice': content[:300] if content else '基于技术指标分析',
        }

    def recommend_strategy(
        self,
        market_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        基于市场分析推荐策略参数。
        """
        signal = market_analysis.get('signal', 'sideways')
        spacing_map = {
            'bull': 0.06,
            'bear': 0.04,
            'sideways': 0.05,
            'volatile': 0.03,
        }
        spacing = spacing_map.get(signal, 0.05)

        return {
            'grid_spacing': spacing,
            'trend_mode': 'full_grid' if signal == 'sideways' else ('buy_only' if signal == 'bear' else 'sell_only'),
            'stop_loss_pct': 0.03,
            'take_profit_pct': 0.08,
        }


# 全局单例（延迟初始化）
_llm_instance: Optional[LLMService] = None


def get_llm_service(config: Dict[str, Any] = None) -> LLMService:
    """
    获取全局 LLM 服务实例（单例模式）。

    Args:
        config: 配置字典，会缓存在全局实例中

    Returns:
        LLMService 实例
    """
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = LLMService(config=config)
    return _llm_instance
