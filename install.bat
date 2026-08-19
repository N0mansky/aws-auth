@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
setlocal enabledelayedexpansion

echo aws-auth Setup and Build Script
echo ==================================
echo.

echo Step 0: Checking required command-line tools...

winget --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] winget is not available. Cannot automatically install dependencies.
    echo Please ensure aws, kubectl, and session-manager-plugin are installed manually.
) else (
    REM Check and install AWS CLI
    aws --version >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo Installing AWS CLI...
        winget install --id Amazon.AWSCLI -e --accept-package-agreements --accept-source-agreements
        echo [OK] AWS CLI installed.
    ) else (
        echo [OK] AWS CLI already installed.
    )

    REM Check and install kubectl
    kubectl version --client >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo Installing kubectl...
        winget install --id Kubernetes.kubectl -e --accept-package-agreements --accept-source-agreements
        echo [OK] kubectl installed.
    ) else (
        echo [OK] kubectl already installed.
    )

    REM Check and install AWS SSM Session Manager Plugin
    session-manager-plugin --version >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo Installing AWS SSM Session Manager Plugin...
        winget install --id Amazon.SessionManagerPlugin -e --accept-package-agreements --accept-source-agreements
        echo [OK] AWS SSM Session Manager Plugin installed.
    ) else (
        echo [OK] AWS SSM Session Manager Plugin already installed.
    )

    REM winget updates Machine PATH; refresh so this session sees new installs
    call :RefreshPath
    call :EnsureSessionManagerPlugin
)
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Error: Python is not installed or not in PATH.
    echo Please install Python 3.8+ and try again.
    pause
    exit /b 1
)

echo [OK] Python found. Proceeding with setup...
echo.

REM Step 1: Create virtual environment first
echo Step 1: Creating virtual environment...
if exist "venv\Scripts\activate.bat" (
    echo Virtual environment already exists. Skipping creation.
) else (
    echo Creating new virtual environment...
    python -m venv venv
    if %ERRORLEVEL% NEQ 0 (
        echo Error: Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created successfully.
)

REM Step 2: Activate virtual environment
echo Step 2: Activating virtual environment...
call venv\Scripts\activate.bat
echo [OK] Virtual environment activated.

REM Step 3: Install pip if not available
venv\Scripts\pip.exe --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Step 3: Installing pip in virtual environment...
    curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
    venv\Scripts\python.exe get-pip.py --force-reinstall
    del get-pip.py
    echo [OK] Pip installed in virtual environment.
) else (
    echo Step 3: Pip already available in virtual environment.
)

REM Step 4: Install Python dependencies
echo Step 4: Installing Python dependencies...
venv\Scripts\pip.exe install -r requirements.txt
venv\Scripts\pip.exe install -r requirements-dev.txt
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to install Python dependencies.
    pause
    exit /b 1
)
echo [OK] Python dependencies installed.

REM Step 5: Generate PyInstaller spec and build (adapted from install.sh)
echo Step 5: Generating PyInstaller spec file and building the executable...
echo.

echo Generating PyInstaller spec file...
venv\Scripts\pyi-makespec.exe --onefile --hidden-import=aws_auth --hidden-import=aws_auth.cli --hidden-import=aws_auth.mcp_server --hidden-import=aws_auth.auth_manager --hidden-import=aws_auth.caller_identity --hidden-import=aws_auth.config --hidden-import=aws_auth.credentials_manager --hidden-import=aws_auth.ec2_manager --hidden-import=aws_auth.eks_manager --hidden-import=aws_auth.local_browser_manager --hidden-import=aws_auth.profile_manager --hidden-import=aws_auth.sso_client --hidden-import=aws_auth.token_manager --hidden-import=aws_auth.user_interface aws-auth.py

if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to generate PyInstaller spec file.
    pause
    exit /b 1
)

echo Running PyInstaller using the generated spec...
venv\Scripts\pyinstaller.exe aws-auth.spec

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [SUCCESS] Build completed successfully!
    echo Executable created in: dist\aws-auth.exe
    echo.
    echo You can now run the application with:
    echo   dist\aws-auth.exe
    echo.
    echo If SSM connections fail with "SessionManagerPlugin is not found" in another
    echo terminal, open a new terminal or refresh PATH with:
    echo   powershell -Command "$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')"
    echo.
    pause
    exit /b 0
) else (
    echo.
    echo [ERROR] Build failed with error code: %ERRORLEVEL%
    pause
    exit /b 1
)

:RefreshPath
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "[Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')"`) do set "PATH=%%P"
exit /b 0

:EnsureSessionManagerPlugin
session-manager-plugin --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK] AWS SSM Session Manager Plugin verified on PATH.
    exit /b 0
)
if exist "C:\Program Files\Amazon\SessionManagerPlugin\bin\session-manager-plugin.exe" (
    set "PATH=%PATH%;C:\Program Files\Amazon\SessionManagerPlugin\bin"
    echo [OK] Added Session Manager Plugin to PATH for this session.
    exit /b 0
)
echo [WARNING] session-manager-plugin not found. SSM connections may fail until PATH is refreshed.
exit /b 0