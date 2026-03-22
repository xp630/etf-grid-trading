@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

set "PROJECT_DIR=%~dp0project"
set "PID_DIR=%~dp0.pids"

:: 创建PID目录
if not exist "%PID_DIR%" mkdir "%PID_DIR%"

goto :main

:usage
echo ========================================
echo    ETF网格交易系统管理器
echo ========================================
echo.
echo 用法: run.bat [command]
echo.
echo 命令:
echo   start main     - 启动交易系统
echo   start web     - 启动Web面板(Flask)
echo   start streamlit - 启动Streamlit面板
echo   start all     - 启动所有服务
echo   stop main     - 停止交易系统
echo   stop web      - 停止Web面板
echo   stop streamlit - 停止Streamlit面板
echo   stop all      - 停止所有服务
echo   restart main  - 重启交易系统
echo   restart web   - 重启Web面板
echo   restart streamlit - 重启Streamlit面板
echo   restart all   - 重启所有服务
echo   status        - 查看服务状态
echo   log           - 查看日志
echo   help          - 显示帮助
echo.
exit /b 0

:example
echo ========================================
echo    ETF网格交易系统管理器 - 使用示例
echo ========================================
echo.
echo 示例:
echo   run.bat start all          - 启动交易系统 + Web面板
echo   run.bat start streamlit    - 启动Streamlit面板
echo   run.bat stop web           - 停止Web面板
echo   run.bat restart main       - 重启交易系统
echo   run.bat status             - 查看服务状态
echo   run.bat log                - 查看日志
echo   run.bat help               - 显示完整帮助
echo.
exit /b 0

:status
echo ========================================
echo    服务状态
echo ========================================
echo.
echo 交易系统(main.py):
tasklist /FI "WINDOWTITLE eq ETF_Main*" 2>nul | findstr /i "python" >nul
if !errorlevel!==0 (
    echo   [运行中]
) else (
    echo   [已停止]
)

echo Web面板(Flask):
tasklist /FI "WINDOWTITLE eq ETF_Web*" 2>nul | findstr /i "python" >nul
if !errorlevel!==0 (
    echo   [运行中]
) else (
    echo   [已停止]
)

echo Streamlit面板:
tasklist /FI "WINDOWTITLE eq ETF_Streamlit*" 2>nul | findstr /i "python" >nul
if !errorlevel!==0 (
    echo   [运行中]
) else (
    echo   [已停止]
)
echo.
exit /b 0

:log
echo ========================================
echo    最近日志
echo ========================================
set "TODAY=%date:~0,4%%date:~5,2%%date:~8,2%"
if exist "%PROJECT_DIR%\logs\trading_%TODAY%.log" (
    type "%PROJECT_DIR%\logs\trading_%TODAY%.log" | findstr /i "ERROR WARNING INFO"
) else (
    echo 今日日志文件不存在
)
echo.
exit /b 0

:start_main
echo [启动] 交易系统...
cd /d "%PROJECT_DIR%"
start "ETF_Main" cmd /c "python main.py"
echo [成功] 交易系统已在后台启动
exit /b 0

:start_web
echo [启动] Web面板(Flask)...
cd /d "%PROJECT_DIR%"
start "ETF_Web" cmd /c "python web/app.py"
echo [成功] Web面板已在后台启动
echo    访问地址: http://127.0.0.1:5000
exit /b 0

:start_streamlit
echo [启动] Streamlit面板...
cd /d "%PROJECT_DIR%"
start "ETF_Streamlit" cmd /c "streamlit run web/streamlit_app.py --server.port 8501 --server.headless=true"
echo [成功] Streamlit面板已在后台启动
echo    访问地址: http://localhost:8501
exit /b 0

:start_all
call :start_main
call :start_web
exit /b 0

:stop_main
echo [停止] 交易系统...
taskkill /F /FI "WINDOWTITLE eq ETF_Main*" >nul 2>&1
echo [成功] 交易系统已停止
exit /b 0

:stop_web
echo [停止] Web面板...
taskkill /F /FI "WINDOWTITLE eq ETF_Web*" >nul 2>&1
echo [成功] Web面板已停止
exit /b 0

:stop_streamlit
echo [停止] Streamlit面板...
taskkill /F /FI "WINDOWTITLE eq ETF_Streamlit*" >nul 2>&1
echo [成功] Streamlit面板已停止
exit /b 0

:stop_all
call :stop_main
call :stop_web
call :stop_streamlit
exit /b 0

:restart_main
call :stop_main
timeout /t 2 /nobreak >nul
call :start_main
exit /b 0

:restart_web
call :stop_web
timeout /t 2 /nobreak >nul
call :start_web
exit /b 0

:restart_streamlit
call :stop_streamlit
timeout /t 2 /nobreak >nul
call :start_streamlit
exit /b 0

:restart_all
call :stop_all
timeout /t 2 /nobreak >nul
call :start_all
exit /b 0

:main
if "%~1"=="" goto :example
if "%~1"=="help" goto :usage
if "%~1"=="start" (
    if "%~2"=="main" goto :start_main
    if "%~2"=="web" goto :start_web
    if "%~2"=="streamlit" goto :start_streamlit
    if "%~2"=="all" goto :start_all
    echo [错误] 未知服务: %~2
    exit /b 1
)
if "%~1"=="stop" (
    if "%~2"=="main" goto :stop_main
    if "%~2"=="web" goto :stop_web
    if "%~2"=="streamlit" goto :stop_streamlit
    if "%~2"=="all" goto :stop_all
    echo [错误] 未知服务: %~2
    exit /b 1
)
if "%~1"=="restart" (
    if "%~2"=="main" goto :restart_main
    if "%~2"=="web" goto :restart_web
    if "%~2"=="streamlit" goto :restart_streamlit
    if "%~2"=="all" goto :restart_all
    echo [错误] 未知服务: %~2
    exit /b 1
)
if "%~1"=="status" goto :status
if "%~1"=="log" goto :log
echo [错误] 未知命令: %~1
echo.
goto :usage
