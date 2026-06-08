@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================================
REM MyInvest Review Package Builder
REM Put this .bat in the repository root, then double-click it.
REM It creates a safe review zip without .git, .env, tokens, keys,
REM secrets, cache folders, virtual environments, or large temp files.
REM ============================================================

cd /d "%~dp0"

set "PROJECT_NAME=MyInvest"
for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HHmmss"') do set "TS=%%i"
set "TEMP_ROOT=%~dp0temp"
for %%i in ("%TEMP_ROOT%") do set "TEMP_ROOT=%%~fi"
set "OUT_DIR=%TEMP_ROOT%\review_package_%TS%"
set "ZIP_NAME=%PROJECT_NAME%_review_safe_%TS%.zip"
set "ZIP_PATH=%TEMP_ROOT%\%ZIP_NAME%"

echo.
echo [1/6] Preparing review package folder...
if not exist "%TEMP_ROOT%" mkdir "%TEMP_ROOT%" || goto :ERR
if exist "%OUT_DIR%" rmdir /s /q "%OUT_DIR%"
mkdir "%OUT_DIR%" || goto :ERR

echo.
echo [2/6] Creating file lists and repo diagnostics...

REM Git diagnostics, if git is available and current folder is a repo.
where git >nul 2>nul
if %errorlevel%==0 (
    git rev-parse --is-inside-work-tree >nul 2>nul
    if %errorlevel%==0 (
        git status --short > "%OUT_DIR%\GIT_STATUS_SHORT.txt" 2>nul
        git status > "%OUT_DIR%\GIT_STATUS_FULL.txt" 2>nul
        git branch --show-current > "%OUT_DIR%\GIT_BRANCH.txt" 2>nul
        git rev-parse HEAD > "%OUT_DIR%\GIT_COMMIT.txt" 2>nul
        git ls-files > "%OUT_DIR%\FILE_LIST_GIT_TRACKED.txt" 2>nul
    ) else (
        echo Not a git repository. > "%OUT_DIR%\GIT_STATUS_SHORT.txt"
    )
) else (
    echo Git not found in PATH. > "%OUT_DIR%\GIT_STATUS_SHORT.txt"
)

REM Full visible file list excluding common sensitive/noisy folders.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$excludeDir=@('.git','.venv','venv','env','__pycache__','.pytest_cache','.mypy_cache','.ruff_cache','node_modules','dist','build','.idea','.vscode','logs','tmp','temp','cache','runtime');" ^
  "$excludeName=@('.env','.env.local','.env.production','.env.development','.env.test','*.pem','*.key','*.pfx','*.p12','id_rsa','id_ed25519','known_hosts','*token*','*secret*','*password*','*passwd*','*credential*','*cookie*','*session*','*.db','*.sqlite','*.sqlite3','*.log','*.zip','*.7z','*.rar');" ^
  "Get-ChildItem -Recurse -File | Where-Object {" ^
  "  $rel=$_.FullName.Substring((Get-Location).Path.Length+1);" ^
  "  $parts=$rel -split '[\\/]'; $n=$_.Name;" ^
  "  -not ($parts | Where-Object { ($excludeDir -contains $_) -or ($_ -like 'review_package_*') }) -and" ^
  "  -not ($excludeName | Where-Object { $n -like $_ })" ^
  "} | ForEach-Object { Resolve-Path -Relative $_.FullName } | Set-Content -Encoding UTF8 '%OUT_DIR%\FILE_LIST_VISIBLE.txt'" || goto :ERR

echo.
echo [3/6] Copying review-safe project files...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$out='%OUT_DIR%';" ^
  "$includeRoots=@('README.md','README.txt','.env.example','pyproject.toml','requirements.txt','requirements-dev.txt','environment.yml','setup.cfg','Makefile','run_all.bat','run_check.bat','start_intraday_dashboard.bat','refresh_qmt_portfolio_snapshot.bat','package_review_safe.bat','docs','scripts','config','configs','templates','research','data/registry','data/registries','registry','registries','tests');" ^
  "$excludeDir=@('.git','.venv','venv','env','__pycache__','.pytest_cache','.mypy_cache','.ruff_cache','node_modules','dist','build','.idea','.vscode','logs','tmp','temp','cache','runtime');" ^
  "$excludeName=@('.env','.env.local','.env.production','.env.development','.env.test','*.pem','*.key','*.pfx','*.p12','id_rsa','id_ed25519','known_hosts','*token*','*secret*','*password*','*passwd*','*credential*','*cookie*','*session*','*.db','*.sqlite','*.sqlite3','*.log','*.zip','*.7z','*.rar');" ^
  "foreach($root in $includeRoots){" ^
  "  if(Test-Path $root){" ^
  "    $item=Get-Item $root;" ^
  "    if($item.PSIsContainer){" ^
  "      Get-ChildItem $item.FullName -Recurse -File | Where-Object {" ^
  "        $rel=$_.FullName.Substring((Get-Location).Path.Length+1); $parts=$rel -split '[\\/]'; $n=$_.Name;" ^
  "        -not ($parts | Where-Object { ($excludeDir -contains $_) -or ($_ -like 'review_package_*') }) -and" ^
  "        -not ($excludeName | Where-Object { $n -like $_ })" ^
  "      } | ForEach-Object {" ^
  "        $rel=$_.FullName.Substring((Get-Location).Path.Length+1);" ^
  "        $dest=Join-Path $out $rel;" ^
  "        New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null;" ^
  "        Copy-Item $_.FullName $dest -Force;" ^
  "      }" ^
  "    } else {" ^
  "      if(-not ($excludeName | Where-Object { $item.Name -like $_ })){ Copy-Item $item.FullName (Join-Path $out $item.Name) -Force }" ^
  "    }" ^
  "  }" ^
  "}" || goto :ERR

REM Directory tree for the copied package only.
pushd "%OUT_DIR%"
tree /f /a > "DIRECTORY_TREE.txt" 2>nul
popd

echo.
echo [4/6] Scanning copied package for possible sensitive filenames...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$patterns=@('*token*','*secret*','*password*','*passwd*','*credential*','*.pem','*.key','id_rsa','id_ed25519','*cookie*','*session*');" ^
  "$hits=@(); foreach($pat in $patterns){ $hits += Get-ChildItem '%OUT_DIR%' -Recurse -Force -File -Filter $pat -ErrorAction SilentlyContinue };" ^
  "$hits += Get-ChildItem '%OUT_DIR%' -Recurse -Force -File -Filter '.env*' -ErrorAction SilentlyContinue | Where-Object { $_.Name -ne '.env.example' };" ^
  "$hits=$hits | Sort-Object FullName -Unique;" ^
  "$hits | Select-Object -ExpandProperty FullName | Set-Content -Encoding UTF8 '%OUT_DIR%\SENSITIVE_FILENAME_SCAN.txt';" ^
  "if($hits.Count -gt 0){ Write-Host 'WARNING: Possible sensitive filenames found. See %OUT_DIR%\SENSITIVE_FILENAME_SCAN.txt' } else { 'No suspicious filenames found.' | Set-Content -Encoding UTF8 '%OUT_DIR%\SENSITIVE_FILENAME_SCAN.txt' }" || goto :ERR

echo.
echo [5/6] Creating package manifest and hashes...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop';" ^
  "$out='%OUT_DIR%';" ^
  "$files=Get-ChildItem $out -Recurse -File;" ^
  "$hashLines=$files | ForEach-Object { $rel=$_.FullName.Substring((Resolve-Path $out).Path.Length+1); $h=(Get-FileHash $_.FullName -Algorithm SHA256).Hash; \"$h  $rel\" };" ^
  "$hashLines | Set-Content -Encoding UTF8 (Join-Path $out 'SHA256SUMS.txt');" ^
  "$manifest=@();" ^
  "$manifest += '# MyInvest Review Package Manifest';" ^
  "$manifest += '';" ^
  "$manifest += ('Generated at: ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'));" ^
  "$manifest += 'Source path: local repository root (full path omitted)';" ^
  "$manifest += ('Package folder: ' + (Split-Path -Leaf $out));" ^
  "$manifest += ('Zip file: %ZIP_NAME%');" ^
  "$manifest += '';" ^
  "$manifest += 'Included roots when present: README, .env.example, docs, scripts, config/configs, templates, research, registry/registries, tests, requirements/pyproject, selected helper .bat files.';" ^
  "$manifest += 'Excluded by default: .git, runtime, generated review packages, env folders, cache folders, logs, zips, databases, token/secret/password/key/env-like filenames. .env.example is allowed as a template.';" ^
  "$manifest += '';" ^
  "$manifest += 'Before uploading, open SENSITIVE_FILENAME_SCAN.txt and confirm there is no credential or account information.';" ^
  "$manifest | Set-Content -Encoding UTF8 (Join-Path $out 'REVIEW_PACKAGE_MANIFEST.md')" || goto :ERR

echo.
echo [6/6] Creating zip file...
if exist "%ZIP_PATH%" del /q "%ZIP_PATH%"
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference='Stop'; Compress-Archive -Path '%OUT_DIR%\*' -DestinationPath '%ZIP_PATH%' -Force" || goto :ERR

echo.
echo ============================================================
echo Done.
echo Created: %ZIP_PATH%
echo Folder : %OUT_DIR%
echo.
echo Please open %OUT_DIR%\SENSITIVE_FILENAME_SCAN.txt before upload.
echo If it is clean, upload %ZIP_PATH% for review.
echo ============================================================
echo.
pause
exit /b 0

:ERR
echo.
echo ERROR: Packaging failed. Please check the message above.
echo.
pause
exit /b 1
