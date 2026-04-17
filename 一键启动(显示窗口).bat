@echo off
title 下单助手服务
cd /d "%~dp0order-helper-backend"
echo 正在启动后端服务...
python app.py
pause
