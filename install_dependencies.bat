@echo off
chcp 65001 > nul
echo =================================================================
echo.
echo      "极速跨盘迁移工具" 依赖库安装程序
echo.
echo =================================================================
echo.
echo 本脚本将安装运行此工具所需的 Python 包。
echo.

pip install --upgrade pip
pip install psutil

echo.
echo =================================================================
echo.
echo   所有依赖库已安装/更新完毕。
echo.
echo =================================================================
echo.
pause
