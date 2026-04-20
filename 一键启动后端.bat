@echo off
title 下单助手后端服务器
:: 切换到后端目录
cd /d "%~dp0order-helper-backend"
:: 运行 Python 程序
python app.py
pause
