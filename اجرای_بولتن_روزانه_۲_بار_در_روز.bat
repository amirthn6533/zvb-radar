@echo off
chcp 65001 > nul
title ZVB Daily Digest & Scheduler (Twice a Day)
echo ==========================================================
echo       ZVB Daily Digest - انتشار خودکار روزی ۲ بار در تلگرام
echo       زمان‌بندی: ساعت ۰۹:۰۰ صبح و ۱۸:۰۰ عصر (به وقت صوفیه)
echo       این پنجره را باز بگذارید تا سیستم سر ساعت بولتن‌ها را
echo       به گروه تلگرام شرکت ZVB ارسال کند.
echo ==========================================================
python daily_digest.py
pause
