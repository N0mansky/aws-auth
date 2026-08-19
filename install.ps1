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

# 1. Target Directory & Executable Path (Pure .NET resolution)
$LocalApp = [Environment]::GetFolderPath([Environment+SpecialFolder]::LocalApplicationData)
if ([string]::IsNullOrWhiteSpace($LocalApp)) {
    $LocalApp = [Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile)
}

$InstallDirectory = "$LocalApp\Programs\aws-auth"
$ExecutableFile = "$InstallDirectory\aws-auth.exe"
$ReleaseDownloadUrl = "https://github.com/N0mansky/aws-auth/releases/latest/download/aws-auth-windows-amd64.exe"

# 2. Check Optional CLI Prerequisites (via winget if available)
$HasWinget = $null -ne (Get-Command -Name winget -ErrorAction SilentlyContinue)
if ($HasWinget) {
    Write-Host "`n🔍 Checking prerequisites..." -ForegroundColor Yellow

    # AWS CLI
    if (-not (Get-Command -Name aws -ErrorAction SilentlyContinue)) {
        Write-Host "📦 Installing AWS CLI via winget..." -ForegroundColor Gray
        winget install --id Amazon.AWSCLI -e --accept-package-agreements --accept-source-agreements --silent
    } else {
        Write-Host "  ✅ AWS CLI is already installed" -ForegroundColor Green
    }

    # Session Manager Plugin
    if (-not (Get-Command -Name session-manager-plugin -ErrorAction SilentlyContinue)) {
        Write-Host "📦 Installing AWS SSM Session Manager Plugin via winget..." -ForegroundColor Gray
        winget install --id Amazon.SessionManagerPlugin -e --accept-package-agreements --accept-source-agreements --silent
    } else {
        Write-Host "  ✅ AWS SSM Session Manager Plugin is already installed" -ForegroundColor Green
    }

    # kubectl
    if (-not (Get-Command -Name kubectl -ErrorAction SilentlyContinue)) {
        Write-Host "📦 Installing kubectl via winget..." -ForegroundColor Gray
        winget install --id Kubernetes.kubectl -e --accept-package-agreements --accept-source-agreements --silent
    } else {
        Write-Host "  ✅ kubectl is already installed" -ForegroundColor Green
    }
}

# 3. Create Target Directory (.NET API - never throws on existing/empty path)
[System.IO.Directory]::CreateDirectory($InstallDirectory) | Out-Null

# 4. Check for Local Binary or Download from GitHub Releases
$CopiedFromLocal = $false
try {
    $LocalDist = "$PSScriptRoot\dist\aws-auth.exe"
    if (-not [string]::IsNullOrWhiteSpace($PSScriptRoot) -and [System.IO.File]::Exists($LocalDist)) {
        Write-Host "`n📂 Copying local build from dist\aws-auth.exe..." -ForegroundColor Yellow
        [System.IO.File]::Copy($LocalDist, $ExecutableFile, $true)
        $CopiedFromLocal = $true
    }
} catch {
    $CopiedFromLocal = $false
}

if (-not $CopiedFromLocal) {
    Write-Host "`n⬇️  Downloading latest aws-auth binary from GitHub Releases..." -ForegroundColor Yellow
    Write-Host "   URL: $ReleaseDownloadUrl" -ForegroundColor DarkGray
    
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13
    (New-Object System.Net.WebClient).DownloadFile($ReleaseDownloadUrl, $ExecutableFile)
}

# 5. Add Target Directory to User PATH if not present
$CurrentUserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($null -eq $CurrentUserPath) {
    $CurrentUserPath = ""
}

if ($CurrentUserPath -notlike "*$InstallDirectory*") {
    Write-Host "`n⚙️  Adding $InstallDirectory to User PATH..." -ForegroundColor Yellow
    $NewUserPath = if ([string]::IsNullOrWhiteSpace($CurrentUserPath)) { $InstallDirectory } else { "$CurrentUserPath;$InstallDirectory" }
    [Environment]::SetEnvironmentVariable("Path", $NewUserPath, "User")
}

# Update current session PATH immediately
if ($env:Path -notlike "*$InstallDirectory*") {
    $env:Path = "$env:Path;$InstallDirectory"
}

# 6. Verification & Output
Write-Host "`n============================================================" -ForegroundColor Green
Write-Host "🎉 aws-auth installed successfully!" -ForegroundColor Green
Write-Host "   Binary Location: $ExecutableFile" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Green
Write-Host "`nTo get started:" -ForegroundColor Yellow
Write-Host "  1. Restart your terminal (PowerShell / Command Prompt / Windows Terminal)" -ForegroundColor White
Write-Host "  2. Run: aws-auth`n" -ForegroundColor Cyan
