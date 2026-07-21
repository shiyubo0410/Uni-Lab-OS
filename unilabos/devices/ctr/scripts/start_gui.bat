@echo off
chcp 65001 >nul
echo ========================================
echo 机器人图形化编程系统
echo ========================================
echo.

cd /d "%~dp0"

python robot_gui.py

if errorlevel 1 (
    echo.
    echo ========================================
    echo 程序运行出错
    echo ========================================
    echo.
    pause
)
