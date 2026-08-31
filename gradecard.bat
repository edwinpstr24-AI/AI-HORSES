@echo off
REM AI Horses - gradecard.bat
REM Run the MORNING AFTER, once the official Equibase chart is out.
REM Grades the card, rebuilds the pages and the record.
REM
REM   gradecard                          newest card
REM   gradecard CARDS\GP-2026-08-31-D.json

setlocal
cd /d "%~dp0"

set CARD=%~1
if "%CARD%"=="" (
  for /f "delims=" %%f in ('dir /b /o-d CARDS\*.json 2^>nul') do (
    set CARD=CARDS\%%f
    goto :found
  )
  echo No cards found in CARDS\
  exit /b 1
)
:found
echo Card: %CARD%
echo.
echo Chart: https://www.equibase.com/static/chart/summary/[TRACK][MMDDYY]USA-EQB.html
echo.

python grade.py "%CARD%"
if errorlevel 1 goto :fail
echo.

echo --- rebuilding card pages
python build_pages.py
if errorlevel 1 goto :fail
echo.

echo --- rebuilding record
python record.py
if errorlevel 1 goto :fail

echo.
echo ================================================
echo  Graded. Commit and push in GitHub Desktop.
echo ================================================
exit /b 0

:fail
echo.
echo STOPPED - fix the error above.
exit /b 1
