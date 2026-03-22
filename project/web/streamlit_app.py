"""
ETF网格交易系统 - Streamlit Web监控面板
"""
import streamlit as st
import requests
import yaml
import os
import subprocess
from datetime import datetime


def restart_trading_system():
    """重启交易系统"""
    try:
        # 杀掉现有main.py进程
        subprocess.run(['taskkill', '/F', '/IM', 'python.exe', '/FI', 'WINDOWTITLE eq *main.py*'],
                      capture_output=True, stderr=subprocess.DEVNULL)
        import time
        time.sleep(2)
        # 启动新的交易系统
        subprocess.Popen(['python', 'main.py'], cwd=os.path.dirname(os.path.dirname(__file__)))
        return True
    except:
        return False

st.set_page_config(
    page_title="ETF网格交易监控",
    layout="wide",
    page_icon="📈"
)

# 森林绿主题 - 护眼莫兰迪色系
st.markdown("""
<style>
    /* 主背景 */
    .stApp { background-color: #1c2118; }

    /* 侧边栏 */
    .stSidebar > div:first-child { background: #252b22; }

    /* 标题 */
    h1, h2, h3 { color: #d4e0c8 !important; font-weight: 600; }

    /* 指标值 - 高对比度 */
    [data-testid="stMetricValue"] {
        color: #e8f0e0 !important;
        font-size: 32px !important;
        font-weight: 700 !important;
    }
    [data-testid="stMetricLabel"] { color: #9aaa88 !important; font-size: 14px !important; }
    [data-testid="stMetricDelta"] { color: #b8d4a8 !important; }

    /* 标签页 */
    .stTabs [data-baseweb="tab-list"] { gap: 8px; background: #252b22; border-radius: 12px; padding: 8px; }
    .stTabs [data-baseweb="tab"] {
        color: #8a9a78;
        font-weight: 500;
        padding: 10px 24px;
        border-radius: 8px;
    }
    .stTabs [data-baseweb="tab"]:hover { color: #d4e0c8; background: #2d362a; }
    .stTabs [aria-selected="true"] { background: #3d4a38 !important; color: #d4e0c8 !important; font-weight: 600; }

    /* 卡片背景 */
    [data-testid="stHorizontalBlock"] > div { background: #252b22; border-radius: 16px; padding: 20px; border: 1px solid #3a4234; }

    /* 表单 */
    .stForm { background: #252b22; border-radius: 16px; padding: 24px; border: 1px solid #3a4234; }
    .stTextInput > div > div > input, .stPassword > div > div > input {
        background: #1c2118;
        color: #e8f0e0;
        border: 1px solid #3a4234;
        border-radius: 10px;
        padding: 12px;
    }
    .stTextInput > div > div > input:focus, .stPassword > div > div > input:focus {
        border-color: #5a7a48;
        box-shadow: 0 0 0 2px rgba(90, 122, 72, 0.3);
    }

    /* 按钮 */
    .stButton > button {
        background: linear-gradient(135deg, #5a7a48 0%, #4a6a38 100%);
        color: #e8f0e0;
        border: none;
        border-radius: 10px;
        padding: 12px 28px;
        font-weight: 600;
        font-size: 15px;
    }
    .stButton > button:hover { background: linear-gradient(135deg, #6a8a58 0%, #5a7a48 100%); }

    /* 进度条 */
    .stProgress > div > div > div > div { background: linear-gradient(90deg, #5a7a48, #7a9a68) !important; }

    /* 分隔线 */
    hr { border-color: #3a4234 !important; margin: 24px 0 !important; }

    /* 成功/警告/错误 */
    .stSuccess { background: #2d3a28; border: 1px solid #5a7a48; border-radius: 10px; }
    .stWarning { background: #3a3528; border: 1px solid #7a6a38; border-radius: 10px; }
    .stError { background: #3a2828; border: 1px solid #7a4848; border-radius: 10px; }
    .stInfo { background: #282d3a; border: 1px solid #38487a; border-radius: 10px; }

    /* 文字 */
    p, span, div { color: #b8c8a8; }
    .stCaption { color: #788878 !important; }

    /* 数字高亮 */
    .highlight-value { color: #e8f0e0; font-size: 48px; font-weight: 700; }
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
page = st.radio("", ["📊 监控面板", "⚙️ 设置", "📋 日志"], horizontal=True, label_visibility="collapsed")

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
        cols = st.columns(10)
        for i, level in enumerate(levels):
            with cols[i]:
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
        submitted = st.form_submit_button("保存")
        if submitted:
            result = put_api('http://127.0.0.1:5000/api/config/notification', {'server酱_key': server酱_key})
            if result and result.get('success'):
                st.success("保存成功!")
            else:
                st.error("保存失败: 无法连接到交易系统")

    st.divider()

    st.subheader("🔐 聚宽账号")
    creds = config.get('credentials', {})
    with st.form("jq_config"):
        col1, col2 = st.columns(2)
        with col1:
            username = st.text_input("用户名", value=creds.get('username', ''))
        with col2:
            password = st.text_input("密码", value=creds.get('password', ''), type='password')
        submitted = st.form_submit_button("保存")
        if submitted:
            result = put_api('http://127.0.0.1:5000/api/config/credentials', {'username': username, 'password': password})
            if result and result.get('success'):
                st.success("保存成功!")
            else:
                st.error("保存失败: 无法连接到交易系统")

    if st.button("🔄 重启交易系统", use_container_width=True):
        with st.spinner("正在重启..."):
            success = restart_trading_system()
            if success:
                st.success("交易系统已重启!")
            else:
                st.error("重启失败，请手动重启")

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
            for log in reversed(logs[-50:]):
                if "ERROR" in log:
                    st.markdown(f":red[{log}]")
                elif "WARNING" in log:
                    st.markdown(f":orange[{log}]")
                else:
                    st.text(log)
        else:
            st.info("暂无日志")
    else:
        st.error("无法获取日志，请确保交易系统正在运行")
