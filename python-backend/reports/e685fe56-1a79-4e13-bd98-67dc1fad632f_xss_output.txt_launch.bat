@echo off
title XSStrike XSS ENGINE
color 0A
echo.
echo  [ WebSecureX ] ENGINE: XSStrike XSS ENGINE
echo  Powered by WebSecureX Security Platform
echo.
echo  Target: https://www.zaproxy.org/
echo.
echo ============================================================
echo  AUDIT IN PROGRESS — DO NOT CLOSE THIS WINDOW
echo ============================================================
echo.
"E:\WebSecureX.(2)\venv\Scripts\python.exe" "E:\WebSecureX.(2)\engines\xss_engine\XSStrike\xsstrike.py" "--url" "https://www.zaproxy.org/" "--crawl" "--threads" "10" "--timeout" "10" "--headers" "{"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36"}" "--skip" "--blind" "--fuzzer"
echo.
echo ============================================================
echo  SCAN COMPLETE — This window closes in 30 seconds
echo ============================================================
timeout /t 30 /nobreak > nul