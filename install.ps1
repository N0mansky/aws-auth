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

# 1. Target Directory & Executable Path
$TargetFolder = if ($env:LOCALAPPDATA) {
    "$env:LOCALAPPDATA\Programs\aws-auth"
} else {
    "$env:USERPROFILE\.aws-auth\bin"
}

$BinaryPath = "$TargetFolder\aws-auth.exe"
$LatestReleaseUrl = "https://github.com/N0mansky/aws-auth/releases/latest/download/aws-auth-windows-amd64.exe"

# 2. Check Optional CLI Prerequisites (via winget if available)
if (Get-Command winget -ErrorAction SilentlyContinue) {
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

# 3. Ensure Target Directory Exists
if (-not (Test-Path -LiteralPath $TargetFolder)) {
    [System.IO.Directory]::CreateDirectory($TargetFolder) | Out-Null
}

# 4. Check for Local Binary or Download from GitHub Releases
$InstalledFromLocal = $false
if (-not [string]::IsNullOrEmpty($PSScriptRoot)) {
    $LocalDistFile = "$PSScriptRoot\dist\aws-auth.exe"
    if (Test-Path -LiteralPath $LocalDistFile) {
        Write-Host "`n📂 Copying local build from dist\aws-auth.exe..." -ForegroundColor Yellow
        Copy-Item -LiteralPath $LocalDistFile -Destination $BinaryPath -Force
        $InstalledFromLocal = $true
    }
}

if (-not $InstalledFromLocal) {
    Write-Host "`n⬇️  Downloading latest aws-auth binary from GitHub Releases..." -ForegroundColor Yellow
    Write-Host "   URL: $LatestReleaseUrl" -ForegroundColor DarkGray
    
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13
    Invoke-WebRequest -Uri $LatestReleaseUrl -OutFile $BinaryPath -UseBasicParsing
}

# 5. Add Target Directory to User PATH if not present
$UserPathValue = [Environment]::GetEnvironmentVariable("Path", [EnvironmentVariableTarget]::User)
if ($null -eq $UserPathValue) {
    $UserPathValue = ""
}

if ($UserPathValue -notlike "*$TargetFolder*") {
    Write-Host "`n⚙️  Adding $TargetFolder to User PATH..." -ForegroundColor Yellow
    $UpdatedUserPath = if ([string]::IsNullOrWhiteSpace($UserPathValue)) { $TargetFolder } else { "$UserPathValue;$TargetFolder" }
    [Environment]::SetEnvironmentVariable("Path", $UpdatedUserPath, [EnvironmentVariableTarget]::User)
}

# Update current session PATH immediately
if ($env:Path -notlike "*$TargetFolder*") {
    $env:Path = "$env:Path;$TargetFolder"
}

# 6. Verification & Output
Write-Host "`n============================================================" -ForegroundColor Green
Write-Host "🎉 aws-auth installed successfully!" -ForegroundColor Green
Write-Host "   Binary Location: $BinaryPath" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Green
Write-Host "`nTo get started:" -ForegroundColor Yellow
Write-Host "  1. Restart your terminal (PowerShell / Command Prompt / Windows Terminal)" -ForegroundColor White
Write-Host "  2. Run: aws-auth`n" -ForegroundColor Cyan
