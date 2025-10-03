@echo off
chcp 65001 > nul

echo [INFO] Activating Conda environment 'fast_transfer_env'...
call conda activate fast_transfer_env

if %errorlevel% neq 0 (
    echo [ERROR] Failed to activate Conda environment.
    echo Please make sure Conda is installed and the environment 'fast_transfer_env' exists.
    goto :eof
)

echo [INFO] Starting the build process using the Conda environment...
rem Change directory to where the script and spec file are
cd /d "%~dp0"
python -m PyInstaller --clean build.spec

if %errorlevel% equ 0 (
    echo [SUCCESS] Build completed successfully!
    echo The executable is located in the 'dist' folder.
) else (
    echo [ERROR] Build failed with error code %errorlevel%.
)

echo [INFO] Deactivating Conda environment...
call conda deactivate

pause
:eof
