@echo off
title XSStrike XSS ENGINE
color 0A
echo.
echo  [ WebSecureX ] ENGINE: XSStrike XSS ENGINE
echo  Powered by WebSecureX Security Platform
echo.
echo  Target: https://pu.edu.pk/home/bs4yearsdegree/BS-4Years-Information-Technology-NC.html
echo.
echo ============================================================
echo  AUDIT IN PROGRESS — DO NOT CLOSE THIS WINDOW
echo ============================================================
echo.
E:\WebSecureX.(2)\venv\Scripts\python.exe ..\engines\xss_engine\XSStrike\xsstrike.py --url https://pu.edu.pk/home/bs4yearsdegree/BS-4Years-Information-Technology-NC.html --crawl --timeout 10 --seeds 10 --headers "{"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36"}"
echo.
echo ============================================================
echo  SCAN COMPLETE — This window closes in 30 seconds
echo ============================================================
timeout /t 30 /nobreak > nul