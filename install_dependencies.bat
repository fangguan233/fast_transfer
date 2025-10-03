@echo off
chcp 65001 > nul

echo [INFO] Checking for Conda environment 'fast_transfer_env'...

conda env list | findstr /C:"fast_transfer_env" > nul
if %errorlevel% equ 0 (
    echo [INFO] Conda environment 'fast_transfer_env' already exists.
) else (
    echo [INFO] Conda environment 'fast_transfer_env' not found. Creating it now...
    conda create --name fast_transfer_env python=3.10 -y
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create Conda environment. Please check your Conda installation.
        pause
        goto :eof
    )
    echo [SUCCESS] Conda environment created.
)

echo [INFO] Installing dependencies into 'fast_transfer_env'...
call conda run -n fast_transfer_env pip install psutil pyinstaller pywin32
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    goto :eof
)

echo [SUCCESS] All dependencies are installed correctly in the 'fast_transfer_env' environment.
pause
:eof
