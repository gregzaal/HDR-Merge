@echo off
setlocal

set "PY=py -3"
set "MAIN_SCRIPT=hdr_brackets.py"
set "DIST_ROOT=build"
set "GENERATED_OUT_DIR=%DIST_ROOT%\hdr_brackets.dist"
set "OUT_DIR=%DIST_ROOT%\hdr_merge_master.dist"
set "VERSION=dev"
set "ZIP_PATH=%DIST_ROOT%\hdr_merge_master_v%VERSION%.zip"

for /f "tokens=2 delims==" %%v in ('findstr /b "VERSION" "%MAIN_SCRIPT%"') do set "VERSION=%%v"
set "VERSION=%VERSION: =%"
set "VERSION=%VERSION:"=%"
set "VERSION=%VERSION:'=%"
if "%VERSION%"=="" set "VERSION=dev"
set "ZIP_PATH=%DIST_ROOT%\hdr_merge_master_v%VERSION%.zip"

echo [1/5] Installing build dependencies...
%PY% -m pip install -q nuitka ordered-set zstandard
if errorlevel 1 exit /b 1

echo [2/5] Cleaning previous outputs...
if exist "%OUT_DIR%" rmdir /s /q "%OUT_DIR%"
if exist "%GENERATED_OUT_DIR%" rmdir /s /q "%GENERATED_OUT_DIR%"
if exist "%DIST_ROOT%\hdr_brackets.build" rmdir /s /q "%DIST_ROOT%\hdr_brackets.build"
if exist "%ZIP_PATH%" del /q "%ZIP_PATH%"

echo [3/5] Building standalone executable with Nuitka...
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

echo [4/5] Packaging distribution...
powershell -NoProfile -Command "Compress-Archive -Path '%OUT_DIR%\*' -DestinationPath '%ZIP_PATH%' -CompressionLevel Optimal"
if errorlevel 1 exit /b 1

echo [5/5] Done.
echo Version: v%VERSION%
echo Output : %OUT_DIR%
echo Zip    : %ZIP_PATH%