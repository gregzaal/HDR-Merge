@echo off
setlocal

set "PY=py -3"
set "MAIN_SCRIPT=hdr_brackets.py"
set "DIST_ROOT=build"
set "GENERATED_OUT_DIR=%DIST_ROOT%\hdr_brackets.dist"
set "OUT_DIR=%DIST_ROOT%\hdr_merge_master.dist"
set "VERSION=dev"

echo [1/4] Installing build dependencies...
%PY% -m pip install -q nuitka ordered-set zstandard
if errorlevel 1 exit /b 1

echo [2/4] Cleaning previous outputs...
if exist "%OUT_DIR%" rmdir /s /q "%OUT_DIR%"
if exist "%GENERATED_OUT_DIR%" rmdir /s /q "%GENERATED_OUT_DIR%"
if exist "%DIST_ROOT%\hdr_brackets.build" rmdir /s /q "%DIST_ROOT%\hdr_brackets.build"

echo [3/4] Building standalone executable with Nuitka...
%PY% -m nuitka ^
	--standalone ^
	--assume-yes-for-downloads ^
	--enable-plugin=tk-inter ^
	--windows-icon-from-ico=icons/icon.ico ^
	--include-data-dir=blender=blender ^
	--include-data-dir=icons=icons ^
	--output-dir=%DIST_ROOT% ^
	--output-filename=hdr_merge_master.exe ^
	%MAIN_SCRIPT%
if errorlevel 1 exit /b 1

if exist "%GENERATED_OUT_DIR%" (
	pushd "%DIST_ROOT%"
	ren "hdr_brackets.dist" "hdr_merge_master.dist"
	popd
)

echo [4/4] Done.
echo Version: v%VERSION%
echo Output : %OUT_DIR%