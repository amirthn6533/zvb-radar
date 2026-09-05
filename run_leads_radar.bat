@echo off
chcp 65001 > nul
title ZVB Lead Scraper - Radar
echo ========================================================
echo   ZVB Electrical & Smart Systems - Lead Radar (Sofia)
echo   Scanning Bazar.bg and Alo.bg for new project requests...
echo ========================================================
python lead_scraper.py
echo.
echo Opening leads dashboard in your browser...
start leads_dashboard.html
pause
