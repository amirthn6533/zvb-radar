@echo off
chcp 65001 > nul
echo ==========================================================
echo   نصب اجرای همیشگی ربات ZVB (با روشن شدن ویندوز)
echo ==========================================================
echo.
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut(\"$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\ZVB_Radar.lnk\"); $s.TargetPath = \"wscript.exe\"; $s.Arguments = \"`\"\" + (Get-Location).Path + \"\run_silent_background.vbs`\"\"; $s.WorkingDirectory = (Get-Location).Path; $s.Save();"

echo ✅ با موفقیت انجام شد!
echo از این پس با هر بار روشن شدن کامپیوتر، ربات به صورت مخفی
echo در پس‌زمینه اجرا می‌شود و روزی ۲ بار پروژه‌ها را به تلگرام می‌فرستد.
echo.
echo برای شروع کار همین الان، ربات در پس‌زمینه اجرا شد.
start wscript.exe "%~dp0run_silent_background.vbs"
echo.
pause
