@echo off
title StyleSphere - Fashion E-Commerce Platform
cd /d "%~dp0"
echo ========================================================
echo  StyleSphere - Fashion E-Commerce Platform
echo ========================================================
echo.
echo Storefront URL: http://127.0.0.1:5000
echo Admin Portal:   http://127.0.0.1:5000/admin/login
echo.
echo Administrator: admin@stylesphere.com / Admin@12345
echo Demo Customer: customer@example.com (OTP shown on screen)
echo ========================================================
echo.
if exist venv\Scripts\python.exe (
    venv\Scripts\python.exe run.py
) else (
    python run.py
)
pause
