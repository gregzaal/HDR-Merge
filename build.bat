@echo off
setlocal

set "PY=py -3"
set "MAIN_SCRIPT=hdr_brackets.py"
set "DIST_ROOT=build"
set "OUT_DIR=%DIST_ROOT%\hdr_brackets.dist"
set "VERSION=dev"

echo [1/4] Installing build dependencies...
%PY% -m pip install -q nuitka ordered-set zstandard
if errorlevel 1 exit /b 1

echo [2/4] Cleaning previous outputs...
if exist "%OUT_DIR%" rmdir /s /q "%OUT_DIR%"
if exist "%DIST_ROOT%\hdr_brackets.build" rmdir /s /q "%DIST_ROOT%\hdr_brackets.build"
if exist "%DIST_ROOT%\hdr_brackets.exe" del /q "%DIST_ROOT%\hdr_brackets.exe"

echo [3/4] Building standalone executable with Nuitka...
%PY% -m nuitka ^
	--standalone ^
	--assume-yes-for-downloads ^
	--enable-plugin=tk-inter ^
	--windows-icon-from-ico=icons/icon.ico ^
	--include-data-dir=blender=blender ^
	--include-data-dir=icons=icons ^
	--output-dir=%DIST_ROOT% ^
	--output-filename=hdr_brackets.exe ^
	%MAIN_SCRIPT%
if errorlevel 1 exit /b 1

echo [4/4] Done.
echo Version: v%VERSION%
echo Output : %OUT_DIR%