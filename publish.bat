@echo off
REM AI Horses - publish.bat
REM Run BEFORE first post. Merges the workbook, validates, builds pages,
REM rebuilds the record. Stops immediately if validation fails.
REM
REM   publish                          newest card, no workbook merge
REM   publish CARDS\GP-2026-08-31-D.json
REM   publish CARDS\GP-2026-08-31-D.json "GULFSTREAM MASTER NEW .xlsm"

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

if not "%~2"=="" (
  echo --- merging workbook scores
  python extract_selections.py "%~2" --merge "%CARD%"
  if errorlevel 1 goto :fail
  echo.
)

echo --- validating
python validate.py "%CARD%"
if errorlevel 1 goto :fail
echo.

echo --- building card pages
python build_pages.py
if errorlevel 1 goto :fail
echo.

echo --- rebuilding record
python record.py
if errorlevel 1 goto :fail

echo.
echo ================================================
echo  Ready. Commit and push in GitHub Desktop.
echo  Do it BEFORE first post.
echo ================================================
exit /b 0

:fail
echo.
echo STOPPED - fix the error above. Nothing further was run.
exit /b 1
