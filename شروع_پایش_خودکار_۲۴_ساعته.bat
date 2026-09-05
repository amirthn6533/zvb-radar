@echo off
chcp 65001 > nul
title ZVB 24/7 Lead Radar (Sofia)
echo ==========================================================
echo       ZVB Electrical & Smart Systems - 24/7 Radar
echo       این پنجره را نبندید تا سیستم هر ۱۵ دقیقه اسکن کند
echo       و پروژه‌های جدید را به گروه تلگرام شرکت بفرستد.
echo ==========================================================
python lead_scraper.py --interval 15
pause
