@echo off
REM =====================================================================
REM  IA Platform - lancement (Windows)
REM  1. cree l'environnement Python .venv au premier lancement
REM     et installe les dependances (requirements.txt)
REM  2. active l'environnement
REM  3. demarre l'application : streamlit run app.py
REM =====================================================================
setlocal
cd /d "%~dp0"
title IA Platform
set "PORT=8501"

if exist ".venv\Scripts\activate.bat" goto activer

echo Premier lancement : creation de l'environnement Python .venv ...
where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
%PY% -m venv .venv
if errorlevel 1 goto sans_python

:activer
REM activation de l'environnement
call ".venv\Scripts\activate.bat"

REM installation (ou mise a jour) des dependances si requirements.txt a change
fc /b requirements.txt ".venv\requirements.installe" >nul 2>nul
if not errorlevel 1 goto lancer
echo Installation des dependances ...
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 goto echec_installation
copy /y requirements.txt ".venv\requirements.installe" >nul

:lancer
REM pas de question "email" de Streamlit au premier lancement
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
    if not exist "%USERPROFILE%\.streamlit" mkdir "%USERPROFILE%\.streamlit"
    > "%USERPROFILE%\.streamlit\credentials.toml" echo [general]
    >> "%USERPROFILE%\.streamlit\credentials.toml" echo email = ""
)
echo.
echo IA Platform demarre : http://localhost:%PORT%   - fermez cette fenetre pour arreter
echo.
streamlit run app.py --server.port %PORT%
pause
exit /b 0

:sans_python
echo.
echo Python est introuvable. Installez-le depuis https://www.python.org
echo en cochant "Add Python to PATH", puis relancez lancer.bat.
pause
exit /b 1

:echec_installation
echo.
echo Echec de l'installation des dependances : verifiez la connexion internet puis relancez lancer.bat.
pause
exit /b 1
