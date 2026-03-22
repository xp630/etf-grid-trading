"""
ETF网格交易系统 - Streamlit Web监控面板
"""
import streamlit as st
import requests
import yaml
import os
import subprocess
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# 导入回测模块（全局，避免条件导入问题）
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from engines.backtest import BacktestEngine
from strategies.trend_grid import TrendGridStrategy
from strategies.ma_crossover import MACrossoverStrategy


def analyze_market_trend(prices: pd.Series) -> dict:
    """
    分析市场趋势（基于技术指标规则）

    判断逻辑：
    1. 计算短期(5日)和长期(20日)均线
    2. 计算近期价格斜率(6个月)
    3. 综合判断：牛市/熊市/震荡市

    Returns:
        dict: {
            'trend': 'bull' | 'bear' | 'sideways',
            'confidence': 0.0-1.0,
            'slope': float,  # 价格斜率
            'ma5': float,
            'ma20': float,
            'reason': str
        }
    """
    if len(prices) < 20:
        return {
            'trend': 'unknown',
            'confidence': 0.0,
            'slope': 0.0,
            'ma5': 0.0,
            'ma20': 0.0,
            'reason': '数据不足'
        }

    current_price = prices.iloc[-1]
    ma5 = prices.iloc[-5:].mean()
    ma20 = prices.iloc[-20:].mean()

    # 计算6个月斜率（假设有足够数据）
    lookback = min(120, len(prices))  # 最多看6个月
    if lookback >= 60:
        price_ago = prices.iloc[-lookback]
        slope = (current_price - price_ago) / price_ago
    else:
        slope = 0.0

    # 综合判断
    trend = 'sideways'
    confidence = 0.5
    reason = []

    # 1. 均线位置判断
    if current_price > ma20:
        ma_signal = '多头'
        confidence += 0.1
    else:
        ma_signal = '空头'
        confidence -= 0.1

    # 2. MA5和MA20关系
    if ma5 > ma20:
        ma_cross = '金叉区域'
        confidence += 0.15
    else:
        ma_cross = '死叉区域'
        confidence -= 0.15

    # 3. 斜率判断
    if slope > 0.05:  # 涨超5%
        trend = 'bull'
        confidence = min(confidence + 0.2, 0.95)
        reason.append(f'价格上涨{slope*100:.1f}%，趋势向上')
    elif slope < -0.05:  # 跌超5%
        trend = 'bear'
        confidence = min(confidence + 0.2, 0.95)
        reason.append(f'价格下跌{abs(slope)*100:.1f}%，趋势向下')
    else:
        trend = 'sideways'
        reason.append(f'价格基本持平({slope*100:+.1f}%)')

    # 4. 综合判断
    if trend == 'sideways' and ma_signal == '多头' and ma_cross == '金叉区域':
        if slope > 0:
            trend = 'bull'
            confidence = 0.7
            reason.append('但均线多头，可能进入上涨趋势')
    elif trend == 'sideways' and ma_signal == '空头' and ma_cross == '死叉区域':
        if slope < 0:
            trend = 'bear'
            confidence = 0.7
            reason.append('但均线空头，可能进入下跌趋势')

    # 翻译显示名称
    trend_names = {
        'bull': '牛市 🐂',
        'bear': '熊市 🐻',
        'sideways': '震荡市 ↔️',
        'unknown': '未知 ❓'
    }

    return {
        'trend': trend,
        'trend_name': trend_names.get(trend, trend),
        'confidence': confidence,
        'slope': slope,
        'ma5': ma5,
        'ma20': ma20,
        'current_price': current_price,
        'reason': '；'.join(reason) if reason else '综合判断',
        'ma_signal': ma_signal,
        'ma_cross': ma_cross
    }


def restart_trading_system():
    """重启交易系统"""
    try:
        # 先调用关闭API
        post_api('http://127.0.0.1:5000/api/shutdown', {})

        import time
        # 等待进程退出
        for _ in range(10):
            time.sleep(1)
            result = subprocess.run(['tasklist'], stdout=subprocess.PIPE, text=True)
            if 'api_server.py' not in result.stdout:
                break

        # 启动新的交易系统
        subprocess.Popen(['python', 'web/api_server.py'],
                       cwd=os.path.dirname(os.path.dirname(__file__)))
        return True, "交易系统已重启!"
    except Exception as e:
        return False, str(e)

st.set_page_config(
    page_title="ETF网格交易监控",
    layout="wide",
    page_icon="📈",
    menu_items=None
)

# 隐藏Streamlit顶部元素
st.markdown("""
<style>
    .stApp > header {
        background-color: transparent;
    }
    .stApp > .main > div:has(> .stTabs) {
        margin-top: -60px;
    }
    section[data-testid="stHeader"] {
        display: none;
    }
    div[data-testid="stToolbar"] {
        display: none;
    }
    .stAppHeader {
        display: none !important;
    }
</style>
""", unsafe_allow_html=True)

# 深海蓝主题 - 专业交易风格
st.markdown("""
<style>
    /* 主背景 - 深蓝色 */
    .stApp { background-color: #0d1421; }

    /* 侧边栏 */
    .stSidebar > div:first-child { background: #111827; }

    /* 标题 */
    h1, h2, h3 { color: #e2e8f0 !important; font-weight: 600; }

    /* 指标值 - 高对比度 */
    [data-testid="stMetricValue"] {
        color: #f1f5f9 !important;
        font-size: 32px !important;
        font-weight: 700 !important;
    }
    [data-testid="stMetricLabel"] { color: #64748b !important; font-size: 14px !important; }
    [data-testid="stMetricDelta"] { color: #94a3b8 !important; }

    /* 标签页 */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; background: #111827; border-radius: 12px; padding: 8px; }
    .stTabs [data-baseweb="tab"] {
        color: #64748b;
        font-weight: 500;
        padding: 10px 24px;
        border-radius: 8px;
    }
    .stTabs [data-baseweb="tab"]:hover { color: #e2e8f0; background: #1e293b; }
    .stTabs [aria-selected="true"] { background: #1e3a5f !important; color: #e2e8f0 !important; font-weight: 600; }

    /* 卡片背景 */
    [data-testid="stHorizontalBlock"] > div { background: #111827; border-radius: 16px; padding: 20px; border: 1px solid #1e293b; }

    /* 表单 */
    .stForm { background: #111827; border-radius: 16px; padding: 24px; border: 1px solid #1e293b; }
    .stTextInput > div > div > input, .stPassword > div > div > input {
        background: #0d1421;
        color: #ffffff !important;
        border: 1px solid #1e293b;
        border-radius: 10px;
        padding: 12px;
    }
    .stTextInput > div > div > input::placeholder {
        color: #475569 !important;
    }
    .stTextInput > div > div > input:focus, .stPassword > div > div > input:focus {
        border-color: #3b82f6;
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.3);
    }

    /* 下拉框 */
    .stSelectbox > div > div {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%) !important;
        color: #ffffff !important;
        border: 1px solid #1e293b !important;
        border-radius: 10px;
    }
    .stSelectbox [data-baseweb="select"] > div {
        background: transparent !important;
        color: #ffffff !important;
    }
    .stSelectbox [data-baseweb="popover"] {
        background: #111827 !important;
        color: #ffffff !important;
    }
    .stSelectbox [data-baseweb="menu"] {
        background: #111827 !important;
        color: #ffffff !important;
    }
    .stSelectbox [data-baseweb="option"] {
        background: #111827 !important;
        color: #ffffff !important;
    }
    .stSelectbox [data-baseweb="option"]:hover {
        background: #1e293b !important;
    }

    /* 按钮 */
    .stButton > button, .stFormSubmitButton > button {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%) !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 10px;
        padding: 12px 28px;
        font-weight: 600;
        font-size: 15px;
    }
    .stButton > button:hover, .stFormSubmitButton > button:hover {
        background: linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%) !important;
    }
    .stButton > button:active, .stFormSubmitButton > button:active {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
    }

    /* 进度条 */
    .stProgress > div > div > div > div { background: linear-gradient(90deg, #3b82f6, #60a5fa) !important; }

    /* 分隔线 */
    hr { border-color: #1e293b !important; margin: 24px 0 !important; }

    /* 成功/警告/错误 */
    .stSuccess { background: #022c22; border: 1px solid #059669; border-radius: 10px; color: #d1fae5 !important; }
    .stSuccess p, .stSuccess span { color: #d1fae5 !important; }
    .stWarning { background: #451a03; border: 1px solid #d97706; border-radius: 10px; color: #fef3c7 !important; }
    .stWarning p, .stWarning span { color: #fef3c7 !important; }
    .stError { background: #450a0a; border: 1px solid #dc2626; border-radius: 10px; color: #fee2e2 !important; }
    .stError p, .stError span { color: #fee2e2 !important; }
    .stInfo { background: #0c1929; border: 1px solid #3b82f6; border-radius: 10px; color: #bfdbfe !important; }
    .stInfo p, .stInfo span { color: #bfdbfe !important; }

    /* 文字 */
    p, span, div { color: #94a3b8; }
    .stCaption { color: #475569 !important; }

    /* 日志显示 */
    .log-container { background: #020617; border-radius: 8px; padding: 15px; font-family: 'Consolas', 'Monaco', monospace; font-size: 13px; }
    .log-error { color: #f87171; background: transparent; }
    .log-warning { color: #fbbf24; background: transparent; }
    .log-info { color: #60a5fa; background: transparent; }
    .log-debug { color: #6b7280; background: transparent; }
</style>
""", unsafe_allow_html=True)

# 加载配置
@st.cache_data
def load_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def load_settings():
    """从API加载配置（不脱敏）"""
    return get_api('http://127.0.0.1:5000/api/config/settings')

def get_api(url):
    try:
        r = requests.get(url, timeout=5)
        return r.json()
    except:
        return None

def post_api(url, data):
    try:
        r = requests.post(url, json=data, timeout=5)
        return r.json()
    except:
        return None

def put_api(url, data):
    try:
        r = requests.put(url, json=data, timeout=5)
        return r.json()
    except:
        return None

# ========== 侧边栏 ==========
with st.sidebar:
    st.markdown("### 📈 ETF网格交易")
    st.divider()
    st.markdown("**沪深300ETF**")
    st.markdown("**510300**")
    st.divider()
    st.markdown("网格间距: 5%")
    st.markdown("网格档位: 10档")
    st.markdown("每格金额: ¥500")
    st.divider()
    st.caption("交易API")
    st.caption("127.0.0.1:5000")

# ========== 主内容 ==========
page = st.radio("", ["📊 监控面板", "📊 市场分析", "📈 回测分析", "⚙️ 设置", "📋 日志"], horizontal=True, label_visibility="collapsed")

# ========== 监控面板 ==========
if page == "📊 监控面板":
    st.title("📊 监控面板")

    status_data = get_api('http://127.0.0.1:5000/api/status')
    risk_data = get_api('http://127.0.0.1:5000/api/risk/status')
    grid_data = get_api('http://127.0.0.1:5000/api/grid/status')

    # 第一行 - 核心指标
    col1, col2, col3, col4 = st.columns(4)

    if status_data and status_data.get('success'):
        d = status_data['data']
        with col1:
            st.metric("当前价格", f"¥{d['current_price']:.3f}")
        with col2:
            pnl = d['daily_pnl']
            delta_color = "normal" if pnl >= 0 else "inverse"
            st.metric("当日盈亏", f"¥{pnl:.2f}", delta=f"{pnl:+.2f}")
        with col3:
            st.metric("总资产", f"¥{d['total_assets']:.2f}")
        with col4:
            st.metric("持仓市值", f"¥{d['position_value']:.2f}")
    else:
        st.error("无法获取数据，请确保交易系统正在运行")

    st.divider()

    # 第二行 - 风险状态
    if risk_data and risk_data.get('success'):
        r = risk_data['data']
        st.subheader("🛡️ 风险状态")

        risk_col1, risk_col2, risk_col3, risk_col4 = st.columns(4)

        with risk_col1:
            st.markdown("**日亏损限额**")
            st.markdown(f"### ¥{r.get('daily_limit', 100):.2f}")
            progress_val = min(r.get('daily_remaining', 100) / r.get('daily_limit', 100), 1.0) if r.get('daily_limit') else 1.0
            st.progress(progress_val)

        with risk_col2:
            st.markdown("**可用亏损**")
            remaining = r.get('daily_remaining', 0)
            if remaining > 50:
                st.markdown(f"### :green[¥{remaining:.2f}]")
            elif remaining > 20:
                st.markdown(f"### :orange[¥{remaining:.2f}]")
            else:
                st.markdown(f"### :red[¥{remaining:.2f}]")

        with risk_col3:
            st.markdown("**止损线**")
            st.markdown(f"### ¥{r.get('stop_loss_line', 9000):.2f}")

        with risk_col4:
            st.markdown("**风险状态**")
            status = r.get('status', 'unknown')
            if status == 'safe':
                st.success("✅ 安全")
            elif status == 'warning':
                st.warning("⚠️ 警告")
            else:
                st.error("🚨 危险")

    st.divider()

    # 第三行 - 网格状态
    if grid_data and grid_data.get('success'):
        g = grid_data['data']
        st.subheader(f"📐 网格状态  |  基准价 ¥{g['baseline_price']:.3f}")

        levels = g['levels']
        num_levels = len(levels)
        cols = st.columns(min(num_levels, 10))
        for i, level in enumerate(levels[:10]):
                l = level
                if l['is_current']:
                    st.markdown(f"**◉**")
                    st.markdown(f":green[{l['price']:.3f}]")
                elif l['has_position']:
                    st.markdown(f"📈")
                    st.markdown(f":green[{l['price']:.3f}]")
                elif l['is_below']:
                    st.markdown(f"⬆️")
                    st.markdown(f"{l['price']:.3f}")
                else:
                    st.markdown(f"⬇️")
                    st.markdown(f"{l['price']:.3f}")

    st.divider()

    # 第四行 - 持仓和交易
    left_col, right_col = st.columns(2)

    with left_col:
        st.subheader("💼 当前持仓")
        if status_data and status_data.get('success'):
            positions = status_data['data'].get('positions', [])
            if positions:
                for p in positions:
                    pnl_str = f"+{p['pnl']:.2f}" if p['pnl'] >= 0 else f"{p['pnl']:.2f}"
                    pnl_color = "green" if p['pnl'] >= 0 else "red"
                    st.markdown(f"**{p['symbol']}**  {p['quantity']}股 @ ¥{p['avg_price']:.3f}")
                    st.markdown(f"市值 ¥{p['current_value']:.2f}  |  盈亏 :{pnl_color}[{pnl_str}元]")
                    st.markdown("")
            else:
                st.info("📭 当前无持仓")

    with right_col:
        st.subheader("📜 最近交易")
        if status_data and status_data.get('success'):
            trades = status_data['data'].get('recent_trades', [])
            if trades:
                for t in trades[:5]:
                    action = "🟢 买入" if t['action'] == 'buy' else "🔴 卖出"
                    st.markdown(f"{action} **{t['symbol']}** {t['quantity']}股 @ ¥{t['price']:.3f}")
                    st.caption(f"⏰ {t['timestamp']}")
            else:
                st.info("📭 今日无交易")

    st.divider()
    st.caption(f"最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ========== 设置页面 ==========
elif page == "⚙️ 设置":
    st.title("⚙️ 系统设置")
    settings = load_settings()
    config = settings.get('data', {}) if settings else {}

    st.subheader("📱 微信通知")
    with st.form("server_config"):
        server酱_key = st.text_input(
            "Server酱 Key",
            value=config.get('notification', {}).get('server酱_key', ''),
            type='password',
            placeholder="输入你的Server酱SCKEY"
        )
        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("保存", use_container_width=True)
        with col2:
            test_clicked = st.form_submit_button("🧪 发送测试", use_container_width=True)
        if submitted:
            result = put_api('http://127.0.0.1:5000/api/config/notification', {'server酱_key': server酱_key})
            if result and result.get('success'):
                st.success("保存成功!")
            else:
                st.error("保存失败: 无法连接到交易系统")
        if test_clicked:
            result = post_api('http://127.0.0.1:5000/api/config/notification/test', {})
            if result and result.get('success'):
                st.success("发送成功，请检查微信！")
            else:
                st.error(f"发送失败: {result.get('error', '未知错误') if result else '无法连接'}")

    st.divider()

    st.subheader("🤖 AI模型配置")
    ai_config = config.get('ai_model', {})
    with st.form("ai_config"):
        col1, col2 = st.columns([1, 1])
        with col1:
            provider = st.selectbox(
                "AI提供商",
                options=["minimax", "openai", "deepseek"],
                index=["minimax", "openai", "deepseek"].index(ai_config.get('provider', 'minimax')),
                format_func=lambda x: {"minimax": "MiniMax", "openai": "OpenAI GPT", "deepseek": "DeepSeek"}[x]
            )
        with col2:
            model_options = {
                "minimax": ["MiniMax-M2.7-highspeed", "MiniMax-M2.7"],
                "openai": ["gpt-4o-mini", "gpt-4o"],
                "deepseek": ["deepseek-chat", "deepseek-coder"]
            }
            default_model = "MiniMax-M2.7-highspeed"
            current_model = ai_config.get('model', default_model)
            available_models = model_options.get(provider, [default_model])
            model_index = available_models.index(current_model) if current_model in available_models else 0
            model = st.selectbox(
                "模型",
                options=available_models,
                index=model_index
            )

        api_key = st.text_input(
            "API Key",
            value=ai_config.get('api_key', ''),
            type='password',
            placeholder="输入API密钥"
        )

        col1, col2 = st.columns([1, 4])
        with col1:
            test_clicked = st.form_submit_button("🧪 测试连接", use_container_width=True)
        with col2:
            submitted = st.form_submit_button("💾 保存", use_container_width=True)

        if submitted:
            result = put_api('http://127.0.0.1:5000/api/config/ai_model', {
                'provider': provider,
                'model': model,
                'api_key': api_key
            })
            if result and result.get('success'):
                st.success("保存成功!")
            else:
                st.error("保存失败")

        if test_clicked and api_key:
            with st.spinner("测试AI连接..."):
                try:
                    from utils.llm_service import LLMService
                    llm = LLMService(api_key=api_key, provider=provider, model=model)
                    if llm.enabled:
                        st.success("✅ API连接正常!")
                    else:
                        st.error("❌ API密钥无效")
                except Exception as e:
                    st.error(f"连接失败: {e}")
        elif test_clicked and not api_key:
            st.warning("请先输入API密钥")

    st.divider()

    st.subheader("📡 市场数据源")
    data_source_config = config.get('data_source', {})
    current_source = data_source_config.get('index', 'auto')
    with st.form("data_source_config"):
        st.info("选择市场指数数据的来源：优先使用有数据的源，自动模式下按 聚宽 → AkShare → Baostock 顺序尝试")
        index_source = st.selectbox(
            "指数数据源",
            options=["auto", "joinquant", "akshare", "baostock", "mock"],
            index=["auto", "joinquant", "akshare", "baostock", "mock"].index(current_source),
            format_func=lambda x: {
                "auto": "自动选择（推荐）",
                "joinquant": "聚宽（需要账号）",
                "akshare": "AkShare（免费，偶有不稳定）",
                "baostock": "Baostock（免费，稳定）",
                "mock": "模拟数据（仅测试用）"
            }[x]
        )
        submitted = st.form_submit_button("💾 保存", use_container_width=True)
        if submitted:
            result = put_api('http://127.0.0.1:5000/api/config/data_source', {'index': index_source})
            if result and result.get('success'):
                st.success("保存成功!")
            else:
                st.error("保存失败")

    st.divider()

    st.subheader("🔐 聚宽账号")
    creds = config.get('credentials', {})
    with st.form("jq_config"):
        col1, col2 = st.columns(2)
        with col1:
            username = st.text_input("用户名", value=creds.get('username', ''))
        with col2:
            password = st.text_input("密码", value=creds.get('password', ''), type='password')
        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("保存", use_container_width=True)
        with col2:
            test_clicked = st.form_submit_button("🧪 测试认证", use_container_width=True)
        if submitted:
            result = put_api('http://127.0.0.1:5000/api/config/credentials', {'username': username, 'password': password})
            if result and result.get('success'):
                st.success("保存成功!")
            else:
                st.error("保存失败: 无法连接到交易系统")
        if test_clicked:
            result = post_api('http://127.0.0.1:5000/api/config/credentials/test', {})
            if result and result.get('success'):
                st.success("认证成功！")
            else:
                st.error(f"认证失败: {result.get('error', '未知错误') if result else '无法连接'}")

    st.divider()

    st.subheader("📊 交易策略")
    strategy_info = get_api('http://127.0.0.1:5000/api/strategy')
    if strategy_info and strategy_info.get('success'):
        current = strategy_info['data']['name']
        available = strategy_info['data'].get('available', [])

        # AI策略推荐
        st.markdown("**🤖 AI策略推荐**")
        try:
            # 获取市场数据
            trend_data = get_api(f'http://127.0.0.1:5000/api/index/trend?code=000300.XSHG&days=60')
            if trend_data and trend_data.get('success'):
                td = trend_data['data']
                prices = td.get('prices', [])
                ma5 = td.get('ma5', [])
                ma20 = td.get('ma20', [])

                if prices and ma5 and ma20:
                    current_price = prices[-1]
                    m5 = ma5[-1] if not pd.isna(ma5[-1]) else 0
                    m20 = ma20[-1] if not pd.isna(ma20[-1]) else 0

                    # 基于均线判断市场状态
                    if m5 > m20 > 0 and current_price > m5:
                        ai_recommend = "📈 **趋势上涨** → 建议使用 `趋势网格策略`，可跟上上涨趋势"
                        ai_emoji = "🐂"
                    elif m5 < m20 and current_price < m20:
                        ai_recommend = "📉 **趋势下跌** → 建议使用 `原始网格策略`，高抛低吸更安全"
                        ai_emoji = "🐻"
                    else:
                        ai_recommend = "↔️ **震荡市场** → 建议使用 `趋势网格策略`，自动适应市场变化"
                        ai_emoji = "📊"

                    st.info(f"{ai_emoji} {ai_recommend}")
            else:
                st.info("💡 无法获取市场数据，请在设置中配置AI模型获取推荐")
        except Exception as e:
            st.info("💡 配置AI后可根据市场自动推荐策略")

        st.divider()

        strategy_options = {
            'grid': '原始网格策略（无趋势过滤）',
            'trend_grid': '趋势网格策略（MA20过滤 + 止损止盈）',
            'ma_crossover': '均线交叉策略（金叉买死叉卖）'
        }

        selected = st.selectbox(
            "选择策略",
            options=available,
            index=available.index(current) if current in available else 0,
            format_func=lambda x: strategy_options.get(x, x),
            help="切换策略后立即生效"
        )

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 切换策略", use_container_width=True):
                result = put_api('http://127.0.0.1:5000/api/strategy', {'name': selected})
                if result and result.get('success'):
                    st.success(f"已切换为: {strategy_options.get(selected, selected)}")
                    st.rerun()
                else:
                    st.error(f"切换失败: {result.get('error', '未知错误') if result else '无法连接'}")

        with col2:
            st.info(f"当前: {strategy_options.get(current, current)}")

        # 显示策略说明
        if selected == 'trend_grid':
            st.success("""
            **趋势网格策略特点:**
            - MA20趋势判断，三种模式自动切换
            - 止损3% / 止盈8% / 移动止损2%
            - 自动计算买入单位（50%持仓）
            """)
        else:
            st.info("""
            **原始网格策略特点:**
            - 纯网格交易，无趋势过滤
            - 价格跌破档位买入，涨破档位卖出
            - 适合震荡市
            """)
    else:
        st.error("无法获取策略信息，请确保交易系统正在运行")

    st.divider()

    st.subheader("🔄 系统操作")
    st.warning("💡 仅限非交易时间或交易结束后使用重启")

    if st.button("🔄 重启交易系统", use_container_width=True):
        with st.spinner("正在重启..."):
            success, msg = restart_trading_system()
            if success:
                st.success(msg)
            else:
                st.error(f"重启失败: {msg}")

    st.divider()

    st.subheader("📋 当前配置")
    grid_cfg = config.get('grid', {})
    risk_cfg = config.get('risk', {})

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("网格档位", f"{grid_cfg.get('levels', 10)}档")
    with col2:
        st.metric("网格间距", f"{grid_cfg.get('spacing', 0.05)*100:.1f}%")
    with col3:
        st.metric("每格金额", f"¥{grid_cfg.get('unit_size', 500)}")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("日亏损熔断", f"¥{risk_cfg.get('max_daily_loss', 100)}")
    with col2:
        st.metric("最大持仓", f"¥{risk_cfg.get('max_position', 5000)}")
    with col3:
        st.metric("总止损线", f"¥{risk_cfg.get('total_stop_loss', 9000)}")

    st.warning("配置修改需要重启交易系统生效")

# ========== 市场分析页面 ==========
elif page == "📊 市场分析":
    st.title("📊 市场分析")

    # 预设指数列表
    indices_list = {
        '000001.XSHG': '上证指数',
        '399001.XSHE': '深证成指',
        '399006.XSHE': '创业板指',
        '000688.XSHG': '科创50',
        '000300.XSHG': '沪深300',
        '000016.XSHG': '上证50',
        '000905.XSHG': '中证500'
    }

    # 选项卡：预设指数 vs 手动输入
    tab1, tab2 = st.tabs(["📈 预设指数", "🔍 手动输入"])

    with tab1:
        selected_index = st.selectbox(
            "选择指数",
            options=list(indices_list.keys()),
            index=4,
            format_func=lambda x: indices_list.get(x, x),
            key="index_select"
        )
        trend_data = get_api(f'http://127.0.0.1:5000/api/index/trend?code={selected_index}&days=120')
        source_label = "指数"

    with tab2:
        stock_code = st.text_input(
            "输入股票代码",
            value="",
            placeholder="如：600000（浦发银行）、000001（平安银行）",
            key="stock_input"
        )
        days_input = st.slider("分析天数", 20, 250, 120, key="stock_days")
        if stock_code:
            trend_data = get_api(f'http://127.0.0.1:5000/api/stock/trend?code={stock_code}&days={days_input}')
            source_label = "股票"
        else:
            trend_data = None
            st.info("请输入股票代码进行走势分析")

    if trend_data and trend_data.get('success'):
        td = trend_data['data']
        # 获取名称：如果是手动输入股票，显示股票代码；否则显示指数名称
        if source_label == "股票" and stock_code:
            item_name = stock_code
        else:
            item_name = td.get('name', selected_index if 'selected_index' in dir() else '')
        dates = td.get('dates', [])
        prices = td.get('prices', [])
        ma5 = td.get('ma5', [])
        ma20 = td.get('ma20', [])
        ma60 = td.get('ma60', [])

        # 当前值
        current_price_idx = prices[-1] if prices else 0
        current_ma5 = ma5[-1] if ma5 and not pd.isna(ma5[-1]) else None
        current_ma20 = ma20[-1] if ma20 and not pd.isna(ma20[-1]) else None
        current_ma60 = ma60[-1] if ma60 and not pd.isna(ma60[-1]) else None

        # 显示均线指标
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(f"{item_name}", f"{current_price_idx:.2f}")
        with col2:
            ma5_val = f"{current_ma5:.2f}" if current_ma5 else "N/A"
            st.metric("MA5", ma5_val)
        with col3:
            ma20_val = f"{current_ma20:.2f}" if current_ma20 else "N/A"
            st.metric("MA20", ma20_val)
        with col4:
            ma60_val = f"{current_ma60:.2f}" if current_ma60 else "N/A"
            st.metric("MA60", ma60_val)

        # 均线趋势图表
        if dates and prices:
            import pandas as pd
            chart_df = pd.DataFrame({
                '日期': pd.to_datetime(dates),
                '价格': prices,
                'MA5': ma5,
                'MA20': ma20,
                'MA60': ma60
            })
            chart_df = chart_df.set_index('日期')

            # 趋势判断
            trend_status = "震荡"
            if current_ma5 and current_ma20 and current_ma60:
                if current_price_idx > current_ma5 > current_ma20 > current_ma60:
                    trend_status = "强势上涨 🐂"
                elif current_price_idx > current_ma20 > current_ma5:
                    trend_status = "上涨 📈"
                elif current_price_idx < current_ma60 < current_ma20 < current_ma5:
                    trend_status = "弱势下跌 🐻"
                elif current_price_idx < current_ma20 < current_ma5:
                    trend_status = "下跌 📉"
                else:
                    trend_status = "横盘震荡 ↔️"

            st.info(f"**{item_name}** 当前趋势: **{trend_status}**")

            # 绘制均线图
            st.line_chart(chart_df[['价格', 'MA5', 'MA20', 'MA60']], height=300)

        # 个股走势分析（替代AI策略推荐）
        st.divider()
        st.markdown("### 📊 走势分析")

        if prices and len(prices) >= 5:
            # 计算涨跌
            price_change = prices[-1] - prices[0]
            price_change_pct = (price_change / prices[0]) * 100 if prices[0] > 0 else 0

            # 近期涨跌
            recent_change = 0
            if len(prices) >= 5:
                recent_change = (prices[-1] - prices[-5]) / prices[-5] * 100

            # 趋势判断
            col1, col2, col3 = st.columns(3)
            with col1:
                change_color = "🔴" if price_change < 0 else "🟢"
                st.metric("区间涨跌", f"{change_color} {price_change_pct:+.2f}%")
            with col2:
                recent_color = "🔴" if recent_change < 0 else "🟢"
                st.metric("近5日涨跌", f"{recent_color} {recent_change:+.2f}%")
            with col3:
                vol = 0
                if len(prices) >= 20:
                    returns = [(prices[i]/prices[i-1]-1) for i in range(1, len(prices))]
                    vol = pd.Series(returns).std() * np.sqrt(250) * 100
                st.metric("年化波动率", f"{vol:.1f}%")

            # 均线多空判断（通俗解释）
            st.markdown("**📈 趋势判断**")
            ma_analysis = []

            # MA5 = 5日均线 = 最近5天平均价
            if current_ma5 and current_price_idx > current_ma5:
                ma_analysis.append("🟢 **近5天在涨**（短线强势）")
            elif current_ma5:
                ma_analysis.append("🔴 **近5天在跌**（短线弱势）")

            # MA20 = 20日均线 ≈ 最近1个月平均价
            if current_ma20 and current_price_idx > current_ma20:
                ma_analysis.append("🟢 **近1月在涨**（中期强势）")
            elif current_ma20:
                ma_analysis.append("🔴 **近1月在跌**（中期弱势）")

            # MA60 = 60日均线 ≈ 最近3个月平均价
            if current_ma60 and current_price_idx > current_ma60:
                ma_analysis.append("🟢 **近3月在涨**（长期强势）")
            elif current_ma60:
                ma_analysis.append("🔴 **近3月在跌**（长期弱势）")

            for analysis in ma_analysis:
                st.markdown(analysis)

            # 判断是否适合做网格
            st.markdown("**🎯 适合做网格吗？**")
            grid_suitable = True
            grid_reasons = []

            # 1. 波动率判断（网格需要波动才有利润）
            if vol < 10:
                grid_suitable = False
                grid_reasons.append("⚠️ 波动太小（年化仅 {:.1f}%），网格利润空间不足".format(vol))
            elif vol > 40:
                grid_suitable = False
                grid_reasons.append("⚠️ 波动太大（年化 {:.1f}%），风险较高".format(vol))
            else:
                grid_reasons.append("✅ 波动适中（年化 {:.1f}%），有利润空间".format(vol))

            # 2. 趋势判断（震荡市适合网格，趋势市不适合）
            trend_score = 0
            if current_ma5 and current_price_idx > current_ma5:
                trend_score += 1
            else:
                trend_score -= 1
            if current_ma20 and current_price_idx > current_ma20:
                trend_score += 1
            else:
                trend_score -= 1
            if current_ma60 and current_price_idx > current_ma60:
                trend_score += 1
            else:
                trend_score -= 1

            if trend_score >= 2:
                grid_suitable = False
                grid_reasons.append("⚠️ 明显上涨趋势，不适合（容易卖飞）")
            elif trend_score <= -2:
                grid_suitable = False
                grid_reasons.append("⚠️ 明显下跌趋势，不适合（容易套牢）")
            else:
                grid_reasons.append("✅ 震荡整理，适合网格交易")

            # 3. 显示结论
            if grid_suitable:
                st.success("**✅ 目前适合做网格交易**")
            else:
                st.warning("**⚠️ 目前不太适合做网格**")

            for reason in grid_reasons:
                st.markdown(reason)

            # AI解读按钮
            st.divider()
            if 'ai_explain' not in st.session_state:
                st.session_state.ai_explain = False

            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("🤖 AI解读", use_container_width=True):
                    st.session_state.ai_explain = not st.session_state.ai_explain

            if st.session_state.ai_explain:
                # 检查AI是否配置
                from utils.llm_service import get_llm_service
                settings = load_settings()
                config = settings.get('data', {}) if settings else {}
                llm = get_llm_service(config)

                if not llm.enabled:
                    st.info("💡 请在设置中配置AI模型才能使用AI解读功能")
                else:
                    # 构建提示词（不包含结论，让AI自己判断）
                    prompt = f"""你是一位专业的网格交易策略分析师。请根据以下数据，判断这只股票是否适合做网格交易，并给出投资建议。

【股票数据】
- 股票名称：{item_name}
- 当前价格：{current_price_idx:.2f}
- 区间涨跌：{price_change_pct:+.2f}%
- 近5日涨跌：{recent_change:+.2f}%
- 年化波动率：{vol:.1f}%

【趋势判断】（MA5=5日均线，MA20=20日均线，MA60=60日均线）
{chr(10).join(ma_analysis)}

请分析并给出：
1. 是否适合做网格交易？（适合/不太适合）
2. 判断理由是什么？
3. 如果适合，建议什么策略？（网格间距、仓位等）

请用通俗易懂的语言回答。
"""

                    # 先显示提示词
                    st.markdown("**📤 发送给AI的提示词：**")
                    with st.expander("查看提示词内容", expanded=False):
                        st.text(prompt)

                    if st.button("🚀 确认发送给AI", use_container_width=True):
                        with st.spinner("🤖 AI正在分析..."):
                            try:
                                # 直接调用LLM API
                                import requests
                                headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {llm.api_key}'}
                                payload = {
                                    'model': llm.model,
                                    'messages': [{'role': 'user', 'content': prompt}],
                                    'temperature': 0.3,
                                    'max_tokens': 800
                                }
                                response = requests.post(llm.api_url, headers=headers, json=payload, timeout=30)
                                if response.status_code == 200:
                                    result = response.json()
                                    content = result.get('choices', [{}])[0].get('message', {}).get('content', '')
                                    if content:
                                        st.markdown("**📋 AI解读结果：**")
                                        st.info(content)
                                    else:
                                        st.warning("AI未返回有效内容")
                                else:
                                    st.error(f"AI调用失败: {response.status_code}")
                            except Exception as e:
                                st.error(f"AI解读失败: {e}")
        else:
            st.info("💡 数据不足，无法进行分析")

    else:
        if source_label == "股票" and stock_code:
            st.error(f"❌ 无法获取股票 {stock_code} 的数据，请检查代码是否正确")
        else:
            st.warning("📭 暂时无法获取数据，请确保交易系统正在运行")

# ========== 回测分析页面 ==========
elif page == "📈 回测分析":
    st.title("📈 回测分析")

    # 参数配置
    with st.sidebar:
        st.markdown("### 回测参数")

        # 策略选择
        st.markdown("**📊 交易策略**")
        backtest_strategy = st.selectbox(
            "选择策略",
            options=['trend_grid', 'grid', 'ma_crossover'],
            index=0,
            format_func=lambda x: {
                'grid': '原始网格策略',
                'trend_grid': '趋势网格策略(MA20+止损止盈)',
                'ma_crossover': '均线交叉策略(金叉买死叉卖)'
            }.get(x, x),
            help="选择用于回测的策略"
        )

        # 均线策略参数
        if backtest_strategy == 'ma_crossover':
            st.markdown("**均线参数**")
            col1, col2 = st.columns(2)
            with col1:
                fast_ma = st.slider("快速MA", 3, 20, 5)
            with col2:
                slow_ma = st.slider("慢速MA", 10, 60, 20)

        # 日期范围 - 默认近15个月，结束日期3个月前
        from dateutil.relativedelta import relativedelta
        today = datetime.today()
        default_end = today - relativedelta(months=3)
        default_start = default_end - relativedelta(months=15)

        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("开始日期", value=default_start)
        with col2:
            end_date = st.date_input("结束日期", value=default_end)

        # 初始资金
        initial_capital = st.number_input("初始资金(元)", value=100000, step=10000, min_value=10000)

        # 网格参数
        st.markdown("**网格参数**")
        col1, col2 = st.columns(2)
        with col1:
            grid_levels = st.slider("网格档位", 5, 20, 10)
        with col2:
            grid_spacing_pct = st.slider("网格间距(%)", 1, 10, 5)
        grid_spacing = grid_spacing_pct / 100

        # 趋势策略额外参数
        if backtest_strategy == 'trend_grid':
            st.markdown("**趋势过滤参数**")
            col1, col2 = st.columns(2)
            with col1:
                ma_period = st.slider("MA周期", 5, 60, 20)
            with col2:
                trend_threshold_pct = st.slider("趋势阈值(%)", 1, 20, 5)
            trend_threshold = trend_threshold_pct / 100

            st.markdown("**风控参数**")
            col1, col2 = st.columns(2)
            with col1:
                stop_loss_pct = st.slider("止损(%)", 1, 10, 3)
            with col2:
                take_profit_pct = st.slider("止盈(%)", 1, 20, 8)
            stop_loss = stop_loss_pct / 100
            take_profit = take_profit_pct / 100

        # 交易成本
        st.markdown("**交易成本**")
        col1, col2 = st.columns(2)
        with col1:
            commission_rate = st.number_input("佣金(%)", value=0.025, step=0.005) / 100
        with col2:
            slippage_rate = st.number_input("滑点(%)", value=0.1, step=0.05) / 100

        run_backtest = st.button("🚀 运行回测", use_container_width=True)

        # 清除缓存
        if st.button("🗑️ 清除结果", use_container_width=True):
            if 'backtest_result' in st.session_state:
                del st.session_state['backtest_result']
            st.rerun()

    # 运行回测
    if run_backtest or 'backtest_result' in st.session_state:
        if run_backtest:
            with st.spinner("正在获取历史数据..."):
                try:
                    # 获取历史数据
                    status = get_api('http://127.0.0.1:5000/api/status')
                    if status and status.get('success'):
                        current_price = status['data']['current_price']

                        # 生成模拟历史数据（用于演示）
                        # 实际应该从聚宽API获取历史数据
                        import pandas as pd
                        dates = pd.date_range(start=start_date, end=end_date, freq='B')
                        np.random.seed(42)
                        returns = np.random.normal(0.0005, 0.02, len(dates))
                        prices = current_price * (1 + returns).cumprod()

                        price_data = pd.DataFrame({
                            'date': dates,
                            'open': prices * 0.99,
                            'high': prices * 1.02,
                            'low': prices * 0.98,
                            'close': prices,
                            'volume': [1000000] * len(dates)
                        })

                        # 根据选择的策略运行回测
                        if backtest_strategy == 'grid':
                            engine = BacktestEngine(
                                initial_capital=initial_capital,
                                grid_levels=grid_levels,
                                grid_spacing=grid_spacing,
                                commission_rate=commission_rate,
                                slippage_rate=slippage_rate
                            )
                            result = engine.run(price_data)
                        elif backtest_strategy == 'ma_crossover':
                            # 均线交叉策略回测
                            from strategies.ma_crossover import MACrossoverStrategy
                            strategy = MACrossoverStrategy(
                                initial_capital=initial_capital,
                                fast_ma=fast_ma,
                                slow_ma=slow_ma,
                                commission_rate=commission_rate,
                                slippage_rate=slippage_rate
                            )
                            result = strategy.run(price_data)
                        else:
                            # 趋势网格策略回测
                            strategy = TrendGridStrategy(
                                initial_capital=initial_capital,
                                grid_levels=grid_levels,
                                grid_spacing=grid_spacing,
                                unit_size=100,
                                commission_rate=commission_rate,
                                slippage_rate=slippage_rate,
                                ma_period=ma_period,
                                trend_threshold=trend_threshold,
                                confirm_days=1
                            )
                            result = strategy.run(price_data)

                        # 添加网格配置信息
                        result['grid_config'] = {
                            'baseline_price': price_data['close'].iloc[0]
                        }

                        st.session_state['backtest_result'] = result
                        st.session_state['backtest_params'] = {
                            'start_date': str(start_date),
                            'end_date': str(end_date),
                            'initial_capital': initial_capital,
                            'grid_levels': grid_levels,
                            'grid_spacing': grid_spacing,
                            'strategy': backtest_strategy
                        }
                    else:
                        st.error("无法获取当前价格，请确保交易系统运行中")
                except Exception as e:
                    st.error(f"回测失败: {str(e)}")

    # 运行回测
    if run_backtest or 'backtest_result' in st.session_state:
        if run_backtest:
            with st.spinner("正在获取历史数据..."):
                try:
                    # 获取历史数据
                    status = get_api('http://127.0.0.1:5000/api/status')
                    if status and status.get('success'):
                        current_price = status['data']['current_price']

                        # 生成模拟历史数据（用于演示）
                        # 实际应该从聚宽API获取历史数据
                        import pandas as pd
                        dates = pd.date_range(start=start_date, end=end_date, freq='B')
                        np.random.seed(42)
                        returns = np.random.normal(0.0005, 0.02, len(dates))
                        prices = current_price * (1 + returns).cumprod()

                        price_data = pd.DataFrame({
                            'date': dates,
                            'open': prices * 0.99,
                            'high': prices * 1.02,
                            'low': prices * 0.98,
                            'close': prices,
                            'volume': [1000000] * len(dates)
                        })

                        # 运行回测
                        engine = BacktestEngine(
                            initial_capital=initial_capital,
                            grid_levels=grid_levels,
                            grid_spacing=grid_spacing,
                            commission_rate=commission_rate,
                            slippage_rate=slippage_rate
                        )
                        result = engine.run(price_data)
                        st.session_state['backtest_result'] = result
                        st.session_state['backtest_params'] = {
                            'start_date': str(start_date),
                            'end_date': str(end_date),
                            'initial_capital': initial_capital,
                            'grid_levels': grid_levels,
                            'grid_spacing': grid_spacing
                        }
                    else:
                        st.error("无法获取当前价格，请确保交易系统运行中")
                except Exception as e:
                    st.error(f"回测失败: {str(e)}")

        # 显示结果
        if 'backtest_result' in st.session_state:
            result = st.session_state['backtest_result']
            metrics = result.get('metrics', {})

            st.divider()

            # AI大模型分析（默认关闭）
            st.markdown("### 🤖 AI策略推荐")

            # 初始化session state
            if 'run_ai_analysis' not in st.session_state:
                st.session_state.run_ai_analysis = False

            def display_ai_result(analysis):
                """显示AI分析结果"""
                if not analysis:
                    return

                # 市场状态
                market_status = analysis.get('market_status', '未知')
                status_icon = {
                    '牛市': '🐂',
                    '熊市': '🐻',
                    '震荡市': '📊',
                    '高波动': '⚡'
                }.get(market_status, '❓')

                st.markdown(f"### {status_icon} 市场状态：{market_status}")

                # 信号描述
                signal = analysis.get('signal', '分析中')
                st.info(f"📋 **市场信号**: {signal}")

                # 推荐策略（重点突出）
                strategy = analysis.get('recommended_strategy', '观望')
                strategy_icon = {
                    '网格策略': '📦',
                    '趋势跟踪': '📈',
                    '观望': '👀',
                    '空仓': '⏸️'
                }.get(strategy, '❓')

                st.success(f"### {strategy_icon} 推荐策略：{strategy}")

                # 策略理由
                rationale = analysis.get('strategy_rationale', '')
                if rationale:
                    st.markdown(f"**理由**: {rationale}")

                # 仓位建议
                position = analysis.get('position_suggestion', '轻仓')
                position_icon = {
                    '满仓': '🟢',
                    '重仓': '🟢',
                    '半仓': '🟡',
                    '轻仓': '🟠',
                    '空仓': '🔴'
                }.get(position, '⚪')
                st.markdown(f"{position_icon} 仓位建议：{position}")

                # 网格间距建议（如果适用）
                grid_suggest = analysis.get('grid_suggestion', '')
                if grid_suggest:
                    st.info(f"📐 **网格间距建议**: {grid_suggest}")

                # 参数调整建议
                param_adjust = analysis.get('parameter_adjustment', '')
                if param_adjust:
                    st.markdown(f"**⚙️ 参数调整**: {param_adjust}")

                # 风险等级
                risk = analysis.get('risk_level', 'medium').upper()
                risk_color = {"LOW": "🟢", "MEDIUM": "🟡", "HIGH": "🔴"}.get(risk, "⚪")
                st.caption(f"{risk_color} 风险等级: {risk}")

                # 原始返回
                raw = analysis.get('raw_response', '')
                if raw:
                    with st.expander("📄 查看AI原始返回"):
                        import json
                        try:
                            json_start = raw.find('{')
                            json_end = raw.rfind('}') + 1
                            if json_start >= 0 and json_end > json_start:
                                json_str = raw[json_start:json_end]
                                parsed = json.loads(json_str)
                                st.json(parsed)
                            else:
                                st.text(raw)
                        except:
                            st.text(raw)

            # AI分析开关
            if not st.session_state.run_ai_analysis:
                col1, col2 = st.columns([1, 3])
                with col1:
                    if st.button("🤖 启用AI分析", use_container_width=True):
                        st.session_state.run_ai_analysis = True
                        st.rerun()
                with col2:
                    st.info("💡 点击按钮启用AI策略分析（需要一定时间）")
            else:
                ai_analysis = result.get('ai_analysis', {})

                # 情况1：回测已有AI分析结果
                if ai_analysis and ai_analysis.get('ai_enabled') and not ai_analysis.get('error'):
                    try:
                        from utils.llm_service import get_llm_service
                        config = st.session_state.get('config', {})
                        llm = get_llm_service(config)
                        prices = result.get('close_prices', []) or result.get('equity_curve', [])
                        dates = result.get('dates', [])
                        trades = result.get('trades', [])
                        account_info = result.get('account_info', {})
                    except:
                        pass
                    display_ai_result(ai_analysis)

                # 情况2：有error
                elif ai_analysis and ai_analysis.get('error'):
                    st.warning(f"⚠️ {ai_analysis.get('error', 'AI分析暂时不可用')}")
                    st.info("💡 请在设置中配置API密钥")

                # 情况3：流式调用
                else:
                    try:
                        from utils.llm_service import get_llm_service
                        config = st.session_state.get('config', {})
                        llm = get_llm_service(config)

                        if not llm.enabled:
                            st.info("🤖 AI分析未启用，请在设置中配置AI模型")
                        else:
                            prices = result.get('close_prices', []) or result.get('equity_curve', [])
                            dates = result.get('dates', [])
                            trades = result.get('trades', [])
                            account_info = result.get('account_info', {})

                            if len(prices) >= 5:
                                with st.chat_message("assistant"):
                                    text_area = st.empty()
                                    text_area.info("🤖 AI正在分析市场...")

                                full_content = ''
                                market_result = None
                                strategy_result = None

                                for chunk in llm.analyze_market_stream(prices, dates, market_indicators=None, account_info=account_info, trades=trades):
                                    if not chunk.get('enabled'):
                                        if chunk.get('error'):
                                            text_area.warning(f"⚠️ {chunk.get('error')}")
                                        break

                                    phase = chunk.get('phase')

                                    if phase == 'market':
                                        delta = chunk.get('delta', '')
                                        if delta:
                                            full_content += delta
                                            text_area.text(full_content + "▌")
                                    elif phase == 'market_done':
                                        market_result = chunk.get('market_analysis', {})
                                    elif phase == 'strategy_start':
                                        text_area.text(full_content + "\n\n🤖 正在生成策略建议...")
                                    elif phase == 'strategy_done':
                                        strategy_result = chunk.get('strategy_recommendation', {})

                                text_area.text(full_content)
                                if market_result or strategy_result:
                                    st.markdown("---")
                                    st.markdown("**AI分析结果：**")
                                    if market_result:
                                        # 显示市场状态
                                        market_status = market_result.get('market_status', '未知')
                                        status_icon = {
                                            '牛市': '🐂', '熊市': '🐻', '震荡市': '📊', '高波动': '⚡'
                                        }.get(market_status, '❓')
                                        st.markdown(f"{status_icon} 市场状态：{market_status}")
                                        st.info(f"📋 **{market_result.get('signal', '分析中')}**")
                                    if strategy_result:
                                        strategy = strategy_result.get('recommended_strategy', '观望')
                                        strategy_icon = {
                                            '网格策略': '📦', '趋势跟踪': '📈', '观望': '👀', '空仓': '⏸️'
                                        }.get(strategy, '❓')
                                        st.success(f"{strategy_icon} 推荐策略：{strategy}")
                                        rationale = strategy_result.get('strategy_rationale', '')
                                        if rationale:
                                            st.markdown(f"**理由**: {rationale}")
                                        position = strategy_result.get('position_suggestion', '轻仓')
                                        st.markdown(f"📊 仓位建议：{position}")
                                        grid_suggest = strategy_result.get('grid_suggestion', '')
                                        if grid_suggest:
                                            st.info(f"📐 **网格间距建议**: {grid_suggest}")
                            else:
                                st.info("🤖 数据不足，无法进行AI分析")
                    except Exception as e:
                        st.info("🤖 AI分析未启用，请在设置中配置AI模型")

                if st.button("🔄 重新分析", use_container_width=True):
                    st.session_state.run_ai_analysis = False
                    st.rerun()

            # 规则引擎技术分析（仅显示指标，不推荐策略）
            market_analysis = result.get('market_analysis', {})
            if market_analysis and market_analysis.get('status') != 'unknown':
                with st.expander("📊 规则引擎技术指标（仅供参考）"):
                    status = market_analysis.get('status', 'unknown')
                    status_emoji = {
                        'bull': '🐂 牛市',
                        'strong_bull': '🐂 强势牛市',
                        'bear': '🐻 熊市',
                        'strong_bear': '🐻 强势熊市',
                        'sideways': '📊 震荡',
                        'volatile': '⚡ 高波动'
                    }.get(status, '❓')

                    st.markdown(f"**市场状态**: {status_emoji}")

                    details = market_analysis.get('details', {})
                    if details:
                        col_a, col_b, col_c = st.columns(3)
                        col_a.metric("MA5", f"{details.get('ma5', 0):.3f}" if details.get('ma5') else "N/A")
                        col_b.metric("MA20", f"{details.get('ma20', 0):.3f}" if details.get('ma20') else "N/A")
                        col_c.metric("MA60", f"{details.get('ma60', 0):.3f}" if details.get('ma60') else "N/A")

                        col_d, col_e = st.columns(2)
                        col_d.metric("20日动量", f"{details.get('momentum_20', 0):.2f}%")
                        col_e.metric("年化波动率", f"{details.get('volatility_annual', 0):.2f}%")

                    st.caption("💡 策略推荐由上方AI分析提供")

            st.divider()

            # 核心指标
            st.markdown("### 📊 回测结果")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("总收益率", f"{metrics.get('total_return', 0):.2f}%",
                          delta=f"{metrics.get('total_return', 0):.2f}%")
            with col2:
                st.metric("年化收益率", f"{metrics.get('annualized_return', 0):.2f}%")
            with col3:
                st.metric("最大回撤", f"{metrics.get('max_drawdown', 0):.2f}%")
            with col4:
                st.metric("夏普比率", f"{metrics.get('sharpe_ratio', 0):.2f}")

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("胜率", f"{metrics.get('win_rate', 0):.1f}%")
            with col2:
                st.metric("总交易次数", f"{metrics.get('total_trades', 0)}")
            with col3:
                st.metric("盈利因子", f"{metrics.get('profit_factor', 0):.2f}")
            with col4:
                st.metric("每笔平均", f"{metrics.get('avg_profit_per_trade', 0):.2f}元")

            # 权益曲线
            st.divider()
            st.markdown("### 📈 权益曲线")

            equity = result.get('equity_curve', [])
            dates = result.get('dates', [])

            if equity and dates:
                import pandas as pd
                equity_df = pd.DataFrame({'date': pd.to_datetime(dates), 'equity': equity})

                # 使用Streamlit原生图表
                st.line_chart(equity_df.set_index('date'), height=300)

            # 回撤曲线
            st.markdown("### 📉 回撤曲线")
            drawdown = result.get('drawdown_series', [])
            if drawdown and dates:
                drawdown_df = pd.DataFrame({'date': pd.to_datetime(dates), 'drawdown': drawdown})
                st.area_chart(drawdown_df.set_index('date'), height=200)

            # 月度收益热力图
            st.divider()
            st.markdown("### 📅 月度收益热力图")
            monthly = result.get('monthly_returns', {})

            if monthly:
                # 创建12x12网格
                import calendar

                # 解析月度数据
                month_data = {}
                for ym, ret in monthly.items():
                    year, month = ym.split('-')
                    if year not in month_data:
                        month_data[year] = {}
                    month_data[year][int(month)] = ret

                # 显示每个年度
                for year in sorted(month_data.keys()):
                    st.markdown(f"**{year}年**")
                    months = month_data[year]
                    cols = st.columns(4)
                    for i, month_name in enumerate(['1月', '2月', '3月', '4月', '5月', '6月',
                                                     '7月', '8月', '9月', '10月', '11月', '12月']):
                        month_num = i + 1
                        if month_num in months:
                            ret = months[month_num]
                            color = "#22c55e" if ret >= 0 else "#ef4444"
                            cols[i % 4].markdown(
                                f"<div style='padding:10px; background:{color}20; "
                                f"border-radius:8px; text-align:center;'>"
                                f"<div style='color:#888; font-size:12px;'>{month_name}</div>"
                                f"<div style='color:{color}; font-weight:bold;'>{ret:+.1f}%</div>"
                                f"</div>",
                                unsafe_allow_html=True
                            )
                        else:
                            cols[i % 4].markdown(
                                f"<div style='padding:10px; background:#333; border-radius:8px; "
                                f"text-align:center;'>"
                                f"<div style='color:#888; font-size:12px;'>{month_name}</div>"
                                f"<div style='color:#666;'>-</div>"
                                f"</div>",
                                unsafe_allow_html=True
                            )

            # 交易明细
            st.divider()
            st.markdown("### 📋 交易明细")
            trades = result.get('trades', [])
            if trades:
                trade_df = pd.DataFrame(trades)
                trade_df['date'] = pd.to_datetime(trade_df['date']).dt.strftime('%Y-%m-%d')
                trade_df['action'] = trade_df['action'].map({'buy': '买入', 'sell': '卖出'})
                st.dataframe(trade_df, use_container_width=True, hide_index=True)
            else:
                st.info("无交易记录")

            # 参数敏感性分析
            if show_sensitivity:
                st.divider()
                st.markdown("### 🔬 参数敏感性分析")

                with st.spinner("正在测试不同参数组合..."):
                    engine = BacktestEngine(
                        initial_capital=initial_capital,
                        grid_levels=10,
                        grid_spacing=0.05,
                        commission_rate=commission_rate,
                        slippage_rate=slippage_rate
                    )

                    # 获取模拟数据
                    import pandas as pd
                    np.random.seed(42)
                    dates = pd.date_range(start=start_date, end=end_date, freq='B')
                    current_price = st.session_state.get('backtest_result', {}).get('grid_config', {}).get('baseline_price', 4.0)
                    returns = np.random.normal(0.0005, 0.02, len(dates))
                    prices = current_price * (1 + returns).cumprod()
                    price_data = pd.DataFrame({
                        'date': dates, 'close': prices,
                        'open': prices * 0.99, 'high': prices * 1.02,
                        'low': prices * 0.98, 'volume': [1000000] * len(dates)
                    })

                    results = engine.run_parameter_sweep(price_data)

                    # 显示Top10参数组合
                    st.markdown("**最优参数组合 (Top 10)**")
                    top_results = results[:10]

                    sensitivity_data = []
                    for r in top_results:
                        params = r.get('params', {})
                        m = r.get('metrics', {})
                        sensitivity_data.append({
                            '网格档位': params.get('levels', 0),
                            '网格间距(%)': f"{params.get('spacing', 0) * 100:.1f}",
                            '总收益率(%)': f"{m.get('total_return', 0):.2f}",
                            '年化收益(%)': f"{m.get('annualized_return', 0):.2f}",
                            '最大回撤(%)': f"{m.get('max_drawdown', 0):.2f}",
                            '夏普比率': f"{m.get('sharpe_ratio', 0):.2f}",
                        })

                    sensitivity_df = pd.DataFrame(sensitivity_data)
                    st.dataframe(sensitivity_df, use_container_width=True, hide_index=True)

    else:
        st.info("👈 配置回测参数后点击「运行回测」开始分析")

# ========== 日志页面 ==========
elif page == "📋 日志":
    st.title("📋 系统日志")

    if st.button("刷新"):
        st.rerun()

    logs_data = get_api('http://127.0.0.1:5000/api/logs?lines=100')

    if logs_data and logs_data.get('success'):
        st.markdown(f"**文件**: `{logs_data['data']['log_file']}`")
        st.markdown(f"**记录数**: {logs_data['data']['count']} 条")

        logs = logs_data['data']['lines']
        if logs:
            st.divider()
            st.markdown('<div class="log-container">', unsafe_allow_html=True)
            for log in reversed(logs[-50:]):
                if "ERROR" in log or "错误" in log:
                    st.markdown(f'<div class="log-error">{log}</div>', unsafe_allow_html=True)
                elif "WARNING" in log or "警告" in log:
                    st.markdown(f'<div class="log-warning">{log}</div>', unsafe_allow_html=True)
                elif "INFO" in log or "信息" in log:
                    st.markdown(f'<div class="log-info">{log}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="log-debug">{log}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("暂无日志")
    else:
        st.error("无法获取日志，请确保交易系统正在运行")
