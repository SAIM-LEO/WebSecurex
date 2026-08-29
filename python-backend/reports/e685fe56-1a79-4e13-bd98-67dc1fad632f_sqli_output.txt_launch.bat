@echo off
title sqlmap SQL INJECTION ENGINE
color 0A
echo.
echo  [ WebSecureX ] ENGINE: sqlmap SQL INJECTION ENGINE
echo  Powered by WebSecureX Security Platform
echo.
echo  Target: https://www.zaproxy.org/
echo.
echo ============================================================
echo  AUDIT IN PROGRESS — DO NOT CLOSE THIS WINDOW
echo ============================================================
echo.
"E:\WebSecureX.(2)\venv\Scripts\python.exe" "E:\WebSecureX.(2)\engines\sqli_engine\sqlmap\sqlmap.py" "-u" "https://www.zaproxy.org/" "--data=username=test&password=test" "--batch" "--random-agent" "--dbs" "--crawl=5" "--threads=10" "--level=5" "--risk=3" "--output-dir=E:\WebSecureX.(2)\python-backend\reports\e685fe56-1a79-4e13-bd98-67dc1fad632f\sqlmap"
echo.
echo ============================================================
echo  SCAN COMPLETE — This window closes in 30 seconds
echo ============================================================
timeout /t 30 /nobreak > nul