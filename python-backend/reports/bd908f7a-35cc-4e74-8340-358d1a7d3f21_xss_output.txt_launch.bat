@echo off
title XSStrike XSS ENGINE
color 0A
echo.
echo  [ WebSecureX ] ENGINE: XSStrike XSS ENGINE
echo  Powered by WebSecureX Security Platform
echo.
echo  Target: https://cms.pu.edu.pk/
echo.
echo ============================================================
echo  AUDIT IN PROGRESS — DO NOT CLOSE THIS WINDOW
echo ============================================================
echo.
"E:\WebSecureX.(2)\venv\Scripts\python.exe" "E:\WebSecureX.(2)\engines\xss_engine\XSStrike\xsstrike.py" "--url" "https://cms.pu.edu.pk/" "--crawl" "--threads" "3" "--timeout" "10" "--headers" "{"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}" "--skip"
echo.
echo ============================================================
echo  SCAN COMPLETE — This window closes in 30 seconds
echo ============================================================
timeout /t 30 /nobreak > nul