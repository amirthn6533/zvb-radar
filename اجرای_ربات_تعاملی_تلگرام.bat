@echo off
chcp 65001 > nul
title ZVB Interactive Telegram Bot Service
echo ==========================================================
echo       ZVB Interactive Telegram Bot 24/7
echo       پاسخگویی زنده به دکمه‌ها و جستجو در تلگرام
echo       + پایش خودکار هر ۱۵ دقیقه و بولتن‌های روزانه
echo ==========================================================
python telegram_bot_service.py
pause
