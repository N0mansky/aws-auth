# ==============================================================================
# ⚡ AWS-Auth Windows Quick Installer
# ==============================================================================
# Usage:
#   irm https://raw.githubusercontent.com/N0mansky/aws-auth/main/install.ps1 | iex
#   powershell -ExecutionPolicy Bypass -File .\install.ps1
# ==============================================================================

$ErrorActionPreference = "Stop"

Write-Host "`n⚡ AWS-Auth Windows Quick Installer" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor DarkGray

# 1. Initialize Paths & Options (Safe for both file execution and irm | iex)
if ($null -eq $InstallDir -or [string]::IsNullOrWhiteSpace($InstallDir)) {
    if ($env:LOCALAPPDATA) {
        $InstallDir = "$env:LOCALAPPDATA\Programs\aws-auth"
    } else {
        $InstallDir = "$env:USERPROFILE\.aws-auth\bin"
    }
}

if ($null -eq $ReleaseTag -or [string]::IsNullOrWhiteSpace($ReleaseTag)) {
    $ReleaseTag = "latest"
}

# 2. Check Optional CLI Prerequisites (via winget if available)
if (-not $SkipDeps -and (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Host "`n🔍 Checking prerequisites..." -ForegroundColor Yellow

    # AWS CLI
    if (-not (Get-Command aws -ErrorAction SilentlyContinue)) {
        Write-Host "📦 Installing AWS CLI via winget..." -ForegroundColor Gray
        winget install --id Amazon.AWSCLI -e --accept-package-agreements --accept-source-agreements --silent
    } else {
        Write-Host "  ✅ AWS CLI is already installed" -ForegroundColor Green
    }

    # Session Manager Plugin
    if (-not (Get-Command session-manager-plugin -ErrorAction SilentlyContinue)) {
        Write-Host "📦 Installing AWS SSM Session Manager Plugin via winget..." -ForegroundColor Gray
        winget install --id Amazon.SessionManagerPlugin -e --accept-package-agreements --accept-source-agreements --silent
    } else {
        Write-Host "  ✅ AWS SSM Session Manager Plugin is already installed" -ForegroundColor Green
    }

    # kubectl
    if (-not (Get-Command kubectl -ErrorAction SilentlyContinue)) {
        Write-Host "📦 Installing kubectl via winget..." -ForegroundColor Gray
        winget install --id Kubernetes.kubectl -e --accept-package-agreements --accept-source-agreements --silent
    } else {
        Write-Host "  ✅ kubectl is already installed" -ForegroundColor Green
    }
}

# 3. Setup Target Installation Directory
if (-not (Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

$ExePath = "$InstallDir\aws-auth.exe"

# 4. Check for Local Binary or Download from GitHub Releases
$FoundLocal = $false
if (-not [string]::IsNullOrEmpty($PSScriptRoot)) {
    $LocalCandidate = "$PSScriptRoot\dist\aws-auth.exe"
    if (Test-Path $LocalCandidate) {
        Write-Host "`n📂 Copying local build from dist\aws-auth.exe..." -ForegroundColor Yellow
        Copy-Item -Path $LocalCandidate -Destination $ExePath -Force
        $FoundLocal = $true
    }
}

if (-not $FoundLocal) {
    $DownloadUrl = if ($ReleaseTag -eq "latest") {
        "https://github.com/N0mansky/aws-auth/releases/latest/download/aws-auth-windows-amd64.exe"
    } else {
        "https://github.com/N0mansky/aws-auth/releases/download/$ReleaseTag/aws-auth-windows-amd64.exe"
    }

    Write-Host "`n⬇️  Downloading latest aws-auth binary from GitHub Releases..." -ForegroundColor Yellow
    Write-Host "   URL: $DownloadUrl" -ForegroundColor DarkGray
    
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13
    Invoke-WebRequest -Uri $DownloadUrl -OutFile $ExePath -UseBasicParsing
}

# 5. Add Target Directory to User PATH if not present
$CurrentUserPath = [Environment]::GetEnvironmentVariable("Path", [EnvironmentVariableTarget]::User)
if ($null -eq $CurrentUserPath) {
    $CurrentUserPath = ""
}

if ($CurrentUserPath -notlike "*$InstallDir*") {
    Write-Host "`n⚙️  Adding $InstallDir to User PATH..." -ForegroundColor Yellow
    $NewUserPath = if ([string]::IsNullOrWhiteSpace($CurrentUserPath)) { $InstallDir } else { "$CurrentUserPath;$InstallDir" }
    [Environment]::SetEnvironmentVariable("Path", $NewUserPath, [EnvironmentVariableTarget]::User)
}

# Update current session PATH immediately
if ($env:Path -notlike "*$InstallDir*") {
    $env:Path = "$env:Path;$InstallDir"
}

# 6. Verification & Output
Write-Host "`n============================================================" -ForegroundColor Green
Write-Host "🎉 aws-auth installed successfully!" -ForegroundColor Green
Write-Host "   Binary Location: $ExePath" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Green
Write-Host "`nTo get started:" -ForegroundColor Yellow
Write-Host "  1. Restart your terminal (PowerShell / Command Prompt / Windows Terminal)" -ForegroundColor White
Write-Host "  2. Run: aws-auth`n" -ForegroundColor Cyan
