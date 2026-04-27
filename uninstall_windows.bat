@echo off
chcp 65001 >nul 2>&1

echo ============================================
echo   巨浪商品分发 - 卸载本地代理
echo ============================================
echo.

rem 删除开机自启任务
echo 正在删除开机自启任务...
schtasks /delete /tn "LuffyBackend" /f >nul 2>&1
echo   已删除

rem 停止后台进程
echo 正在停止后台服务...
for /f "tokens=2" %%p in ('tasklist /fi "IMAGENAME eq python.exe" /fo csv /nh 2^>nul') do (
    wmic process where "ProcessId=%%~p" get CommandLine 2>nul | findstr /i "start.py" >nul
    if not errorlevel 1 (
        taskkill /f /pid %%~p >nul 2>&1
    )
)
echo   服务已停止

echo.
echo 卸载完成。虚拟环境和数据文件保留在原目录中。
echo 如需完全删除，请手动删除整个 luffy0211 文件夹。
echo.
pause
