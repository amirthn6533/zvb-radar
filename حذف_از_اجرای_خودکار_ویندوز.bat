@echo off
chcp 65001 > nul
echo ==========================================================
echo   حذف ربات ZVB از اجرای خودکار ویندوز
echo ==========================================================
powershell -Command "Remove-Item -Force -ErrorAction SilentlyContinue \"$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\ZVB_Radar.lnk\""
echo ✅ با موفقیت حذف شد. ربات دیگر با روشن شدن ویندوز خودکار اجرا نمی‌شود.
echo.
pause
