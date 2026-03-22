#!/bin/bash

# ========================================
#    ETF网格交易系统管理器 (macOS/Linux)
# ========================================

PROJECT_DIR="$(cd "$(dirname "$0")/project" && pwd)"
PID_DIR="$(dirname "$0")/.pids"
mkdir -p "$PID_DIR"

usage() {
    echo "========================================"
    echo "   ETF网格交易系统管理器"
    echo "========================================"
    echo ""
    echo "用法: $0 [command]"
    echo ""
    echo "命令:"
    echo "  start main      - 启动交易系统"
    echo "  start web       - 启动Web面板(Flask)"
    echo "  start streamlit - 启动Streamlit面板"
    echo "  start all       - 启动所有服务"
    echo "  stop main       - 停止交易系统"
    echo "  stop web        - 停止Web面板"
    echo "  stop streamlit   - 停止Streamlit面板"
    echo "  stop all        - 停止所有服务"
    echo "  restart main     - 重启交易系统"
    echo "  restart web      - 重启Web面板"
    echo "  restart streamlit - 重启Streamlit面板"
    echo "  restart all      - 重启所有服务"
    echo "  status          - 查看服务状态"
    echo "  log             - 查看日志"
    echo "  help            - 显示帮助"
    echo ""
}

status() {
    echo "========================================"
    echo "   服务状态"
    echo "========================================"
    echo ""

    if pgrep -f "python.*main.py" > /dev/null 2>&1; then
        echo "  交易系统(main.py): [运行中]"
    else
        echo "  交易系统(main.py): [已停止]"
    fi

    if pgrep -f "python.*web/app.py" > /dev/null 2>&1; then
        echo "  Web面板(Flask):    [运行中]"
    else
        echo "  Web面板(Flask):    [已停止]"
    fi

    if pgrep -f "streamlit.*streamlit_app.py" > /dev/null 2>&1; then
        echo "  Streamlit面板:     [运行中]"
    else
        echo "  Streamlit面板:     [已停止]"
    fi
    echo ""
}

show_log() {
    echo "========================================"
    echo "   最近日志"
    echo "========================================"
    TODAY=$(date +%Y%m%d)
    LOG_FILE="$PROJECT_DIR/logs/trading_$TODAY.log"
    if [ -f "$LOG_FILE" ]; then
        grep -E "ERROR|WARNING|INFO" "$LOG_FILE" | tail -20
    else
        echo "今日日志文件不存在"
    fi
    echo ""
}

start_main() {
    echo "[启动] 交易系统..."
    cd "$PROJECT_DIR"
    nohup python3 main.py > /dev/null 2>&1 &
    echo "$$" > "$PID_DIR/main.pid"
    echo "[成功] 交易系统已在后台启动"
}

start_web() {
    echo "[启动] Web面板(Flask)..."
    cd "$PROJECT_DIR"
    nohup python3 web/app.py > /dev/null 2>&1 &
    echo "$$" > "$PID_DIR/web.pid"
    echo "[成功] Web面板已在后台启动"
    echo "    访问地址: http://127.0.0.1:5000"
}

start_streamlit() {
    echo "[启动] Streamlit面板..."
    cd "$PROJECT_DIR"
    nohup streamlit run web/streamlit_app.py --server.port 8501 --server.headless=true > /dev/null 2>&1 &
    echo "$$" > "$PID_DIR/streamlit.pid"
    echo "[成功] Streamlit面板已在后台启动"
    echo "    访问地址: http://localhost:8501"
}

start_all() {
    start_main
    start_web
}

stop_main() {
    echo "[停止] 交易系统..."
    pkill -f "python.*main.py" 2>/dev/null
    rm -f "$PID_DIR/main.pid" 2>/dev/null
    echo "[成功] 交易系统已停止"
}

stop_web() {
    echo "[停止] Web面板..."
    pkill -f "python.*web/app.py" 2>/dev/null
    rm -f "$PID_DIR/web.pid" 2>/dev/null
    echo "[成功] Web面板已停止"
}

stop_streamlit() {
    echo "[停止] Streamlit面板..."
    pkill -f "streamlit.*streamlit_app.py" 2>/dev/null
    rm -f "$PID_DIR/streamlit.pid" 2>/dev/null
    echo "[成功] Streamlit面板已停止"
}

stop_all() {
    stop_main
    stop_web
    stop_streamlit
}

restart_main() {
    stop_main
    sleep 2
    start_main
}

restart_web() {
    stop_web
    sleep 2
    start_web
}

restart_streamlit() {
    stop_streamlit
    sleep 2
    start_streamlit
}

restart_all() {
    stop_all
    sleep 2
    start_all
}

case "$1" in
    help|--help|-h)
        usage
        ;;
    start)
        case "$2" in
            main) start_main ;;
            web) start_web ;;
            streamlit) start_streamlit ;;
            all) start_all ;;
            *) echo "[错误] 未知服务: $2" ;;
        esac
        ;;
    stop)
        case "$2" in
            main) stop_main ;;
            web) stop_web ;;
            streamlit) stop_streamlit ;;
            all) stop_all ;;
            *) echo "[错误] 未知服务: $2" ;;
        esac
        ;;
    restart)
        case "$2" in
            main) restart_main ;;
            web) restart_web ;;
            streamlit) restart_streamlit ;;
            all) restart_all ;;
            *) echo "[错误] 未知服务: $2" ;;
        esac
        ;;
    status) status ;;
    log) show_log ;;
    *)
        if [ -n "$1" ]; then
            echo "[错误] 未知命令: $1"
        fi
        usage
        ;;
esac
